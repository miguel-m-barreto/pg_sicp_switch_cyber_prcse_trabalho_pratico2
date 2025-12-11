# greyscrape/scrapers/common/supabase_client.py

import os
import sys
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable, Tuple
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
import requests

from common.run_diff import build_state_hash  # reuse same state hash used by diff

import math
from typing import Any

SCRAPE_COUNT_UNTIL_DELETION_MARK = 1

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env.local")

# Max number of rows per POST to Supabase.
# Keep this conservative to avoid 520 / timeouts due to large payloads.
MAX_ROWS_PER_REQUEST = int(os.getenv("MAX_ROWS_PER_REQUEST", "1000"))

PRODUCT_MAX_ROWS_PER_REQUEST = int(
    os.getenv("PRODUCT_MAX_ROWS_PER_REQUEST", str(MAX_ROWS_PER_REQUEST))
)
VARIANT_MAX_ROWS_PER_REQUEST = int(
    os.getenv("VARIANT_MAX_ROWS_PER_REQUEST", str(MAX_ROWS_PER_REQUEST))
)
SNAPSHOT_MAX_ROWS_PER_REQUEST = int(
    os.getenv("SNAPSHOT_MAX_ROWS_PER_REQUEST", str(MAX_ROWS_PER_REQUEST))
)


def get_env_var(name: str) -> str:
    """
    Read a required environment variable or fail loudly.

    This is shared across all stores using Supabase.
    """
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def utc_now_iso() -> str:
    """
    Return current UTC time in ISO 8601 format with 'Z' suffix.
    """
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Variant helpers
# ---------------------------------------------------------------------------

def _normalize_url_for_variant(url: str) -> str:
    """
    Normalize product URL for variant key construction.

    - Removes query string and fragment
    - Keeps scheme, host and path
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        # In case of weird garbage, just return the raw string
        return url

    cleaned = parsed._replace(query="", fragment="")
    return urlunparse(cleaned)


def build_variant_key(link: str, source_page_path: Optional[str]) -> str:
    """
    Build a stable variant key from:

        normalized_link + "|" + source_page_path

    This distinguishes:
      - different catalog contexts (categories / subcategories)
      - different URL presentations of the same external_id

    It deliberately does NOT depend on price, promotion, stock, etc.
    """
    normalized_link = _normalize_url_for_variant(link or "")
    page_path = (source_page_path or "").strip()
    raw_key = f"{normalized_link}|{page_path}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _sanitize_for_json(value: Any) -> Any:
    """
    Recursively sanitize a Python object for JSON encoding:
    - Replace NaN / +inf / -inf floats with None
    - Recurse into dicts and lists
    """
    if isinstance(value, float):
        # Replace NaN, +inf, -inf with None so that json.dumps() does not fail
        if not math.isfinite(value):
            return None
        return value

    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]

    return value



# ---------------------------------------------------------------------------
# Main ingest logic
# ---------------------------------------------------------------------------

def _derive_store_code(store_label: str) -> str:
    """
    Derive a stable store code from the human label.
    Example:
      'Auchan'      -> 'auchan'
      'Pingo Doce'  -> 'pingo_doce'
    """
    return store_label.strip().lower().replace(" ", "_")


def _ensure_store_row(
    base_rest: str,
    common_headers: dict,
    store_id: int,
    store_label: str,
) -> None:
    """
    Ensure that a row exists in 'stores' for this store_id.

    Uses an upsert on (id), so é idempotente:
      - se não existir, cria
      - se existir, faz merge e segue
    """
    store_code = _derive_store_code(store_label)

    payload = [
        {
            "id": store_id,
            "code": store_code,
            "name": store_label,
        }
    ]

    headers = {
        **common_headers,
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }

    resp = requests.post(
        f"{base_rest}/stores?on_conflict=id",
        headers=headers,
        json=payload,
    )
    if not resp.ok:
        print(
            f"[Supabase][{store_label}] Failed to ensure store row "
            f"(id={store_id}, code='{store_code}'): {resp.status_code} {resp.text}",
            file=sys.stderr,
        )
        resp.raise_for_status()


def push_products_with_snapshots(
    produtos: List[Dict],
    query: str,
    store_id_env_var: str,
    extract_external_id: Callable[[str], Optional[str]],
    parse_price: Callable[[Optional[str]], Optional[float]],
    store_label: str = "store",
) -> None:
    """
    Generic Supabase ingest for product scrapers.

    New schema:

      - scrape_runs
      - products            (catalog-level, one per external_id)
      - product_variants    (one per (store_id, external_id, variant_key))
      - product_snapshots   (one per (variant_id, state_hash))
    """
    if not produtos:
        print(f"[Supabase][{store_label}] No products to send, skipping.")
        return

    supabase_url = get_env_var("SUPABASE_URL")
    service_key = get_env_var("SUPABASE_SERVICE_ROLE_KEY")
    store_id_str = get_env_var(store_id_env_var)
    store_id = int(store_id_str)

    base_rest = f"{supabase_url}/rest/v1"

    common_headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    # Garante que a store existe (idempotente, via upsert)
    _ensure_store_row(
        base_rest=base_rest,
        common_headers=common_headers,
        store_id=store_id,
        store_label=store_label,
    )

    # ------------------------------------------------------------------
    # Create scrape_runs row
    # ------------------------------------------------------------------
    started_at = utc_now_iso()

    run_payload = [
        {
            "store_id": store_id,
            "query": query,
            "started_at": started_at,
            "status": "running",
        }
    ]

    headers_runs = {
        **common_headers,
        "Prefer": "return=representation",
    }

    resp = requests.post(
        f"{base_rest}/scrape_runs",
        headers=headers_runs,
        json=run_payload,
    )
    resp.raise_for_status()

    run_row = resp.json()[0]
    run_id = run_row["id"]
    print(f"[Supabase][{store_label}] Created scrape_run id={run_id}")

    try:
        # ------------------------------------------------------------------
        # Upsert catalog-level products (one per external_id), batched
        # ------------------------------------------------------------------
        product_rows: List[Dict] = []
        ext_seen = set()

        for p in produtos:
            ext_id = extract_external_id(p.get("link", ""))
            if not ext_id:
                continue
            if ext_id in ext_seen:
                # Only one catalog row per external_id in this batch
                continue
            ext_seen.add(ext_id)

            product_rows.append(
                {
                    "store_id": store_id,
                    "external_id": ext_id,
                    "name": p.get("name") or "",
                    "raw_name": p.get("name") or "",
                    "product_url": p.get("link") or "",
                    # New catalog-level fields
                    "brand": p.get("brand"),
                    "category_slug_path": p.get("category_slug_path"),
                    "category_human_1": p.get("category_human_1"),
                    "category_human_2": p.get("category_human_2"),
                    "category_human_3": p.get("category_human_3"),
                    "category_human_4": p.get("category_human_4"),
                    # first_seen_at is managed by DB default on insert
                    "last_seen_at": started_at,
                    "is_active": True,
                    "not_on_scrape_count": 0,
                }
            )


        if not product_rows:
            print(
                f"[Supabase][{store_label}] No products with valid external_id, "
                "skipping."
            )
            return

        headers_products = {
            **common_headers,
            "Prefer": "return=representation,resolution=merge-duplicates",
        }

        products_returned: List[Dict] = []

        for i in range(0, len(product_rows), PRODUCT_MAX_ROWS_PER_REQUEST):
            chunk = product_rows[i : i + PRODUCT_MAX_ROWS_PER_REQUEST]
            resp = requests.post(
                f"{base_rest}/products?on_conflict=store_id,external_id",
                headers=headers_products,
                json=chunk,
            )
            if not resp.ok:
                print(
                    f"[Supabase][{store_label}] Products batch FAILED "
                    f"(status={resp.status_code}): {resp.text}",
                    file=sys.stderr,
                )
                resp.raise_for_status()
            products_returned.extend(resp.json())


        # external_id -> product_id map
        product_id_by_ext: Dict[str, int] = {
            row["external_id"]: row["id"] for row in products_returned
        }

        # ------------------------------------------------------------------
        # Upsert product_variants, batched
        # ------------------------------------------------------------------
        variant_rows: List[Dict] = []
        variant_key_set: set[Tuple[str, str]] = set()  # (external_id, variant_key)

        for p in produtos:
            link = p.get("link") or ""
            ext_id = extract_external_id(link)
            if not ext_id:
                continue

            product_id = product_id_by_ext.get(ext_id)
            if not product_id:
                continue

            source_page_path = p.get("source_page_path")
            variant_key = build_variant_key(link, source_page_path)

            dedup_key = (ext_id, variant_key)
            if dedup_key in variant_key_set:
                continue
            variant_key_set.add(dedup_key)

            variant_rows.append(
                {
                    "product_id": product_id,
                    "store_id": store_id,
                    "external_id": ext_id,
                    "variant_key": variant_key,
                    "product_url": _normalize_url_for_variant(link),
                    "source_page_path": source_page_path,
                    "source_cgid": p.get("source_cgid"),

                    "raw_name": p.get("name") or "",
                    "normalized_name": p.get("name") or "",
                    "quantity": p.get("min_quantity"),

                    # NOVO – metadados de produto/variant
                    "brand": p.get("brand"),
                    "product_type": p.get("product_type"),
                    "category_slug_path": p.get("category_slug_path"),
                    "category_human_1": p.get("category_human_1"),
                    "category_human_2": p.get("category_human_2"),
                    "category_human_3": p.get("category_human_3"),
                    "category_human_4": p.get("category_human_4"),

                    "image_url": p.get("image_url"),
                    "image_alt": p.get("image_alt"),
                    "image_title": p.get("image_title"),
                    "unit_suffix": p.get("unit_suffix"),

                    "is_bio": bool(p.get("is_bio")),
                    "is_national_product": bool(p.get("is_national_product")),
                    "is_refrigerated": bool(p.get("is_refrigerated")),

                    "rating_product_id": p.get("rating_product_id"),
                    "rating_url": p.get("rating_url"),

                    # labels completos (lista de dicts) como jsonb
                    "labels_raw": p.get("labels_raw"),
                }
            )


        if not variant_rows:
            print(
                f"[Supabase][{store_label}] No product_variants to insert "
                "(no valid links / variant keys)."
            )
            return

        headers_variants = {
            **common_headers,
            "Prefer": "return=representation,resolution=merge-duplicates",
        }

        variants_returned: List[Dict] = []

        for i in range(0, len(variant_rows), VARIANT_MAX_ROWS_PER_REQUEST):
            chunk = variant_rows[i : i + VARIANT_MAX_ROWS_PER_REQUEST]
            resp = requests.post(
                f"{base_rest}/product_variants"
                f"?on_conflict=store_id,external_id,variant_key",
                headers=headers_variants,
                json=chunk,
            )
            if not resp.ok:
                print(
                    f"[Supabase][{store_label}] Variant batch FAILED "
                    f"(status={resp.status_code}): {resp.text}",
                    file=sys.stderr,
                )
                resp.raise_for_status()
            variants_returned.extend(resp.json())


        # ------------------------------------------------------------------
        # Build variant_map FIRST (from all returned batches)
        # ------------------------------------------------------------------
        variant_map: Dict[Tuple[str, str], Tuple[int, int]] = {}
        for row in variants_returned:
            ext_id = row["external_id"]
            vkey = row["variant_key"]
            variant_map[(ext_id, vkey)] = (row["id"], row["product_id"])

        # ------------------------------------------------------------------
        # Insert product_snapshots, batched
        # ------------------------------------------------------------------
        snapshot_rows: List[Dict] = []
        snapshot_seen: set[Tuple[int, str]] = set()  # (variant_id, state_hash)

        for p in produtos:
            link = p.get("link", "")
            ext_id = extract_external_id(link)
            if not ext_id:
                continue

            source_page_path = p.get("source_page_path")
            variant_key = build_variant_key(link, source_page_path)
            vm = variant_map.get((ext_id, variant_key))
            if not vm:
                continue

            variant_id, product_id = vm

            state_hash = build_state_hash(p)

            dedup_key = (variant_id, state_hash)
            if dedup_key in snapshot_seen:
                continue
            snapshot_seen.add(dedup_key)

            snapshot_rows.append(
                {
                    "variant_id": variant_id,
                    "product_id": product_id,
                    "scraped_at": started_at,
                    "state_hash": state_hash,

                    # preços parseados (numéricos) que já usavas
                    "price": parse_price(p.get("current_price_raw")),
                    "old_price": parse_price(p.get("old_price_raw")),
                    "unit_price": parse_price(p.get("unit_price_raw")),
                    "currency": "EUR",

                    # strings tal como aparecem no site
                    "current_price_raw": p.get("current_price_raw"),
                    "old_price_raw": p.get("old_price_raw"),
                    "unit_price_raw": p.get("unit_price_raw"),
                    "promotion_raw": p.get("promotion_raw"),
                    "discount_badge_raw": p.get("discount_badge_raw"),
                    "min_quantity": p.get("min_quantity"),

                    # campos GTM numéricos vindos do scraper
                    "gtm_price": p.get("original_price"),
                    "gtm_discount_value": p.get("discount_value"),
                    "gtm_quantity": p.get("gtm_quantity"),
                    "final_price": p.get("final_price"),

                    # flags de estado
                    "promo_label": p.get("promotion_raw"),
                    "is_on_promotion": p.get("is_on_promotion"),
                    "stock_status": p.get("stock_status"),
                    "limited_availability_flag": p.get("limited_availability_flag"),
                    "delay_delivery_flag": p.get("delay_delivery_flag"),

                    # snapshot completo para futuro / debug
                    "raw_json": p,
                    "run_id": run_id,
                }
            )


        if not snapshot_rows:
            print(
                f"[Supabase][{store_label}] No snapshot rows to insert "
                "(no valid variant/state combinations)."
            )
        else:
            headers_snapshots = {
                **common_headers,
                "Prefer": "return=none,resolution=merge-duplicates",
            }

            for i in range(0, len(snapshot_rows), SNAPSHOT_MAX_ROWS_PER_REQUEST):
                chunk = snapshot_rows[i : i + SNAPSHOT_MAX_ROWS_PER_REQUEST]

                # Sanitize NaN / inf values before sending to Supabase
                safe_chunk = _sanitize_for_json(chunk)

                resp = requests.post(
                    f"{base_rest}/product_snapshots"
                    f"?on_conflict=variant_id,state_hash",
                    headers=headers_snapshots,
                    json=safe_chunk,
                )

                if not resp.ok:
                    print(
                        f"[Supabase][{store_label}] Snapshot batch FAILED "
                        f"(status={resp.status_code}): {resp.text}",
                        file=sys.stderr,
                    )
                    resp.raise_for_status()


        # ------------------------------------------------------------------
        # Mark run as success
        # ------------------------------------------------------------------
        finished_at = utc_now_iso()
        update_payload = {"finished_at": finished_at, "status": "success"}

        requests.patch(
            f"{base_rest}/scrape_runs?id=eq.{run_id}",
            headers=common_headers,
            json=update_payload,
        )

        print(
            f"[Supabase][{store_label}] Stored {len(product_rows)} products, "
            f"{len(variant_rows)} variants and {len(snapshot_rows)} snapshots "
            f"(run_id={run_id})"
        )

    except Exception as exc:
        finished_at = utc_now_iso()
        error_payload = {
            "finished_at": finished_at,
            "status": "error",
            "error_msg": str(exc),
        }

        try:
            requests.patch(
                f"{base_rest}/scrape_runs?id=eq.{run_id}",
                headers=common_headers,
                json=error_payload,
            )
        except Exception as patch_exc:
            print(
                f"[Supabase][{store_label}] Failed to update run status after error: "
                f"{patch_exc}",
                file=sys.stderr,
            )

        print(f"[Supabase][{store_label}] ERROR during ingest: {exc}", file=sys.stderr)
        raise


def mark_products_deleted(
    deleted_ids: List[str],
    store_id_env_var: str,
    store_label: str = "store",
) -> None:
    """
    Mark products as deleted/inactive in a single step, without reading from DB.

    Logic:
      - For each external_id in deleted_ids:
          * set is_active = false
          * set deleted_at = now
          * set not_on_scrape_count = SCRAPE_COUNT_UNTIL_DELETION_MARK
    """
    if not deleted_ids:
        return

    supabase_url = get_env_var("SUPABASE_URL")
    service_key = get_env_var("SUPABASE_SERVICE_ROLE_KEY")
    store_id_str = get_env_var(store_id_env_var)
    store_id = int(store_id_str)

    base_rest = f"{supabase_url}/rest/v1"

    common_headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    deleted_at = utc_now_iso()
    batch_size = 200
    ids_list = list(deleted_ids)

    total_marked_deleted = 0

    for i in range(0, len(ids_list), batch_size):
        chunk = ids_list[i : i + batch_size]

        # Build rows as upserts by (store_id, external_id)
        updates = [
            {
                "store_id": store_id,
                "external_id": ext_id,
                "is_active": False,
                "deleted_at": deleted_at,
                "not_on_scrape_count": SCRAPE_COUNT_UNTIL_DELETION_MARK,
                "last_seen_at": deleted_at,
            }
            for ext_id in chunk
        ]

        upsert_headers = {
            **common_headers,
            "Prefer": "return=none,resolution=merge-duplicates",
        }

        try:
            resp = requests.post(
                f"{base_rest}/products?on_conflict=store_id,external_id",
                headers=upsert_headers,
                json=updates,
            )
            resp.raise_for_status()
        except Exception as exc:
            print(
                f"[Supabase][{store_label}] Failed to mark deleted products "
                f"for chunk starting at {i}: {exc}",
                file=sys.stderr,
            )
            raise

        total_marked_deleted += len(chunk)

    print(
        f"[Supabase][{store_label}] Marked {total_marked_deleted} products as "
        f"deleted (threshold = {SCRAPE_COUNT_UNTIL_DELETION_MARK})."
    )

# greyscrape/scrapers/supabase_client.py

import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable
from pathlib import Path

from dotenv import load_dotenv
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

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

    It will:
      - create a row in 'scrape_runs'
      - upsert rows in 'products' on (store_id, external_id)
      - insert rows in 'product_snapshots' linked to the run

    Parameters:
      produtos: list of raw product dicts as returned by the scraper.
      query:   identifier of the run (e.g. 'categoria:produtos-frescos').
      store_id_env_var: env var that holds the store_id (e.g. SUPABASE_AUCHAN_STORE_ID).
      extract_external_id: function that extracts a stable ID from the product URL.
      parse_price: function that converts price strings (like '1,99 €/Kg') into floats.
      store_label: label used only in logs (e.g. 'Auchan', 'Pingo Doce').
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

    # 1) Create scrape_runs row
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
        # Build product rows
        product_rows = []
        for p in produtos:
            ext_id = extract_external_id(p.get("link", ""))
            if not ext_id:
                continue

            product_rows.append(
                {
                    "store_id": store_id,
                    "external_id": ext_id,
                    "name": p.get("nome") or "",
                    "raw_name": p.get("nome") or "",
                    "product_url": p.get("link") or "",
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

        resp = requests.post(
            f"{base_rest}/products?on_conflict=store_id,external_id",
            headers=headers_products,
            json=product_rows,
        )
        resp.raise_for_status()
        products_returned = resp.json()

        # Build external_id -> product_id map
        id_map = {row["external_id"]: row["id"] for row in products_returned}

        # 3) Build product_snapshots rows
        snapshot_rows = []
        for p in produtos:
            ext_id = extract_external_id(p.get("link", ""))
            if not ext_id:
                continue

            product_id = id_map.get(ext_id)
            if not product_id:
                continue

            snapshot_rows.append(
                {
                    "product_id": product_id,
                    "scraped_at": started_at,
                    "price": parse_price(p.get("preco_atual")),
                    "old_price": parse_price(p.get("preco_antigo")),
                    "unit_price": parse_price(p.get("preco_unitario")),
                    "currency": "EUR",
                    "promo_label": p.get("promocao"),
                    "is_featured": False,
                    "stock_status": None,
                    "raw_json": p,
                    "run_id": run_id,
                }
            )

        if not snapshot_rows:
            print(
                f"[Supabase][{store_label}] No snapshot rows to insert, "
                "products mapping failed."
            )
        else:
            batch_size = 500
            headers_snapshots = {
                **common_headers,
                "Prefer": "return=none",
            }

            for i in range(0, len(snapshot_rows), batch_size):
                chunk = snapshot_rows[i : i + batch_size]
                resp = requests.post(
                    f"{base_rest}/product_snapshots",
                    headers=headers_snapshots,
                    json=chunk,
                )

                if not resp.ok:
                    # Print full error from PostgREST
                    print(
                        f"[Supabase][{store_label}] Snapshot batch FAILED "
                        f"(status={resp.status_code}): {resp.text}",
                        file=sys.stderr,
                    )
                    resp.raise_for_status()

        finished_at = utc_now_iso()
        update_payload = {"finished_at": finished_at, "status": "success"}

        requests.patch(
            f"{base_rest}/scrape_runs?id=eq.{run_id}",
            headers=common_headers,
            json=update_payload,
        )

        print(
            f"[Supabase][{store_label}] Stored {len(product_rows)} products and "
            f"{len(snapshot_rows)} snapshots (run_id={run_id})"
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
    Soft-delete logic with hysteresis:

      - For each external_id that disappeared in the current run:
          * increment not_on_scrape_count
          * if not_on_scrape_count >= 3, set is_active = False and deleted_at = now

      - Products that reappear in a later scrape will have their
        not_on_scrape_count reset to 0 and is_active = True in
        push_products_with_snapshots.
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
        ids_csv = ",".join(chunk)

        # 1) Fetch current rows for these external_ids
        select_url = (
            f"{base_rest}/products"
            f"?store_id=eq.{store_id}"
            f"&external_id=in.({ids_csv})"
        )

        try:
            resp = requests.get(select_url, headers=common_headers)
            resp.raise_for_status()
        except Exception as exc:
            print(
                f"[Supabase][{store_label}] Failed to fetch products for deletion "
                f"chunk starting at {i}: {exc}",
                file=sys.stderr,
            )
            raise

        rows = resp.json()
        if not rows:
            continue

        updates = []
        for row in rows:
            current_count = row.get("not_on_scrape_count")
            if current_count is None:
                current_count = 0

            try:
                current_count = int(current_count)
            except (TypeError, ValueError):
                current_count = 0

            new_count = current_count + 1

            update_row: Dict[str, object] = {
                "id": row["id"],
                "not_on_scrape_count": new_count,
            }

            if new_count >= 3:
                update_row["is_active"] = False
                update_row["deleted_at"] = deleted_at
                total_marked_deleted += 1

            updates.append(update_row)

        if not updates:
            continue

        # 2) Upsert updates by primary key id
        upsert_headers = {
            **common_headers,
            "Prefer": "return=none,resolution=merge-duplicates",
        }

        try:
            resp = requests.post(
                f"{base_rest}/products?on_conflict=id",
                headers=upsert_headers,
                json=updates,
            )
            resp.raise_for_status()
        except Exception as exc:
            print(
                f"[Supabase][{store_label}] Failed to update deletion counters "
                f"for chunk starting at {i}: {exc}",
                file=sys.stderr,
            )
            raise

    print(
        f"[Supabase][{store_label}] Processed {len(ids_list)} candidate-deleted "
        f"products (marked {total_marked_deleted} as deleted, threshold >= 3)."
    )

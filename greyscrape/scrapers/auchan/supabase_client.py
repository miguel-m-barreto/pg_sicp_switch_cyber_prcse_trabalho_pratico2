# greyscrape/scrapers/auchan/supabase_client.py

import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable
from dotenv import load_dotenv

import requests

load_dotenv("/home/user/Documents/Trabalho-Pratico2_SCRIPTS/.env.local")

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
        # 2) Build product rows
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
                    "first_seen_at": started_at,
                    "last_seen_at": started_at,
                    "is_active": True,
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

# scraper_git/TESTE/auchan_DB.py
import sys
import os
import json
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

from scraper_git.TESTE.auchan_helper import (
    BASE_URL,
    LOG_DIR_NAME,
    extract_products_from_html,
    parse_total_results,
    format_elapsed_time,
)

load_dotenv("/home/user/Documents/Trabalho-Pratico2_SCRIPTS/.env.local")


# -----------------------------
# Scroll helper for search / landing
# -----------------------------
def _scroll_to_bottom(driver, max_tries: int = 10, wait: float = 1.5) -> None:
    """Scroll until no new content is loaded (for search / landing pages)."""
    last_height = driver.execute_script("return document.body.scrollHeight;")
    stagnant = 0

    for _ in range(max_tries):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)

        new_height = driver.execute_script("return document.body.scrollHeight;")
        if new_height == last_height:
            stagnant += 1
            if stagnant >= 2:
                break
        else:
            stagnant = 0
            last_height = new_height


# -----------------------------
# Category / subcategory scraping
# -----------------------------
def _scrape_category_with_api_and_selenium(
    driver,
    page_path: str,
    cgid: str,
    run_timestamp: str,
) -> List[Dict]:
    """
    Scrape a category or subcategory:
      1) Load the visible page at /pt/<page_path>/
      2) Parse first batch of products from HTML
      3) Use Search-UpdateGrid with the correct cgid for the remaining products

    Examples:
      page_path = "limpeza-e-cuidados-do-lar", cgid = "limpeza-e-cuidados-do-lar"
      page_path = "animais/natal-para-cao-e-gato", cgid = "natal-para-cao-e-gato"
    """
    page_path = page_path.strip("/")
    category_url = f"{BASE_URL}/pt/{page_path}/"

    print(f"[Auchan] Loading category page: {category_url}")
    driver.get(category_url)
    time.sleep(2)

    html = driver.page_source
    all_products = extract_products_from_html(html, run_timestamp)
    seen_links = {p.get("link") for p in all_products if p.get("link")}

    print(f"[Auchan] Initial page: {len(all_products)} products")

    api_base = (
        f"{BASE_URL}/on/demandware.store/"
        "Sites-AuchanPT-Site/pt_PT/Search-UpdateGrid"
    )

    sz = 512  # requested chunk size
    total_expected = parse_total_results(html)

    if total_expected:
        print(f"[Auchan] Counter says total_results = {total_expected}")
    else:
        print("[Auchan] Could not parse total_results from counter, will rely on stagnation.")

    start = len(all_products)
    start_ts = time.time()
    stagnant_chunks = 0  # consecutive chunks with no new products

    while True:
        params = {
            "cgid": cgid,
            "prefn1": "soldInStores",
            "prefv1": "000",
            "start": start,
            "sz": sz,
            "next": "true",
        }

        api_url = f"{api_base}?{urlencode(params)}"
        print(f"[Auchan] Fetching page chunk: start={start}, sz={sz}, cgid={cgid}")

        driver.get(api_url)
        time.sleep(1.5)

        page_html = driver.page_source
        page_products = extract_products_from_html(page_html, run_timestamp)

        added = 0
        if not page_products:
            print("[Auchan] No products returned in this chunk.")
            stagnant_chunks += 1
        else:
            for p in page_products:
                link = p.get("link")
                if link and link in seen_links:
                    continue
                if link:
                    seen_links.add(link)
                all_products.append(p)
                added += 1

            if added == 0:
                stagnant_chunks += 1
                print("[Auchan] Chunk had only duplicates, no new products.")
            else:
                stagnant_chunks = 0  # progress was made
                print(
                    f"[Auchan] Chunk added {added} new products "
                    f"(total so far: {len(all_products)})"
                )

        print(f"[Auchan] Time elapsed: {format_elapsed_time(start_ts)}")

        # Main criterion: reach or exceed what the UI counter claims
        if total_expected and len(all_products) >= total_expected:
            print("[Auchan] Reached or exceeded total_expected from counter, stopping.")
            break

        # Fallback: multiple chunks with zero progress
        if stagnant_chunks > 2:
            print(
                "[Auchan] Multiple stagnant chunks (no new products), "
                "assuming end of results."
            )
            break

        # Move start offset to current total, consistent with counter behaviour
        start = len(all_products)

    return all_products


# -----------------------------
# Supabase helpers
# -----------------------------
def _get_env_var(name: str) -> str:
    """Read required environment variable or fail loudly."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_price(value: Optional[str]) -> Optional[float]:
    """Convert strings like '1,99 €', '1.99 €/Kg' into float, or None."""
    if not value:
        return None

    s = value.replace("€", "").replace("EUR", "")
    s = s.replace("\xa0", " ").strip()

    # Drop units like €/Kg, /kg, etc.
    for token in ["€/Kg", "€/kg", "/Kg", "/kg", "€/Un", "€/un", "/Un", "/un"]:
        s = s.replace(token, "")

    # Take first token with digits
    num_token = None
    for part in s.split():
        if any(ch.isdigit() for ch in part):
            num_token = part
            break

    if not num_token:
        return None

    num_token = num_token.replace(".", "").replace(",", ".")

    try:
        return float(num_token)
    except ValueError:
        return None


def _extract_external_id(link: str) -> Optional[str]:
    """
    Extract a stable external product id from the Auchan product URL.

    Example:
      https://www.auchan.pt/.../espinafres-150-g/2939097.html -> '2939097'
    """
    if not link:
        return None

    path = urlparse(link).path
    last = path.rstrip("/").split("/")[-1]

    if last.endswith(".html"):
        last = last[:-5]

    digits = "".join(ch for ch in last if ch.isdigit())
    return digits or last or None


def _utc_now_iso() -> str:
    """Return current UTC time in ISO 8601 with 'Z'."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _push_to_supabase(produtos: List[Dict], query: str) -> None:
    """
    Insert data into Supabase:
      - create scrape_runs row
      - upsert products on (store_id, external_id)
      - insert product_snapshots rows linked to run
    """
    if not produtos:
        print("[Supabase] No products to send, skipping.")
        return

    supabase_url = _get_env_var("SUPABASE_URL")
    service_key = _get_env_var("SUPABASE_SERVICE_ROLE_KEY")
    store_id_str = _get_env_var("SUPABASE_AUCHAN_STORE_ID")
    store_id = int(store_id_str)

    base_rest = f"{supabase_url}/rest/v1"

    common_headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    # 1) Create scrape_runs row
    started_at = _utc_now_iso()
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
    print(f"[Supabase] Created scrape_run id={run_id}")

    try:
        # 2) Upsert products
        product_rows = []
        for p in produtos:
            ext_id = _extract_external_id(p.get("link", ""))
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
            print("[Supabase] No products with valid external_id, skipping.")
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

        # 3) Create product_snapshots rows
        snapshot_rows = []
        for p in produtos:
            ext_id = _extract_external_id(p.get("link", ""))
            if not ext_id:
                continue

            product_id = id_map.get(ext_id)
            if not product_id:
                continue

            snapshot_rows.append(
                {
                    "product_id": product_id,
                    "scraped_at": started_at,
                    "price": _parse_price(p.get("preco_atual")),
                    "old_price": _parse_price(p.get("preco_antigo")),
                    "unit_price": _parse_price(p.get("preco_unitario")),
                    "currency": "EUR",
                    "promo_label": p.get("promocao"),
                    "is_featured": False,
                    "stock_status": None,
                    "raw_json": p,
                    "run_id": run_id,
                }
            )

        if not snapshot_rows:
            print("[Supabase] No snapshot rows to insert, products mapping failed.")
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

        finished_at = _utc_now_iso()
        update_payload = {"finished_at": finished_at, "status": "success"}

        requests.patch(
            f"{base_rest}/scrape_runs?id=eq.{run_id}",
            headers=common_headers,
            json=update_payload,
        )

        print(
            f"[Supabase] Stored {len(product_rows)} products and "
            f"{len(snapshot_rows)} snapshots (run_id={run_id})"
        )

    except Exception as exc:
        finished_at = _utc_now_iso()
        error_payload = {
            "finished_at": finished_at,
            "status": "error",
            "error_msg": str(exc),
        }

        requests.patch(
            f"{base_rest}/scrape_runs?id=eq.{run_id}",
            headers=common_headers,
            json=error_payload,
        )

        print(f"[Supabase] ERROR during ingest: {exc}", file=sys.stderr)
        raise


# -----------------------------
# Public scrape function
# -----------------------------
def _parse_categoria_arg(produto: str) -> Tuple[str, str]:
    """
    From something like:
      'categoria:limpeza-e-cuidados-do-lar'
      'categoria:animais/natal-para-cao-e-gato'

    return (page_path, cgid).
    """
    raw = produto.split(":", 1)[1].strip().lstrip("/").rstrip("/")
    parts = [p for p in raw.split("/") if p]

    if not parts:
        raise ValueError(f"Invalid categoria argument: {produto}")

    if len(parts) == 1:
        page_path = parts[0]
        cgid = parts[0]
    else:
        page_path = "/".join(parts)
        cgid = parts[-1]

    return page_path, cgid


def scrape_auchan(produto: Optional[str] = None) -> List[Dict]:
    """
    Scrape Auchan search results, category pages or landing page.

      - 'categoria:limpeza-e-cuidados-do-lar'
      - 'categoria:animais/natal-para-cao-e-gato'
      - 'arroz' (search page)
      - None/"" (landing page)
    """
    produto = (produto or "").strip()
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    try:
        # CATEGORY / SUBCATEGORY MODE
        if produto.startswith("categoria"):
            page_path, cgid = _parse_categoria_arg(produto)
            produtos = _scrape_category_with_api_and_selenium(
                driver,
                page_path,
                cgid,
                run_timestamp,
            )
            print(
                f"[Auchan] CATEGORY '{page_path}' (cgid={cgid}): "
                f"fetched {len(produtos)} items"
            )
            return produtos

        # SEARCH / LANDING MODE
        if produto:
            url = (
                f"{BASE_URL}/pt/pesquisa?"
                f"search-button=&q={produto}&lang=null"
            )
            mode = "search"
        else:
            url = f"{BASE_URL}/pt"
            mode = "landing"

        print(f"[Auchan] Loading {mode} page: {url}")
        driver.get(url)

        _scroll_to_bottom(driver)

        html = driver.page_source
        produtos = extract_products_from_html(html, run_timestamp)

        # basic dedup just in case
        seen_links = set()
        unique_produtos: List[Dict] = []

        for p in produtos:
            link = p.get("link")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            unique_produtos.append(p)

        print(
            f"[Auchan] {mode.upper()} '{produto}': "
            f"fetched {len(unique_produtos)} items"
        )
        return unique_produtos

    finally:
        driver.quit()


# -----------------------------
# URL helper + JSON log
# -----------------------------
def _detect_categoria_from_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Extract (page_path, cgid) from an Auchan URL like:

      https://www.auchan.pt/pt/limpeza-e-cuidados-do-lar/
        -> ("limpeza-e-cuidados-do-lar", "limpeza-e-cuidados-do-lar")

      https://www.auchan.pt/pt/animais/natal-para-cao-e-gato/
        -> ("animais/natal-para-cao-e-gato", "natal-para-cao-e-gato")
    """
    parsed = urlparse(url)
    if "auchan.pt" not in (parsed.netloc or ""):
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if not parts or parts[0] != "pt":
        return None

    if len(parts) == 2:
        # /pt/<category>/
        page_path = parts[1]
        cgid = parts[1]
    else:
        # /pt/<category>/<sub>[/...]/ -> last segment is the cgid
        page_path = "/".join(parts[1:])
        cgid = parts[-1]

    return page_path, cgid


def _save_json_log(produtos: List[Dict], context: str) -> str:
    """
    Save all scraped products into a JSON file under ./logs.
    'context' is something like the query/category used (for the filename).
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, LOG_DIR_NAME)
    os.makedirs(log_dir, exist_ok=True)

    safe_ctx = re.sub(r"[^a-zA-Z0-9_-]+", "_", context).strip("_")
    if not safe_ctx:
        safe_ctx = "run"

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"auchan_{safe_ctx}_{timestamp}.json"
    path = os.path.join(log_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(produtos, f, ensure_ascii=False, indent=2)

    print(f"[Auchan] Saved JSON log -> {path}")
    return path


# -----------------------------
# CLI entrypoint
# -----------------------------
if __name__ == "__main__":
    start_ts = time.time()

    if len(sys.argv) < 2:
        print("Usage:")
        print('  python3 auchan_DB.py "categoria:produtos-frescos"')
        print('  python3 auchan_DB.py "categoria:animais/natal-para-cao-e-gato"')
        print('  python3 auchan_DB.py "arroz"')
        print('  python3 auchan_DB.py "https://www.auchan.pt/pt/produtos-frescos/"')
        sys.exit(1)

    arg = sys.argv[1].strip()

    # URL mode
    if arg.startswith("http"):
        cat_info = _detect_categoria_from_url(arg)
        if not cat_info:
            print("[Auchan] Could not detect category/subcategory from URL, aborting.")
            sys.exit(1)

        page_path, cgid = cat_info
        print(f"[Auchan] Detected from URL: page_path='{page_path}', cgid='{cgid}'")
        query_for_db = f"categoria:{page_path}"
        produtos = scrape_auchan(query_for_db)
    else:
        produtos = scrape_auchan(arg)
        query_for_db = arg

    print(f"[Auchan] TOTAL PRODUCTS COLLECTED: {len(produtos)}")

    # Supabase push disabled for now to avoid trashing DB during testing
    # if os.getenv("SUPABASE_URL"):
    #     try:
    #         _push_to_supabase(produtos, query_for_db)
    #     except Exception as e:
    #         print(f"[Supabase] Failed to push data: {e}", file=sys.stderr)
    # else:
    #     print("[Supabase] SUPABASE_URL not set, skipping DB ingest.")

    _save_json_log(produtos, query_for_db)
    print(f"[Auchan] Script finished in: {format_elapsed_time(start_ts)}")

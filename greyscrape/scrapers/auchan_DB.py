# greyscrape/scrapers/auchan_DB.py

import sys
import os
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse, parse_qsl

from auchan.auchan_helper import (
    BASE_URL,
    extract_products_from_html,
    parse_total_results,
)
from store_common import (
    LOG_DIR_NAME,
    format_elapsed_time,
    build_headless_chrome,
    log_msg,
)
from supabase_client import push_products_with_snapshots

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

def _extract_cgid_from_html(html: str) -> Optional[str]:
    """
    Try to detect the real cgid from the page HTML by looking for a
    Search-UpdateGrid URL and parsing its query string.

    Returns:
      - cgid string if found
      - None if no Search-UpdateGrid URL is present (non-scrollable page)
    """
    # Look for something like: Search-UpdateGrid?cgid=...&...
    m = re.search(r"Search-UpdateGrid\?([^\"'>]+)", html)
    if not m:
        return None

    qs = m.group(1)

    try:
        params = dict(parse_qsl(qs))
    except Exception:
        return None

    cgid = params.get("cgid") or params.get("cgId") or params.get("cgid[]")
    if not cgid:
        return None

    return cgid



# -----------------------------
# Category / subcategory scraping
# -----------------------------
def _scrape_category_with_api_and_selenium(
    driver,
    page_path: str,
    cgid: str,
    run_timestamp: str,
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Scrape a category or subcategory:
      1) Load the visible page at /pt/<page_path>/
      2) Parse first batch of products from HTML
      3) If the page uses Search-UpdateGrid (scrollable), use it for more products
         otherwise, return only the initial page products.

    Returns:
      (all_products, stats)

      stats = {
          "page_path": str,
          "original_cgid": str,
          "final_cgid": str,
          "total_expected": Optional[int],
          "chunks": int,
      }
    """
    page_path = page_path.strip("/")
    category_url = f"{BASE_URL}/pt/{page_path}/"

    stats: Dict[str, Any] = {
        "page_path": page_path,
        "original_cgid": cgid,
        "final_cgid": cgid,
        "total_expected": None,
        "chunks": 0,
    }

    log_msg(f"[Auchan] Loading category page: {category_url}")
    driver.get(category_url)
    time.sleep(2)

    html = driver.page_source

    # Total esperado a partir do contador da Auchan (se existir)
    total_expected = parse_total_results(html)
    stats["total_expected"] = total_expected

    # Extract initial products from the visible page
    all_products = extract_products_from_html(html, run_timestamp)
    seen_links = {p.get("link") for p in all_products if p.get("link")}

    log_msg(f"[Auchan] Initial page: {len(all_products)} products")

    # Check if this page actually uses Search-UpdateGrid
    detected_cgid = _extract_cgid_from_html(html)
    if not detected_cgid:
        # Non-scrollable page (e.g. medicamentos com ~15 items)
        log_msg(
            "[Auchan] No Search-UpdateGrid URL found on page, "
            "skipping API chunks and returning only initial products."
        )
        # Attach category info with the original cgid (parsed from URL)
        _attach_category_metadata(all_products, page_path, cgid)
        stats["final_cgid"] = cgid
        stats["chunks"] = 0
        return all_products, stats

    # If we got here, the page is scrollable and uses Search-UpdateGrid
    original_cgid = cgid
    cgid = detected_cgid

    if cgid != original_cgid:
        log_msg(
            f"[Auchan] Adjusted cgid from '{original_cgid}' to '{cgid}' "
            "based on Search-UpdateGrid URL."
        )

    stats["final_cgid"] = cgid

    # Attach category metadata with the FINAL cgid
    _attach_category_metadata(all_products, page_path, cgid)
    api_base = (
        f"{BASE_URL}/on/demandware.store/"
        "Sites-AuchanPT-Site/pt_PT/Search-UpdateGrid"
    )

    if total_expected:
        log_msg(f"[Auchan] Counter says total_results = {total_expected}")
        sz = min(360, total_expected)
    else:
        log_msg(
            "[Auchan] Could not parse total_results from counter, "
            "will rely on stagnation."
        )
        sz = 360  # requested chunk size

    start = len(all_products)
    start_ts = time.time()
    stagnant_chunks = 0
    chunks = 0

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
        log_msg(
            f"[Auchan] Fetching page chunk: start={start}, sz={sz}, cgid={cgid}"
        )

        driver.get(api_url)
        time.sleep(1.5)
        chunks += 1

        page_html = driver.page_source
        page_products = extract_products_from_html(page_html, run_timestamp)

        _attach_category_metadata(page_products, page_path, cgid)

        added = 0
        if not page_products:
            log_msg("[Auchan] No products returned in this chunk.")
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
                log_msg("[Auchan] Chunk had only duplicates, no new products.")
            else:
                stagnant_chunks = 0
                log_msg(
                    f"[Auchan] Chunk added {added} new products "
                    f"(total so far: {len(all_products)})"
                )

        log_msg(f"[Auchan] Time elapsed: {format_elapsed_time(start_ts)}")

        if total_expected and len(all_products) >= total_expected:
            log_msg(
                "[Auchan] Reached or exceeded total_expected from counter, stopping."
            )
            break

        if stagnant_chunks > 2:
            log_msg(
                "[Auchan] Multiple stagnant chunks (no new products), "
                "assuming end of results."
            )
            break

        start = len(all_products)

    stats["chunks"] = chunks
    return all_products, stats


def _attach_category_metadata(
    products: List[Dict],
    page_path: str,
    cgid: str,
) -> None:
    """
    Attach category metadata to each product dict in-place.

    Fields added:
      - source_page_path
      - source_cgid
    """
    for p in products:
        # Do not overwrite if already set (defensive)
        if "source_page_path" not in p:
            p["source_page_path"] = page_path
        if "source_cgid" not in p:
            p["source_cgid"] = cgid

# -----------------------------
# Supabase helpers
# -----------------------------

def push_auchan_to_supabase(produtos: List[Dict], query: str) -> None:
    """
    Thin wrapper around the generic Supabase ingest, configured for Auchan.

    It uses:
      - SUPABASE_AUCHAN_STORE_ID as the store_id env var
      - _extract_external_id to derive external_id from product URLs
      - _parse_price to parse price strings
    """
    push_products_with_snapshots(
        produtos=produtos,
        query=query,
        store_id_env_var="SUPABASE_AUCHAN_STORE_ID",
        extract_external_id=_extract_external_id,
        parse_price=_parse_price,
        store_label="Auchan",
    )


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

    driver = build_headless_chrome()

    try:
        # CATEGORY / SUBCATEGORY MODE
        if produto.startswith("categoria"):
            page_path, cgid = _parse_categoria_arg(produto)

            # Now _scrape_category_with_api_and_selenium returns (products, stats)
            produtos, stats = _scrape_category_with_api_and_selenium(
                driver=driver,
                page_path=page_path,
                cgid=cgid,
                run_timestamp=run_timestamp,
            )

            final_cgid = stats.get("final_cgid", cgid)
            total_expected = stats.get("total_expected")

            if total_expected:
                log_msg(
                    f"[Auchan] CATEGORY '{page_path}' (cgid={final_cgid}): "
                    f"fetched {len(produtos)}/{total_expected} items"
                )
            else:
                log_msg(
                    f"[Auchan] CATEGORY '{page_path}' (cgid={final_cgid}): "
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

        log_msg(f"[Auchan] Loading {mode} page: {url}")
        driver.get(url)

        _scroll_to_bottom(driver)

        html = driver.page_source
        produtos = extract_products_from_html(html, run_timestamp)

        # Basic dedup just in case
        seen_links = set()
        unique_produtos: List[Dict] = []

        for p in produtos:
            link = p.get("link")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            unique_produtos.append(p)

        log_msg(
            f"[Auchan] {mode.upper()} '{produto}': "
            f"fetched {len(unique_produtos)} items"
        )
        return unique_produtos

    finally:
        driver.quit()

# -----------------------------
# URL helper + JSON log
# -----------------------------
def _detect_sub_category_from_url(url: str) -> Optional[Tuple[str, str]]:
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
    Save all scraped products into a JSON file inside this execution's log folder.

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

    log_msg(f"[Auchan] Saved JSON log -> {path}")
    return path


# -----------------------------
# CLI entrypoint
# -----------------------------
if __name__ == "__main__":
    start_ts = time.time()

    if len(sys.argv) < 2:
        log_msg("Usage:")
        log_msg('  python3 auchan_DB.py "categoria:produtos-frescos"')
        log_msg('  python3 auchan_DB.py "categoria:animais/natal-para-cao-e-gato"')
        log_msg('  python3 auchan_DB.py "arroz"')
        log_msg('  python3 auchan_DB.py "https://www.auchan.pt/pt/produtos-frescos/"')
        sys.exit(1)

    arg = sys.argv[1].strip()

    # URL mode
    if arg.startswith("http"):
        cat_info = _detect_sub_category_from_url(arg)
        if not cat_info:
            log_msg(
                "[Auchan] Could not detect category/subcategory from URL, aborting."
            )
            sys.exit(1)

        page_path, cgid = cat_info
        log_msg(
            f"[Auchan] Detected from URL: page_path='{page_path}', cgid='{cgid}'"
        )
        query_for_db = f"categoria:{page_path}"
        produtos = scrape_auchan(query_for_db)
    else:
        produtos = scrape_auchan(arg)
        query_for_db = arg

    log_msg(f"[Auchan] TOTAL PRODUCTS COLLECTED: {len(produtos)}")

    # Supabase push disabled for now to avoid trashing DB during testing
    # if os.getenv("SUPABASE_URL"):
    #     try:
    #         push_auchan_to_supabase(produtos, query_for_db)
    #     except Exception as e:
    #         print(f"[Supabase] Failed to push data: {e}", file=sys.stderr)
    # else:
    #     print("[Supabase] SUPABASE_URL not set, skipping DB ingest.")

    _save_json_log(produtos, query_for_db)
    log_msg(f"[Auchan] Script finished in: {format_elapsed_time(start_ts)}")

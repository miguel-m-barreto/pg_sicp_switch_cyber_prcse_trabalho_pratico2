# greyscrape/scrapers/pingo_doce_scraper.py

import hashlib
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlencode, urlparse, parse_qsl

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import html as html_lib

from dotenv import load_dotenv

from pingo_doce.pingo_doce_helper import (
    BASE_URL,
    extract_products_from_html,
    parse_total_results,
)

from common.store_common import (
    build_headless_chrome,
    format_elapsed_time,
    log_msg,
    log_debug,
    log_warn,
)

from common.supabase_client import push_products_with_snapshots

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

# Timing / chunk settings
WAIT_FIRST_LOAD = float(os.getenv("PINGO_WAIT_FIRST_LOAD", "1"))
WAIT_DEFAULT = float(os.getenv("PINGO_WAIT_DEFAULT", "0.5"))
WAIT_STAGNANT = float(os.getenv("PINGO_WAIT_STAGNANT", "0.2"))
#BASE_CHUNK_SIZE = int(os.getenv("PINGO_BASE_CHUNK_SIZE", "200"))
PINGO_ELAPSED_LOG_INTERVAL = float(os.getenv("PINGO_ELAPSED_LOG_INTERVAL", "30"))


PINGO_WAIT_CLICK_MORE = float(os.getenv("PINGO_WAIT_CLICK_MORE", "1.0"))
PINGO_WAIT_UPDATEGRID = float(os.getenv("PINGO_WAIT_UPDATEGRID", "3.0"))
PINGO_CLICK_MORE_MAX_TRIES = int(os.getenv("PINGO_CLICK_MORE_MAX_TRIES", "2"))


def _extract_cgid_from_html(html: str) -> Optional[str]:
    """
    Extract the effective cgid.
    Priority:
      1) hidden input.category-id (often "ec_...") if present
      2) any Search-UpdateGrid URL that contains cgid=
    """
    if not html:
        return None

    # 1) hidden input.category-id
    m = re.search(r'<input[^>]+class="category-id"[^>]+value="([^"]+)"', html)
    if m:
        val = (m.group(1) or "").strip()
        if val:
            return val

    # 2) cgid inside any UpdateGrid URL (sort options often include it)
    m = re.search(r"Search-UpdateGrid\?[^\"']*cgid=([^&\"']+)", html)
    if m:
        return html_lib.unescape(m.group(1)).strip()

    return None

def _parse_start_sz_from_url(url: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse start/sz from a Search-UpdateGrid URL.
    Returns (start, sz) as ints when present, otherwise (None, None).
    """
    try:
        parsed = urlparse(url)
        params = dict(parse_qsl(parsed.query))
        start = int(params["start"]) if "start" in params else None
        sz = int(params["sz"]) if "sz" in params else None
        return start, sz
    except Exception:
        return None, None


def _build_api_url(template_url: str, cgid: str, start: int, sz: int) -> str:
    parsed = urlparse(template_url)
    params = dict(parse_qsl(parsed.query))

    params["cgid"] = cgid
    params["start"] = str(start)
    params["sz"] = str(sz)

    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return f"{base}?{urlencode(params)}"



def _attach_category_metadata(products: List[Dict], page_path: str, cgid: str) -> None:
    """Attach page_path + cgid to every product."""
    for p in products:
        if "source_page_path" not in p:
            p["source_page_path"] = page_path
        if "source_cgid" not in p:
            p["source_cgid"] = cgid


def _scrape_category_with_api_and_selenium(
    driver,
    page_path: str,
    cgid: str,
    run_timestamp: str,
    worker_id: Optional[int] = None,
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Pingo Doce category scraper logic using Selenium + API chunks.
    """
    page_path = page_path.strip("/")
     # If page_path is a fabricated Search-Show marker, load Search-Show directly.
    if page_path.startswith("_search/"):
        category_url = (
            f"{BASE_URL}/on/demandware.store/Sites-pingo-doce-Site/default/"
            f"Search-Show?cgid={cgid}"
        )
    else:
        category_url = f"{BASE_URL}/home/produtos/{page_path}"
        if "?" not in category_url and not category_url.endswith("/"):
            category_url += "/"

    stats: Dict[str, Any] = {
        "page_path": page_path,
        "original_cgid": cgid,
        "final_cgid": cgid,
        "total_expected": None,
        "chunks": 0,
    }

    log_msg(f"[Pingo_Doce] Loading category page: {category_url}", worker_id=worker_id)
    driver.get(category_url)
    time.sleep(WAIT_FIRST_LOAD)

    # IMPORTANT: on many categories Search-UpdateGrid only appears after clicking "Ver mais"
    _try_enable_infinite_scroll(driver, worker_id=worker_id)
    time.sleep(0.5)

    # Give the page a brief chance to inject Search-UpdateGrid after clicking "Ver mais"
    t0 = time.time()
    while time.time() - t0 < PINGO_WAIT_UPDATEGRID:
        if _extract_updategrid_template_from_html(driver.page_source):
            break
        time.sleep(0.2)

    html = driver.page_source

    all_products = extract_products_from_html(html, run_timestamp)

    seen_keys = set()
    for p in all_products:
        k = _get_dedup_key(p)
        if k:
            seen_keys.add(k)


    stats["total_expected"] = parse_total_results(html)

    log_msg(f"[Pingo_Doce] Initial page: {len(all_products)} products", worker_id=worker_id)

    template_url = _extract_updategrid_template_from_html(html)
    detected_cgid = _extract_cgid_from_html(html)

    log_debug(
        f"[Pingo_Doce] updategrid_template={template_url} detected_cgid={detected_cgid}",
        worker_id=worker_id,
    )

    if not template_url:
        log_msg("[Pingo_Doce] No Search-UpdateGrid template found; returning initial page.", worker_id=worker_id)
        _attach_category_metadata(all_products, page_path, cgid)
        stats["final_cgid"] = cgid
        return all_products, stats

    # If the HTML reveals a different cgid, use that for API pagination

    if detected_cgid and detected_cgid != cgid:
        cgid = detected_cgid


    stats["final_cgid"] = cgid
    _attach_category_metadata(all_products, page_path, cgid)

    # Chunk pagination loop
    # IMPORTANT: Pingo Doce gives the *next page* URL in the "Ver mais" button.
    # We must respect its start/sz to avoid overfetch and misalignment.
    tpl_start, tpl_sz = _parse_start_sz_from_url(template_url)

    # Fallbacks only if template is missing params
    if tpl_start is None:
        tpl_start = len(all_products)
    if tpl_sz is None:
        tpl_sz = 12  # Pingo default is usually 12

    start = tpl_start
    page_sz = tpl_sz

    start_ts = time.time()
    last_elapsed_log = start_ts
    stagnant_chunks = 0
    bad_chunk_count = 0
    chunks = 0

    while True:

        # Hard stop when we know total
        if stats["total_expected"] is not None:
            if start >= stats["total_expected"]:
                break
            if len(seen_keys) >= stats["total_expected"]:
                break

        api_url = _build_api_url(template_url, cgid, start, page_sz)

        driver.get(api_url)
        time.sleep(WAIT_DEFAULT)
        chunks += 1


        page_html = driver.page_source
        page_products = extract_products_from_html(page_html, run_timestamp)
        _attach_category_metadata(page_products, page_path, cgid)

        added = 0
        if not page_products:
            stagnant_chunks += 1
            bad_chunk_count += 1
            time.sleep(WAIT_STAGNANT)
        else:
            for p in page_products:
                k = _get_dedup_key(p)
                if k and k in seen_keys:
                    continue
                if k:
                    seen_keys.add(k)
                all_products.append(p)
                added += 1

            if added == 0:
                bad_chunk_count += 1

            else:
                stagnant_chunks = 0
                bad_chunk_count = 0

        # Periodic progress logs
        now = time.time()

        # If we know total_expected, stop when we've reached it (by unique keys).
        if stats["total_expected"] is not None and len(seen_keys) >= stats["total_expected"]:
            break


        if now - last_elapsed_log >= PINGO_ELAPSED_LOG_INTERVAL:
            log_msg(f"[Pingo_Doce] Elapsed: {format_elapsed_time(start_ts)} (Total: {len(all_products)})", worker_id=worker_id)
            last_elapsed_log = now

        # Stop conditions
        if stagnant_chunks >= 3:
            log_warn("[Pingo_Doce] Stagnant chunks (end of list?).", worker_id=worker_id)
            break
        if bad_chunk_count >= 6:
            break
        
        # Advance by the real page size, not by extracted count (avoids drift).
        start += page_sz

        # If server returned fewer than a full page, that's end-of-list.
        if page_products and len(page_products) < page_sz:
            break


    stats["chunks"] = chunks
    return all_products, stats


def _extract_updategrid_template_from_html(html: str) -> Optional[str]:
    """
    Extract a Search-UpdateGrid URL from DOM.
    Prefer the "Ver mais" button data-url, fallback to any occurrence in HTML.
    Uses BeautifulSoup to avoid regex fragility.
    """
    if not html:
        return None

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        btn = soup.select_one("button.more[data-url]")
        if btn:
            raw = btn.get("data-url")
            if raw:
                return html_lib.unescape(raw).strip()
    except Exception:
        pass

    # Fallback: any occurrence
    m = re.search(r'(https?://[^"\']+/Search-UpdateGrid\?[^"\'>\s]+)', html)
    if m:
        return html_lib.unescape(m.group(1)).strip()

    return None



def _try_enable_infinite_scroll(driver, worker_id: Optional[int] = None) -> None:
    """
    Many Pingo Doce category pages only expose the Search-UpdateGrid endpoint
    after clicking the 'Ver mais' button. This function attempts to click it.
    """
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-tile-pd[data-pid]"))
        )
    except Exception:
        # If tiles never appear, don't block; caller will handle empty HTML/products.
        return

    # If updategrid already present, no need to click anything.
    if _extract_updategrid_template_from_html(driver.page_source):
        return


    for _ in range(max(1, PINGO_CLICK_MORE_MAX_TRIES)):
        btn = None

        # Strategy 0 (best): the actual button that matters
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button.more[data-url]")
        except Exception:
            btn = None

        # Fallback: visible text "Ver mais"
        if btn is None:
            try:
                btn = driver.find_element(
                    By.XPATH,
                    "//button[contains(translate(normalize-space(.),"
                    " 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',"
                    " 'abcdefghijklmnopqrstuvwxyzáàâãäéèêëíìîïóòôõöúùûüç'),"
                    " 'ver mais')]"
                )
            except Exception:
                btn = None


        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(PINGO_WAIT_CLICK_MORE)
        except Exception:
            return

        # Wait briefly for the endpoint to become visible in HTML after click
        t0 = time.time()
        while time.time() - t0 < PINGO_WAIT_UPDATEGRID:
            if _extract_updategrid_template_from_html(driver.page_source):
                break
            time.sleep(0.2)



def _parse_price(value: Optional[str]) -> Optional[float]:
    """Convert '6,49 €/Kg', '4.99 €/Un', '1.234,56 €' into float."""
    if not value:
        return None

    # Strip currency and non-breaking spaces
    s = value.replace("€", "").replace("EUR", "")
    s = s.replace("\xa0", " ").strip()

    # Remove common unit tokens
    for token in [
        "€/Kg", "€/kg", "/Kg", "/kg",
        "€/Un", "€/un", "/Un", "/un",
        "€/L", "€/l", "/L", "/l",
    ]:
        s = s.replace(token, "")

    # Split and grab the first token that has digits
    num_token = None
    for part in s.split():
        if any(ch.isdigit() for ch in part):
            num_token = part
            break

    if not num_token:
        return None

    num = num_token.strip()

    has_comma = "," in num
    has_dot = "." in num

    # Cases:
    #  - '1.234,56' -> European: '.' thousands, ',' decimal
    #  - '1234,56'  -> European: ',' decimal
    #  - '1234.56'  -> '.' decimal
    if has_comma and has_dot:
        # Assume European-style: 1.234,56
        num = num.replace(".", "").replace(",", ".")
    elif has_comma:
        # Only comma, treat comma as decimal, dot (if any) as thousands separator
        num = num.replace(".", "").replace(",", ".")
    else:
        # Only dot or pure digits → assume dot is decimal separator
        pass

    try:
        return float(num)
    except ValueError:
        return None


def _canonicalize_link(link: str) -> str:
    """Canonicalize URL to reduce duplicates when external_id is missing."""
    if not link:
        return ""
    try:
        p = urlparse(link)
        path = (p.path or "").rstrip("/")
        return f"{p.scheme}://{p.netloc}{path}".lower()
    except Exception:
        return link.strip().lower()


def _get_dedup_key(p: Dict[str, Any]) -> Optional[str]:
    link = p.get("link") or ""
    ext = _extract_external_id(link)

    # Only treat numeric IDs as true external ids for dedup
    if ext and re.fullmatch(r"\d+", ext):
        return f"eid:{ext}"

    can = _canonicalize_link(link)
    if can:
        return f"url:{can}"
    return None


def _extract_external_id(link: str) -> Optional[str]:
    """
    Extract stable ID from URL.

    Priority:
      1) numeric query params (pid, productId, id)
      2) numeric suffix in path
      3) stable hash of canonical path (fallback to avoid dropping products)
    """
    if not link:
        return None

    try:
        parsed = urlparse(link)

        # 1) Query param IDs (more reliable when present)
        qs = dict(parse_qsl(parsed.query))
        for key in ("pid", "productId", "product_id", "id"):
            val = qs.get(key)
            if val and re.fullmatch(r"\d+", val):
                return val

        # 2) Numeric suffix in path
        path = parsed.path or ""
        if path.endswith(".html"):
            path = path[:-5]

        last = path.rstrip("/").split("/")[-1]
        m = re.search(r"(\d+)$", last)
        if m:
            return m.group(1)

        # 3) Fallback: stable hash of canonical path (prevents silent drops)
        canonical = (parsed.netloc + path).lower()
        return hashlib.sha1(canonical.encode("utf-8")).hexdigest()

    except Exception:
        return None



def _detect_sub_category_from_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Detect (page_path, cgid) from BOTH:
      - SEO URLs: /home/produtos/...
      - Demandware URLs: Search-Show?cgid=...
    """

    parsed = urlparse(url)
    if "pingodoce.pt" not in (parsed.netloc or ""):
        return None

    # ------------------------------------------------------------------
    # Case 1: Demandware Search-Show (authoritative)
    # ------------------------------------------------------------------
    qs = dict(parse_qsl(parsed.query))
    cgid = qs.get("cgid")
    if cgid:
        # page_path does NOT exist for Search-Show URLs
        # we fabricate a stable one from cgid
        page_path = f"_search/{cgid}"
        return page_path, cgid

    # ------------------------------------------------------------------
    # Case 2: SEO category pages
    # ------------------------------------------------------------------
    parts = [p for p in parsed.path.split("/") if p]

    if len(parts) >= 3 and parts[0] == "home" and parts[1] == "produtos":
        page_parts = parts[2:]
        page_path = "/".join(page_parts)
        inferred_cgid = page_parts[-1]
        return page_path, inferred_cgid

    return None


def push_pingo_to_supabase(produtos: List[Dict], query: str) -> None:
    push_products_with_snapshots(
        produtos=produtos,
        query=query,
        store_id_env_var="SUPABASE_PINGO_STORE_ID",
        extract_external_id=_extract_external_id,
        parse_price=_parse_price,
        store_label="Pingo Doce",
    )


# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pingo_doce_scraper.py <url>")
        print("Ex: python3 pingo_doce_scraper.py https://www.pingodoce.pt/home/produtos/talho")
        sys.exit(1)

    url = sys.argv[1]
    cat_info = _detect_sub_category_from_url(url)
    
    if not cat_info:
        print("[Error] Invalid Pingo Doce category URL.")
        sys.exit(1)

    page_path, cgid = cat_info
    print(f"[CLI] Detected: page_path='{page_path}', cgid='{cgid}'")

    driver = build_headless_chrome()
    try:
        run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        products, stats = _scrape_category_with_api_and_selenium(
            driver=driver,
            page_path=page_path,
            cgid=cgid,
            run_timestamp=run_ts,
            worker_id=0
        )
        
        print(f"[CLI] Finished. Fetched {len(products)} products.")
        print(f"[CLI] Stats: {stats}")

    finally:
        driver.quit()
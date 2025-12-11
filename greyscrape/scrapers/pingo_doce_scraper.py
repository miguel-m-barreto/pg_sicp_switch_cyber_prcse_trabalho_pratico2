# greyscrape/scrapers/pingo_doce_scraper.py

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlencode, urlparse, parse_qsl

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

# Configurações de tempo e chunks
WAIT_FIRST_LOAD = float(os.getenv("PINGO_WAIT_FIRST_LOAD", "1"))
WAIT_DEFAULT = float(os.getenv("PINGO_WAIT_DEFAULT", "0.5"))
WAIT_STAGNANT = float(os.getenv("PINGO_WAIT_STAGNANT", "0.2"))
BASE_CHUNK_SIZE = int(os.getenv("PINGO_BASE_CHUNK_SIZE", "200"))
PINGO_ELAPSED_LOG_INTERVAL = float(os.getenv("PINGO_ELAPSED_LOG_INTERVAL", "30"))


def _extract_cgid_from_html(html: str) -> Optional[str]:
    """Detect 'cgid' parameter from the first Search-UpdateGrid URL in the HTML."""
    m = re.search(r"Search-UpdateGrid\?([^\"'>]+)", html)
    if not m:
        return None

    qs = m.group(1)
    try:
        params = dict(parse_qsl(qs))
    except Exception:
        return None

    return params.get("cgid") or params.get("cgId") or params.get("cgid[]")


def _build_api_url(base_html: str, cgid: str, start: int, sz: int) -> str:
    """Build a Search-UpdateGrid URL for Pingo Doce."""
    m = re.search(r"https://[^\"']+/Search-UpdateGrid\?([^\"'>]+)", base_html)
    if m:
        qs = m.group(1)
        params = dict(parse_qsl(qs))
        params["cgid"] = cgid
        params["start"] = str(start)
        params["sz"] = str(sz)

        full = m.group(0)
        parsed = urlparse(full)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return f"{base}?{urlencode(params)}"

    api_base = f"{BASE_URL}/on/demandware.store/Sites-pingo-doce-Site/default/Search-UpdateGrid"
    params = {"cgid": cgid, "start": start, "sz": sz}
    return f"{api_base}?{urlencode(params)}"


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
    category_url = f"{BASE_URL}/home/produtos/{page_path}"
    
    # Garantir que URL acaba limpo ou com query
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

    html = driver.page_source

    all_products = extract_products_from_html(html, run_timestamp)
    seen_links = {p.get("link") for p in all_products if p.get("link")}

    log_msg(f"[Pingo_Doce] Initial page: {len(all_products)} products", worker_id=worker_id)

    detected_cgid = _extract_cgid_from_html(html)
    if not detected_cgid:
        log_msg("[Pingo_Doce] No Search-UpdateGrid URL found; returning initial page.", worker_id=worker_id)
        _attach_category_metadata(all_products, page_path, cgid)
        stats["final_cgid"] = cgid
        return all_products, stats

    # Se detetámos um cgid diferente na página, usamos esse para a API
    if detected_cgid != cgid:
        cgid = detected_cgid

    stats["final_cgid"] = cgid
    _attach_category_metadata(all_products, page_path, cgid)

    # Lógica de chunks
    base_chunk_size = BASE_CHUNK_SIZE

    start = len(all_products)
    start_ts = time.time()
    last_elapsed_log = start_ts
    stagnant_chunks = 0
    bad_chunk_count = 0
    chunks = 0

    while True:

        api_url = _build_api_url(html, cgid, start, base_chunk_size)
        
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
                link = p.get("link")
                if link and link in seen_links:
                    continue
                if link:
                    seen_links.add(link)
                all_products.append(p)
                added += 1

            if added == 0:
                bad_chunk_count += 1
            else:
                stagnant_chunks = 0
                bad_chunk_count = 0

        # Logs periódicos
        now = time.time()
        if now - last_elapsed_log >= PINGO_ELAPSED_LOG_INTERVAL:
            log_msg(f"[Pingo_Doce] Elapsed: {format_elapsed_time(start_ts)} (Total: {len(all_products)})", worker_id=worker_id)
            last_elapsed_log = now

        # Critérios de paragem
        if stagnant_chunks >= 3:
            log_warn("[Pingo_Doce] Stagnant chunks (end of list?).", worker_id=worker_id)
            break
        if bad_chunk_count >= 6:
            break
        
        start = len(all_products)

    stats["chunks"] = chunks
    return all_products, stats


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


def _extract_external_id(link: str) -> Optional[str]:
    """Extract stable ID from URL."""
    if not link:
        return None
    try:
        path = urlparse(link).path
        if path.endswith(".html"):
            path = path[:-5]
        last = path.split("/")[-1]
        
        # Procura por ID numérico no fim (ex: ...-12345)
        m = re.search(r'(\d+)$', last)
        if m:
            return m.group(1)
    except:
        pass
    return None


def _detect_sub_category_from_url(url: str) -> Optional[Tuple[str, str]]:
    """Helper local para testes CLI: extrai (page_path, cgid) do URL."""
    parsed = urlparse(url)
    if "pingodoce.pt" not in (parsed.netloc or ""):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    
    # Esperado: home/produtos/categoria...
    if len(parts) >= 3 and parts[0] == "home" and parts[1] == "produtos":
        page_parts = parts[2:]
        return "/".join(page_parts), page_parts[-1]
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
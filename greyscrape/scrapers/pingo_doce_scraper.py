# greyscrape/scrapers/pingo_doce_scraper.py

import os
import re
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

WAIT_FIRST_LOAD = float(os.getenv("PINGO_WAIT_FIRST_LOAD", "1"))
WAIT_DEFAULT = float(os.getenv("PINGO_WAIT_DEFAULT", "0.5"))
WAIT_STAGNANT = float(os.getenv("PINGO_WAIT_STAGNANT", "0.2"))
BASE_CHUNK_SIZE = int(os.getenv("PINGO_BASE_CHUNK_SIZE", "200"))
PINGO_ELAPSED_LOG_INTERVAL = float(
    os.getenv("PINGO_ELAPSED_LOG_INTERVAL", "30")
)


def _extract_cgid_from_html(html: str) -> Optional[str]:
    """
    Detect 'cgid' parameter from the first Search-UpdateGrid URL in the HTML.

    Works for URLs like:
      .../Search-UpdateGrid?cgid=ec_talho_200&start=12&sz=12&...
    """
    m = re.search(r"Search-UpdateGrid\?([^\"'>]+)", html)
    if not m:
        return None

    qs = m.group(1)
    try:
        params = dict(parse_qsl(qs))
    except Exception:
        return None

    return params.get("cgid") or params.get("cgId") or params.get("cgid[]")


def _build_api_url(
    base_html: str,
    cgid: str,
    start: int,
    sz: int,
) -> str:
    """
    Build a Search-UpdateGrid URL for Pingo Doce.

    Strategy:
      1) Try to reuse the first Search-UpdateGrid URL in the HTML as a template,
         only changing 'start' and 'sz' (safer).
      2) Fallback: build a minimal URL with only cgid/start/sz.
    """
    m = re.search(
        r"https://[^\"']+/Search-UpdateGrid\?([^\"'>]+)", base_html
    )
    if m:
        # Template from existing URL
        qs = m.group(1)
        params = dict(parse_qsl(qs))
        params["cgid"] = cgid
        params["start"] = str(start)
        params["sz"] = str(sz)

        # Rebuild with same host/path as in template
        full = m.group(0)
        parsed = urlparse(full)
        base = (
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        )
        return f"{base}?{urlencode(params)}"

    # Fallback: minimal API URL
    api_base = (
        f"{BASE_URL}/on/demandware.store/"
        "Sites-pingo-doce-Site/default/Search-UpdateGrid"
    )
    params = {
        "cgid": cgid,
        "start": start,
        "sz": sz,
    }
    return f"{api_base}?{urlencode(params)}"


def _attach_category_metadata(
    products: List[Dict],
    page_path: str,
    cgid: str,
) -> None:
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
    Pingo Doce category scraper:

      1) abre /home/produtos/<page_path>
      2) extrai produtos da página inicial
      3) se houver Search-UpdateGrid, faz chamadas paginadas
    """
    page_path = page_path.strip("/")

    category_url = f"{BASE_URL}/home/produtos/{page_path}"
    if not category_url.endswith("?"):
        category_url += "?"

    stats: Dict[str, Any] = {
        "page_path": page_path,
        "original_cgid": cgid,
        "final_cgid": cgid,
        "total_expected": None,
        "chunks": 0,
    }

    log_msg(f"[Pingo] Loading category page: {category_url}", worker_id=worker_id)
    driver.get(category_url)
    time.sleep(WAIT_FIRST_LOAD)

    html = driver.page_source

    total_expected = parse_total_results(html)
    stats["total_expected"] = total_expected

    all_products = extract_products_from_html(html, run_timestamp)
    seen_links = {p.get("link") for p in all_products if p.get("link")}

    log_msg(
        f"[Pingo] Initial page: {len(all_products)} products",
        worker_id=worker_id,
    )

    detected_cgid = _extract_cgid_from_html(html)
    if not detected_cgid:
        log_msg(
            "[Pingo] No Search-UpdateGrid URL found; returning only initial page.",
            worker_id=worker_id,
        )
        _attach_category_metadata(all_products, page_path, cgid)
        stats["final_cgid"] = cgid
        stats["chunks"] = 0
        return all_products, stats

    original_cgid = cgid
    cgid = detected_cgid

    if cgid != original_cgid:
        log_msg(
            f"[Pingo] Adjusted cgid from '{original_cgid}' to '{cgid}' "
            "based on Search-UpdateGrid URL.",
            worker_id=worker_id,
        )

    stats["final_cgid"] = cgid
    _attach_category_metadata(all_products, page_path, cgid)

    if total_expected:
        log_msg(
            f"[Pingo] Counter says total_results = {total_expected}",
            worker_id=worker_id,
        )
        base_chunk_size = min(BASE_CHUNK_SIZE, int(total_expected * 1.1))
    else:
        log_msg(
            "[Pingo] Could not parse total_results; using stagnation heuristic.",
            worker_id=worker_id,
        )
        base_chunk_size = BASE_CHUNK_SIZE

    start = len(all_products)
    start_ts = time.time()
    last_elapsed_log = start_ts
    stagnant_chunks = 0
    bad_chunk_count = 0
    chunks = 0

    while True:
        if total_expected:
            remaining = total_expected - len(all_products)
            effective_sz = max(12, int(remaining * 1.1))
            if effective_sz < remaining:
                effective_sz = remaining
            if effective_sz > base_chunk_size:
                effective_sz = base_chunk_size
        else:
            effective_sz = base_chunk_size

        api_url = _build_api_url(html, cgid, start, effective_sz)

        log_debug(
            f"[Pingo] Fetching page chunk: start={start}, "
            f"sz={effective_sz}, cgid={cgid}",
            worker_id=worker_id,
        )

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
            log_debug(
                "[Pingo] Empty chunk (no products).",
                worker_id=worker_id,
            )
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
                log_debug(
                    "[Pingo] Chunk only had duplicates.",
                    worker_id=worker_id,
                )
            else:
                stagnant_chunks = 0
                bad_chunk_count = 0
                log_debug(
                    f"[Pingo] Chunk added {added} new products "
                    f"(total so far: {len(all_products)})",
                    worker_id=worker_id,
                )

        now = time.time()
        if now - last_elapsed_log >= PINGO_ELAPSED_LOG_INTERVAL:
            log_msg(
                f"[Pingo] Time elapsed: {format_elapsed_time(start_ts)}",
                worker_id=worker_id,
            )
            last_elapsed_log = now

        if stagnant_chunks >= 3:
            log_warn(
                "[Pingo] Multiple stagnant chunks; assuming end of results.",
                worker_id=worker_id,
            )
            break

        if bad_chunk_count >= 6:
            log_warn(
                "[Pingo] Too many consecutive bad chunks; stopping.",
                worker_id=worker_id,
            )
            break

        start = len(all_products)

    stats["chunks"] = chunks
    return all_products, stats


def _parse_price(value: Optional[str]) -> Optional[float]:
    """Convert '6,49 €/Kg', '4.99 €/Un' into float."""
    if not value:
        return None

    s = value.replace("€", "").replace("EUR", "")
    s = s.replace("\xa0", " ").strip()

    for token in ["€/Kg", "€/kg", "/Kg", "/kg", "€/Un", "€/un", "/Un", "/un"]:
        s = s.replace(token, "")

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
    Extract a stable external id from Pingo Doce product URL.

    Example (expected):
      https://www.pingodoce.pt/home/produtos/.../p/544184  -> '544184'

    Fallback: last path segment with digits.
    """
    if not link:
        return None

    path = urlparse(link).path
    last = path.rstrip("/").split("/")[-1]

    # Strip leading 'p/' if the URL is like .../p/544184
    if last == "p" and len(path.rstrip("/").split("/")) >= 2:
        last = path.rstrip("/").split("/")[-2]

    digits = "".join(ch for ch in last if ch.isdigit())
    return digits or last or None


def push_pingo_to_supabase(produtos: List[Dict], query: str) -> None:
    """Wrapper for Supabase ingest configured for Pingo Doce."""
    push_products_with_snapshots(
        produtos=produtos,
        query=query,
        store_id_env_var="SUPABASE_PINGO_STORE_ID",
        extract_external_id=_extract_external_id,
        parse_price=_parse_price,
        store_label="Pingo Doce",
    )

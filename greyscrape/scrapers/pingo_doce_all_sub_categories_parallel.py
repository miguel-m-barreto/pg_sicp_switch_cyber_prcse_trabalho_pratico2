# greyscrape/scrapers/pingo_all_sub_categories_parallel.py

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading
from urllib.parse import urlparse

from dotenv import load_dotenv
from selenium import webdriver

from pingo_doce.pingo_doce_extract_sub_categories import (
    main as extract_subcats_main,
)

from pingo_doce_scraper import (
    _scrape_category_with_api_and_selenium,
    _parse_price,
    _extract_external_id,
)

import common.store_common as store_common
from common.store_common import (
    init_store_logging,
    format_elapsed_time,
    build_headless_chrome,
    log_msg,
)

# Load .env.local from project root (Trabalho-Pratico2_SCRIPTS)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

# This must match the path where pingo_doce_extract_sub_categories.py writes
# pingo_sub_categories.json:
#
#   base_dir = scrapers/pingo_doce
#   LINK_DIR_NAME = "pingo/links"
#   => scrapers/pingo_doce/pingo/links/pingo_sub_categories.json
LINKS_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "pingo_doce",
    "pingo",
    "links",
    "pingo_sub_categories.json",
)

# Max number of parallel workers (more workers = more CPU/RAM and ban risk)
NUM_WORKERS = int(os.getenv("PINGO_NUM_WORKERS", "1"))


def _load_sub_category_urls(path: str) -> List[str]:
    """
    Load category/subcategory URLs from JSON.

    Supports:
      - ["https://www.pingodoce.pt/home/produtos/...", ...]
      - [{"url": "...", "name": "..."}, ...]
      - {"urls": [...]} / {"categories": [...]} wrappers.
    """
    if not os.path.exists(path):
        log_msg(f"[Pingo] Links JSON not found: {path}")
        raise FileNotFoundError(f"Links JSON not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data: Any = json.load(f)

    # Unwrap if it is a dict
    if isinstance(data, dict):
        if "urls" in data and isinstance(data["urls"], list):
            items = data["urls"]
        elif "categories" in data and isinstance(data["categories"], list):
            items = data["categories"]
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("Unexpected JSON structure for categories file")

    urls: List[str] = []
    for item in items:
        if isinstance(item, str):
            url = item.strip()
        elif isinstance(item, dict):
            url = (item.get("url") or item.get("href") or "").strip()
        else:
            continue

        if not url:
            continue
        if "pingodoce.pt" not in url:
            # Skip anything outside Pingo Doce
            continue

        urls.append(url)

    # Deduplicate while preserving order
    seen = set()
    unique_urls: List[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)

    return unique_urls


def _detect_sub_category_from_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Extract (page_path, cgid) from a Pingo Doce URL like:

      https://www.pingodoce.pt/home/produtos/talho
        -> ("talho", "talho")

      https://www.pingodoce.pt/home/produtos/talho/carne-de-porco
        -> ("talho/carne-de-porco", "carne-de-porco")

    page_path is what we append after /home/produtos/
    cgid is the last segment, used as initial category id.
    """
    parsed = urlparse(url)
    host = parsed.netloc or ""
    if "pingodoce.pt" not in host:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 3:
        # Expect something like /home/produtos/<...>
        return None

    # Expect parts[0] == "home", parts[1] == "produtos"
    if parts[0] != "home" or parts[1] != "produtos":
        return None

    page_parts = parts[2:]
    if not page_parts:
        return None

    page_path = "/".join(page_parts)
    cgid = page_parts[-1]
    return page_path, cgid


def _save_json_log(produtos: List[Dict], context: str) -> str:
    """
    Save all scraped products into a JSON file inside this execution's log folder.

    Folder layout:

      <scrapers>/<STORE_NAME>/logs/<EXECUTION_TS>/json

    STORE_NAME and LOG_DIR_NAME come from store_common.init_store_logging("pingo_doce").
    """
    # Base dir of scrapers package
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Store root: <scrapers>/<STORE_NAME> (e.g. scrapers/pingo_doce)
    store_root = os.path.join(base_dir, store_common.STORE_NAME)

    # If LOG_DIR_NAME is not initialized (defensive fallback),
    # create a simple "logs/<ts>/json" under store_root.
    if store_common.LOG_DIR_NAME is None:
        exec_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = os.path.join(store_root, "logs", exec_ts, "json")
    else:
        # Normal path: logs/<EXECUTION_TS>/json relative to store_root
        log_dir = os.path.join(store_root, store_common.LOG_DIR_NAME)

    os.makedirs(log_dir, exist_ok=True)

    safe_ctx = re.sub(r"[^a-zA-Z0-9_-]+", "_", context).strip("_")
    if not safe_ctx:
        safe_ctx = "run"

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"pingo_{safe_ctx}_{timestamp}.json"
    path = os.path.join(log_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(produtos, f, ensure_ascii=False, indent=2)

    log_msg(f"[Pingo] Saved JSON log -> {path}")
    return path


def _scrape_single_category(
    driver: webdriver.Chrome,
    url: str,
    worker_id: int,
) -> Optional[Tuple[str, int, Optional[int]]]:
    """
    Scrape a single category/subcategory URL using the low-level category scraper.

    Returns:
      (context_string, num_products, total_expected) on success,
      or None on failure (after logging the error).
    """
    cat_info = _detect_sub_category_from_url(url)
    if not cat_info:
        log_msg(
            f"[SKIP] Could not detect category/subcategory from URL: {url}",
            worker_id=worker_id,
        )
        return None

    page_path, cgid = cat_info
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    log_msg(
        f">>> Starting scrape for URL='{url}' "
        f"(page_path='{page_path}', cgid='{cgid}')",
        worker_id=worker_id,
    )

    start_ts = time.time()
    try:
        produtos, stats = _scrape_category_with_api_and_selenium(
            driver=driver,
            page_path=page_path,
            cgid=cgid,
            run_timestamp=run_timestamp,
            worker_id=worker_id,
        )
    except Exception as exc:
        log_msg(f"[ERROR] Failed scraping '{url}': {exc}", worker_id=worker_id)
        return None

    total = len(produtos)
    final_cgid = stats.get("final_cgid", cgid)
    total_expected = stats.get("total_expected")
    chunks = stats.get("chunks")

    context = f"sub_category:{page_path}|cgid={final_cgid}"
    _save_json_log(produtos, context)

    elapsed_str = format_elapsed_time(start_ts)

    if total_expected:
        log_msg(
            f"<<< Finished '{context}': {total}/{total_expected} products "
            f"in {elapsed_str} (chunks={chunks})",
            worker_id=worker_id,
        )
    else:
        log_msg(
            f"<<< Finished '{context}': {total} products "
            f"in {elapsed_str} (chunks={chunks})",
            worker_id=worker_id,
        )

    return context, total, total_expected


def _worker_scrape_loop(
    urls: List[str],
    worker_id: int,
    shared_state: Dict[str, int],
    state_lock: threading.Lock,
) -> Dict[str, Any]:
    """
    Worker that keeps pulling URLs from a shared queue (balanced load).

      - builds its own headless Chrome
      - repeatedly grabs the next URL index from shared_state["next_index"]
      - stops when there are no URLs left
    """
    from selenium.common.exceptions import WebDriverException

    driver = build_headless_chrome()
    worker_start = time.time()

    total_products = 0
    total_estimated = 0
    successful_cats = 0
    failed_urls: List[str] = []
    total_urls = len(urls)

    try:
        while True:
            # Get next job index atomically
            with state_lock:
                idx = shared_state["next_index"]
                if idx >= total_urls:
                    break
                shared_state["next_index"] += 1

            url = urls[idx]

            log_msg("", worker_id=worker_id)
            log_msg("=" * 80, worker_id=worker_id)
            log_msg(f"[{idx + 1}/{total_urls}] {url}", worker_id=worker_id)
            log_msg("=" * 80, worker_id=worker_id)

            try:
                result = _scrape_single_category(driver, url, worker_id)
            except WebDriverException as exc:
                # If Chrome dies, mark current URL as failed and abort worker
                log_msg(
                    f"[FATAL] WebDriverException in worker while scraping '{url}': {exc}",
                    worker_id=worker_id,
                )
                failed_urls.append(url)
                break

            if result is None:
                failed_urls.append(url)
                continue

            _, count, total_expected = result
            total_products += count
            if total_expected is not None:
                total_estimated += total_expected
            successful_cats += 1

    finally:
        driver.quit()

    return {
        "worker_id": worker_id,
        "assigned_urls": successful_cats + len(failed_urls),
        "successful": successful_cats,
        "failed": failed_urls,
        "products": total_products,
        "estimated_products": total_estimated,
        "elapsed": format_elapsed_time(worker_start),
    }


def main() -> None:
    # Initialize logging for this store (folder scrapers/pingo_doce)
    init_store_logging("pingo_doce")

    # Behavior:
    #   - No args  -> generate links JSON (extract_subcats_main) and then load it
    #   - With arg -> DO NOT generate, just use existing JSON

    if len(sys.argv) > 1:
        links_path = LINKS_DEFAULT_PATH
        log_msg(
            f"[Pingo] Using existing category URLs file (no extraction): {links_path}"
        )
        should_extract = False
    else:
        links_path = LINKS_DEFAULT_PATH
        log_msg(
            f"[Pingo] No CLI arg given. Generating category URLs into: {links_path}"
        )
        should_extract = True

    if should_extract:
        # This should create/update the JSON at LINKS_DEFAULT_PATH
        extract_subcats_main()

    log_msg(f"[Pingo] Reading category URLs from: {links_path}")
    urls = _load_sub_category_urls(links_path)
    log_msg(f"[Pingo] Loaded {len(urls)} unique URLs")

    if not urls:
        log_msg("[Pingo] No URLs to scrape. Exiting.")
        return

    global_start = time.time()

    n_workers = min(NUM_WORKERS, len(urls))

    log_msg(
        f"[Pingo] Launching {n_workers} threads over {len(urls)} URLs "
        f"(NUM_WORKERS={NUM_WORKERS})"
    )

    total_products = 0
    total_estimated_products = 0
    total_success = 0
    total_failed: List[str] = []

    # Shared state for dynamic job distribution
    shared_state: Dict[str, int] = {"next_index": 0}
    state_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {
            executor.submit(
                _worker_scrape_loop,
                urls,
                worker_id,
                shared_state,
                state_lock,
            ): worker_id
            for worker_id in range(1, n_workers + 1)
        }

        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                log_msg(
                    f"[Pingo][Worker {worker_id}] crashed with exception: {exc}"
                )
                continue

            log_msg("")
            log_msg(f"[Pingo][Worker {worker_id}] summary: {result}")

            total_products += result["products"]
            total_success += result["successful"]
            total_failed.extend(result["failed"])

    # Save run status so sendToDB can decide if this run is valid
    status = {
        "status": "success"
        if total_success == len(urls) and not total_failed
        else "failed",
        "total_urls": len(urls),
        "successful": total_success,
        "failed": len(total_failed),
        "created_at": datetime.now().isoformat(),
    }
    try:
        os.makedirs(store_common.EXECUTION_LOG_ROOT, exist_ok=True)
        status_path = os.path.join(store_common.EXECUTION_LOG_ROOT, "run_status.json")
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        log_msg(f"[Pingo] Saved run status -> {status_path}")
    except Exception as exc:
        log_msg(f"[Pingo] Failed to write run_status.json: {exc}")

    log_msg("")
    log_msg("-" * 80)
    log_msg(
        f"[Pingo] Batch finished. {total_success}/{len(urls)} URLs scraped "
        f"successfully, total products fetched: {total_products}"
    )

    if total_estimated_products > 0:
        log_msg(
            f"[Pingo] Global products: {total_products}/{total_estimated_products} "
            f"(fetched/estimated from counters)"
        )

    if total_failed:
        log_msg(f"[Pingo] Failed URLs ({len(total_failed)}):")
        for u in total_failed:
            log_msg(f"  - {u}")
    log_msg(f"[Pingo] Total wall-clock time: {format_elapsed_time(global_start)}")
    log_msg("-" * 80)

    # Automatic DB ingest only if this run was successful
    from greyscrape.scrapers.common.send_to_db import send_store_to_db

    status_success = (total_success == len(urls)) and (len(total_failed) == 0)

    if status_success:
        log_msg("[Pingo] Run marked as SUCCESS, starting sendToDB.")
        send_store_to_db(
            logs_root=store_common.STORE_LOGS_ROOT,  # root: scrapers/pingo_doce/logs
            store_id_env_var="SUPABASE_PINGO_STORE_ID",
            store_label="Pingo Doce",
            extract_external_id=_extract_external_id,
            parse_price=_parse_price,
            diff_query_prefix="pingo_diff",
            keep_last_runs=2,
        )
    else:
        log_msg("[Pingo] Run FAILED, skipping sendToDB (DB not touched).")


if __name__ == "__main__":
    main()

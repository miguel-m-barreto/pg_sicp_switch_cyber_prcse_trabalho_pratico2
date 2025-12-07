# greyscrape/scrapers/auchan_all_sub_categories_parallel.py
import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading


from dotenv import load_dotenv
from selenium import webdriver

from auchan_extract_sub_categories import main as extract_subcats_main

from auchan_DB import (
    _scrape_category_with_api_and_selenium,
    _detect_sub_category_from_url,
    _save_json_log,
)

import store_common
from store_common import (
    init_store_logging,
    format_elapsed_time,
    build_headless_chrome,
    log_msg,
)

# Load .env.local a partir da raiz (Trabalho-Pratico2_SCRIPTS)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

LINKS_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "auchan",
    "links",
    "auchan_sub_categories.json",
)

# Max number of parallel workers (more workers more CPU/RAM and ban risk)
NUM_WORKERS = int(os.getenv("AUCHAN_NUM_WORKERS", "1"))


def _load_sub_category_urls(path: str) -> List[str]:
    """
    Load category/subcategory URLs from JSON.

    Supports:
      - ["https://www.auchan.pt/pt/animais/...", ...]
      - [{"url": "...", "name": "..."}, ...]
      - {"urls": [...]} / {"categories": [...]} wrappers.
    """
    if not os.path.exists(path):
        # Neste momento NÃO tens gerador automático de links,
        # por isso falhamos de forma explícita.
        log_msg(f"[Auchan] Links JSON not found: {path}")
        raise FileNotFoundError(f"Links JSON not found: {path}")

        # Se no futuro quiseres gerar o ficheiro automaticamente,
        # podes fazer algo do género:
        #
        # from auchan.generate_links import main as generate_links
        # log_msg("[Auchan] Links file missing, generating it...")
        # generate_links()
        # if not os.path.exists(path):
        #     raise FileNotFoundError(f"Links JSON still missing after generation: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data: Any = json.load(f)

    # Unwrap if it is a dict
    if isinstance(data, dict):
        if "urls" in data and isinstance(data["urls"], list):
            items = data["urls"]
        elif "categories" in data and isinstance(data["categories"], list):
            items = data["categories"]
        else:
            # fallback: assume the dict itself is a single entry
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
        if "auchan.pt" not in url:
            # Skip anything outside Auchan
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
        f">>> Starting scrape for URL='{url}' (page_path='{page_path}', cgid='{cgid}')",
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
                # Se o Chrome morrer, marcamos o URL atual como falhado e abortamos o worker
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
    # Initialize logging for this store
    init_store_logging("auchan")

    # Behavior:
    #   - No args  -> generate links JSON (extract_subcats_main) and then load it
    #   - With arg -> DO NOT generate, just use existing JSON
    #
    # Special case:
    #   - "111"    -> use default LINKS_DEFAULT_PATH, but still skip extraction

    if len(sys.argv) > 1:

        links_path = LINKS_DEFAULT_PATH

        log_msg(
            f"[Auchan] Using existing category URLs file (no extraction): {links_path}"
        )
        should_extract = False
    else:
        # No args -> normal mode: regenerate the links JSON first
        links_path = LINKS_DEFAULT_PATH
        log_msg(
            f"[Auchan] No CLI arg given. Generating category URLs into: {links_path}"
        )
        should_extract = True

    if should_extract:
        # This should create/update the JSON at LINKS_DEFAULT_PATH
        extract_subcats_main()

    log_msg(f"[Auchan] Reading category URLs from: {links_path}")
    urls = _load_sub_category_urls(links_path)
    log_msg(f"[Auchan] Loaded {len(urls)} unique URLs")

    if not urls:
        log_msg("[Auchan] No URLs to scrape. Exiting.")
        return

    global_start = time.time()

    n_workers = min(NUM_WORKERS, len(urls))

    log_msg(
        f"[Auchan] Launching {n_workers} threads over {len(urls)} URLs "
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
                    f"[Auchan][Worker {worker_id}] crashed with exception: {exc}"
                )
                continue

            log_msg("")
            log_msg(f"[Auchan][Worker {worker_id}] summary: {result}")

            total_products += result["products"]
            total_success += result["successful"]
            total_failed.extend(result["failed"])

    # Save run status so sendToDB can decide if this run is valid
    status = {
        "status": "success" if total_success == len(urls) and not total_failed else "failed",
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
        log_msg(f"[Auchan] Saved run status -> {status_path}")
    except Exception as exc:
        log_msg(f"[Auchan] Failed to write run_status.json: {exc}")

    log_msg("")
    log_msg("-" * 80)
    log_msg(
        f"[Auchan] Batch finished. {total_success}/{len(urls)} URLs scraped "
        f"successfully, total products fetched: {total_products}"
    )

    if total_estimated_products > 0:
        log_msg(
            f"[Auchan] Global products: {total_products}/{total_estimated_products} "
            f"(fetched/estimated from counters)"
        )

    if total_failed:
        log_msg(f"[Auchan] Failed URLs ({len(total_failed)}):")
        for u in total_failed:
            log_msg(f"  - {u}")
    log_msg(f"[Auchan] Total wall-clock time: {format_elapsed_time(global_start)}")
    log_msg("-" * 80)

    # Automatic DB ingest only if this run was successful
    from send_to_db import send_store_to_db
    from auchan_DB import _extract_external_id, _parse_price

    status_success = (total_success == len(urls)) and (len(total_failed) == 0)

    if status_success:
        log_msg("[Auchan] Run marked as SUCCESS, starting sendToDB.")
        send_store_to_db(
            logs_root=store_common.STORE_LOGS_ROOT,                     # raiz: greyscrape/scrapers/auchan/logs
            store_id_env_var="SUPABASE_AUCHAN_STORE_ID",
            store_label="Auchan",
            extract_external_id=_extract_external_id,
            parse_price=_parse_price,
            diff_query_prefix="auchan_diff",
            keep_last_runs=2,
        )
    else:
        log_msg("[Auchan] Run FAILED, skipping sendToDB (DB not touched).")


if __name__ == "__main__":
    main()

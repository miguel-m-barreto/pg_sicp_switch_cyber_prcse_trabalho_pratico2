# greyscrape/scrapers/auchan/auchan_all_sub_categories_parallel.py

import json
import math
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver

from auchan_DB import (
    _scrape_category_with_api_and_selenium,
    _detect_sub_category_from_url,
    _save_json_log,
)
from store_common import format_elapsed_time, build_headless_chrome, log_msg


LINKS_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "links",
    "auchan_sub_categories.json",
)

# Max number of parallel workers (tune according to CPU/RAM and ban risk)
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
) -> Optional[Tuple[str, int]]:
    """
    Scrape a single category/subcategory URL using the low-level category scraper.

    Returns:
      (context_string, num_products) on success,
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
        produtos = _scrape_category_with_api_and_selenium(
            driver=driver,
            page_path=page_path,
            cgid=cgid,
            run_timestamp=run_timestamp,
        )
    except Exception as exc:
        log_msg(f"[ERROR] Failed scraping '{url}': {exc}", worker_id=worker_id)
        return None

    total = len(produtos)
    context = f"sub_category:{page_path}"
    _save_json_log(produtos, context)

    log_msg(
        f"<<< Finished '{context}': {total} products in {format_elapsed_time(start_ts)}",
        worker_id=worker_id,
    )
    return context, total


def _worker_scrape_chunk(urls: List[str], worker_id: int) -> Dict[str, Any]:
    """
    Logical worker for one thread:

      - builds its own headless Chrome
      - iterates its URL list in sequence
      - returns aggregated stats
    """
    from selenium.common.exceptions import WebDriverException

    driver = build_headless_chrome()
    worker_start = time.time()

    total_products = 0
    successful_cats = 0
    failed_urls: List[str] = []

    try:
        for idx, url in enumerate(urls, start=1):
            log_msg("", worker_id=worker_id)
            log_msg("=" * 80, worker_id=worker_id)
            log_msg(f"[{idx}/{len(urls)}] {url}", worker_id=worker_id)
            log_msg("=" * 80, worker_id=worker_id)

            result = _scrape_single_category(driver, url, worker_id)
            if result is None:
                failed_urls.append(url)
                continue

            _, count = result
            total_products += count
            successful_cats += 1

    except WebDriverException as exc:
        # Do not assume idx/url exist here
        log_msg(f"[FATAL] WebDriverException in worker: {exc}", worker_id=worker_id)
        # Mark all remaining URLs as failed (including the one that crashed mid-way)
        for url in urls[successful_cats + len(failed_urls):]:
            failed_urls.append(url)
    finally:
        driver.quit()

    return {
        "worker_id": worker_id,
        "assigned_urls": len(urls),
        "successful": successful_cats,
        "failed": failed_urls,
        "products": total_products,
        "elapsed": format_elapsed_time(worker_start),
    }


def main() -> None:
    if len(sys.argv) > 1:
        links_path = sys.argv[1]
    else:
        links_path = LINKS_DEFAULT_PATH

    log_msg(f"[Auchan] Reading category URLs from: {links_path}")
    urls = _load_sub_category_urls(links_path)
    log_msg(f"[Auchan] Loaded {len(urls)} unique URLs")

    if not urls:
        log_msg("[Auchan] No URLs to scrape. Exiting.")
        return

    global_start = time.time()

    # Prepare URL chunks for each worker/thread
    n_workers = min(NUM_WORKERS, len(urls))
    chunk_size = math.ceil(len(urls) / n_workers)
    chunks: List[List[str]] = [
        urls[i : i + chunk_size] for i in range(0, len(urls), chunk_size)
    ]

    log_msg(
        f"[Auchan] Launching {len(chunks)} threads with chunk_size={chunk_size} "
        f"(NUM_WORKERS={NUM_WORKERS})"
    )

    total_products = 0
    total_success = 0
    total_failed: List[str] = []

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {
            executor.submit(_worker_scrape_chunk, chunk, worker_id): worker_id
            for worker_id, chunk in enumerate(chunks, start=1)
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

    log_msg("")
    log_msg("-" * 80)
    log_msg(
        f"[Auchan] Batch finished. {total_success}/{len(urls)} URLs scraped "
        f"successfully, total products fetched: {total_products}"
    )
    if total_failed:
        log_msg(f"[Auchan] Failed URLs ({len(total_failed)}):")
        for u in total_failed:
            log_msg(f"  - {u}")
    log_msg(f"[Auchan] Total wall-clock time: {format_elapsed_time(global_start)}")
    log_msg("-" * 80)


if __name__ == "__main__":
    main()

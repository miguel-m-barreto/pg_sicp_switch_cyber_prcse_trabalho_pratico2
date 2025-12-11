# greyscrape/scrapers/common/generic_parallel_runner.py

import json
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from selenium import webdriver

import common.store_common as store_common
from common.store_common import (
    init_store_logging,
    format_elapsed_time,
    build_headless_chrome,
    log_msg,
)
from common.send_to_db import send_store_to_db

# Type aliases for clarity
ScrapeResult = Optional[Tuple[str, int, Optional[int]]]
ScrapeSingleCategoryFn = Callable[[webdriver.Chrome, str, int], ScrapeResult]
LoadUrlsFn = Callable[[str], List[str]]
ExtractSubcatsFn = Callable[[], None]
ParsePriceFn = Callable[[Optional[str]], Optional[float]]
ExtractIdFn = Callable[[str], Optional[str]]


def _worker_scrape_loop(
    urls: List[str],
    worker_id: int,
    shared_state: Dict[str, int],
    state_lock: threading.Lock,
    scrape_single_category: ScrapeSingleCategoryFn,
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

            log_msg("")
            log_msg("=" * 80)
            log_msg(f"[Worker {worker_id}] [{idx + 1}/{total_urls}] {url}")
            log_msg("=" * 80)

            try:
                result = scrape_single_category(driver, url, worker_id)
            except WebDriverException as exc:
                # If Chrome dies, mark current URL as failed and abort worker
                log_msg(
                    f"[Worker {worker_id}] FATAL WebDriverException while scraping "
                    f"'{url}': {exc}"
                )
                failed_urls.append(url)
                break
            except Exception as exc:
                log_msg(
                    f"[Worker {worker_id}] ERROR unexpected exception while "
                    f"scraping '{url}': {exc}"
                )
                failed_urls.append(url)
                continue

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


def run_parallel_store(
    argv: List[str],
    *,
    store_name: str,
    store_label: str,
    links_path: str,
    links_extractor: Optional[ExtractSubcatsFn],
    load_urls: LoadUrlsFn,
    scrape_single_category: ScrapeSingleCategoryFn,
    store_id_env_var: str,
    diff_query_prefix: str,
    num_workers_env_var: str,
    extract_external_id: ExtractIdFn,
    parse_price: ParsePriceFn,
    keep_last_runs: int = 2,
) -> None:
    """
    Generic parallel runner for a store:

    - initializes logging (init_store_logging)
    - optionally regenerates subcategory links JSON
    - loads URLs
    - runs threaded scrape with balanced queue
    - aggregates stats
    - writes run_status.json
    - calls send_store_to_db on success
    """
    init_store_logging(store_name)

    # Decide whether to regenerate links JSON
    if links_extractor is not None and len(argv) <= 1:
        log_msg(
            f"[{store_label}] No CLI arg given. Generating category URLs into: "
            f"{links_path}"
        )
        links_extractor()
    else:
        log_msg(
            f"[{store_label}] Using existing category URLs file (no extraction): "
            f"{links_path}"
        )

    log_msg(f"[{store_label}] Reading category URLs from: {links_path}")
    urls = load_urls(links_path)
    log_msg(f"[{store_label}] Loaded {len(urls)} unique URLs")

    if not urls:
        log_msg(f"[{store_label}] No URLs to scrape. Exiting.")
        return

    global_start = time.time()

    num_workers = int(os.getenv(num_workers_env_var, "1"))
    n_workers = min(num_workers, len(urls))

    log_msg(
        f"[{store_label}] Launching {n_workers} threads over {len(urls)} URLs "
        f"({num_workers_env_var}={num_workers})"
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
                scrape_single_category,
            ): worker_id
            for worker_id in range(1, n_workers + 1)
        }

        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                log_msg(
                    f"[{store_label}][Worker {worker_id}] crashed with exception: {exc}"
                )
                continue

            log_msg("")
            log_msg(f"[{store_label}][Worker {worker_id}] summary: {result}")

            total_products += result["products"]
            total_success += result["successful"]
            total_failed.extend(result["failed"])
            total_estimated_products += result.get("estimated_products", 0)

    # Save run status so send_to_db can decide if this run is valid
    status = {
        "status": "success"
        if total_success == len(urls) and not total_failed
        else "failed",
        "total_urls": len(urls),
        "successful": total_success,
        "failed": len(total_failed),
        "total_products": total_products,
        "estimated_products": total_estimated_products,
        "created_at": datetime.now().isoformat(),
    }
    try:
        os.makedirs(store_common.EXECUTION_LOG_ROOT, exist_ok=True)
        status_path = os.path.join(store_common.EXECUTION_LOG_ROOT, "run_status.json")
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        log_msg(f"[{store_label}] Saved run status -> {status_path}")
    except Exception as exc:
        log_msg(f"[{store_label}] Failed to write run_status.json: {exc}")

    log_msg("")
    log_msg("-" * 80)
    log_msg(
        f"[{store_label}] Batch finished. {total_success}/{len(urls)} URLs scraped "
        f"successfully, total products fetched: {total_products}"
    )

    if total_estimated_products > 0:
        log_msg(
            f"[{store_label}] Global products: {total_products}/"
            f"{total_estimated_products} (fetched/estimated from counters)"
        )

    if total_failed:
        log_msg(f"[{store_label}] Failed URLs ({len(total_failed)}):")
        for u in total_failed:
            log_msg(f"  - {u}")
    log_msg(
        f"[{store_label}] Total wall-clock time: "
        f"{format_elapsed_time(global_start)}"
    )
    log_msg("-" * 80)

    # Automatic DB ingest only if this run was successful
    status_success = (total_success == len(urls)) and (len(total_failed) == 0)

    if status_success:
        log_msg(f"[{store_label}] Run marked as SUCCESS, starting sendToDB.")
        send_store_to_db(
            logs_root=store_common.STORE_LOGS_ROOT,
            store_id_env_var=store_id_env_var,
            store_label=store_label,
            extract_external_id=extract_external_id,
            parse_price=parse_price,
            diff_query_prefix=diff_query_prefix,
            keep_last_runs=keep_last_runs,
        )
    else:
        log_msg(f"[{store_label}] Run FAILED, skipping sendToDB (DB not touched).")

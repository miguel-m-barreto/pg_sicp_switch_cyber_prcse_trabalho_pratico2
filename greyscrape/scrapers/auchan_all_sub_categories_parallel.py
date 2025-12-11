# greyscrape/scrapers/auchan_all_sub_categories_parallel.py

import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver

from auchan.auchan_extract_sub_categories import main as extract_subcats_main

from auchan_scraper import (
    _scrape_category_with_api_and_selenium,
    _detect_sub_category_from_url,
    _save_json_log,
    _extract_external_id,
    _parse_price,
)

import common.store_common as store_common
from common.store_common import (
    init_store_logging,
    format_elapsed_time,
    build_headless_chrome,
    log_msg,
)
from common.generic_parallel_runner import run_parallel_store

# Load .env.local a partir da raiz (Trabalho-Pratico2_SCRIPTS)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

LINKS_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "auchan",
    "links",
    "auchan_sub_categories.json",
)


def _load_sub_category_urls(path: str) -> List[str]:
    """
    Load category/subcategory URLs from JSON.

    Supports:
      - ["https://www.auchan.pt/pt/animais/...", ...]
      - [{"url": "...", "name": "..."}, ...]
      - {"urls": [...]} / {"categories": [...]} wrappers.
    """
    if not os.path.exists(path):
        log_msg(f"[Auchan] Links JSON not found: {path}")
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
        if "auchan.pt" not in url:
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
    Scrape a single Auchan category/subcategory URL using the low-level category scraper.
    """
    cat_info = _detect_sub_category_from_url(url)
    if not cat_info:
        log_msg(
            f"[SKIP] Could not detect category/subcategory from URL: {url}",
        )
        return None

    page_path, cgid = cat_info
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    log_msg(
        f">>> Starting scrape for URL='{url}' (page_path='{page_path}', cgid='{cgid}')",
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
        log_msg(f"[ERROR] Failed scraping '{url}': {exc}")
        return None

    total = len(produtos)
    final_cgid = stats.get("final_cgid", cgid)
    total_expected: Optional[int] = stats.get("total_expected")
    chunks = stats.get("chunks")

    context = f"sub_category:{page_path}|cgid={final_cgid}"
    _save_json_log(produtos, context)

    elapsed_str = format_elapsed_time(start_ts)

    if total_expected:
        log_msg(
            f"<<< Finished '{context}': {total}/{total_expected} products "
            f"in {elapsed_str} (chunks={chunks})",
        )
    else:
        log_msg(
            f"<<< Finished '{context}': {total} products "
            f"in {elapsed_str} (chunks={chunks})",
        )

    return context, total, total_expected


def main() -> None:
    run_parallel_store(
        argv=sys.argv,
        store_name="auchan",
        store_label="Auchan",
        links_path=LINKS_DEFAULT_PATH,
        links_extractor=extract_subcats_main,
        load_urls=_load_sub_category_urls,
        scrape_single_category=_scrape_single_category,
        store_id_env_var="SUPABASE_AUCHAN_STORE_ID",
        diff_query_prefix="auchan_diff",
        num_workers_env_var="AUCHAN_NUM_WORKERS",
        extract_external_id=_extract_external_id,
        parse_price=_parse_price,
        keep_last_runs=2,
    )


if __name__ == "__main__":
    main()

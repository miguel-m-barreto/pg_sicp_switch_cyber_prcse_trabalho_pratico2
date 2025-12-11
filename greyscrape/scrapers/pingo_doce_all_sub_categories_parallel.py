# greyscrape/scrapers/pingo_all_sub_categories_parallel.py

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
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
    format_elapsed_time,
    log_msg,
)
from common.generic_parallel_runner import run_parallel_store

# Load .env.local from project root (Trabalho-Pratico2_SCRIPTS)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

LINKS_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "pingo_doce",
    "links",
    "pingo_doce_sub_categories.json",
)


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
    """
    parsed = urlparse(url)
    host = parsed.netloc or ""
    if "pingodoce.pt" not in host:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 3:
        return None

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
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    store_root = os.path.join(base_dir, store_common.STORE_NAME)

    if store_common.LOG_DIR_NAME is None:
        exec_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = os.path.join(store_root, "logs", exec_ts, "json")
    else:
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
    Scrape a single Pingo Doce category/subcategory URL using the low-level category scraper.
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
        f">>> Starting scrape for URL='{url}' "
        f"(page_path='{page_path}', cgid='{cgid}')",
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
    total_expected = stats.get("total_expected")
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
        store_name="pingo_doce",
        store_label="Pingo Doce",
        links_path=LINKS_DEFAULT_PATH,
        links_extractor=extract_subcats_main,
        load_urls=_load_sub_category_urls,
        scrape_single_category=_scrape_single_category,
        store_id_env_var="SUPABASE_PINGO_STORE_ID",
        diff_query_prefix="pingo_diff",
        num_workers_env_var="PINGO_DOCE_NUM_WORKERS",
        extract_external_id=_extract_external_id,
        parse_price=_parse_price,
        keep_last_runs=2,
    )


if __name__ == "__main__":
    main()

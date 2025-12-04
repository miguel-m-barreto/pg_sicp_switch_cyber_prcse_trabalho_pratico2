# scraper_git/TESTE/scrape_auchan_all_categories.py

import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from auchan_DB import (
    _scrape_category_with_api_and_selenium,
    _detect_sub_category_from_url,
    _save_json_log,
)
from scraper_git.TESTE.auchan_helper import BASE_URL, format_elapsed_time


LINKS_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "links",
    "auchan_categories.json",
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


def _build_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver with the same options used in auchan_DB."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


def _scrape_single_category(
    driver: webdriver.Chrome,
    url: str,
) -> Optional[Tuple[str, int]]:
    """
    Scrape a single category/subcategory URL using the low-level category scraper.

    Returns:
      (context_string, num_products) on success,
      or None on failure (after logging the error).
    """
    cat_info = _detect_sub_category_from_url(url)
    if not cat_info:
        print(f"[Auchan][SKIP] Could not detect category/subcategory from URL: {url}")
        return None

    page_path, cgid = cat_info
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    print("")
    print(
        f"[Auchan] >>> Starting scrape for URL='{url}' "
        f"(page_path='{page_path}', cgid='{cgid}')"
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
        print(f"[Auchan][ERROR] Failed scraping '{url}': {exc}")
        return None

    total = len(produtos)
    context = f"sub_category:{page_path}"
    _save_json_log(produtos, context)

    print(
        f"[Auchan] <<< Finished '{context}': {total} products "
        f"in {format_elapsed_time(start_ts)}"
    )
    return context, total


def main() -> None:
    if len(sys.argv) > 1:
        links_path = sys.argv[1]
    else:
        links_path = LINKS_DEFAULT_PATH

    print(f"[Auchan] Reading category URLs from: {links_path}")
    urls = _load_sub_category_urls(links_path)
    print(f"[Auchan] Loaded {len(urls)} unique URLs")

    if not urls:
        print("[Auchan] No URLs to scrape. Exiting.")
        return

    driver = _build_driver()
    global_start = time.time()

    try:
        total_products = 0
        successful_cats = 0

        for idx, url in enumerate(urls, start=1):
            print("")
            print("=" * 80)
            print(f"[Auchan] [{idx}/{len(urls)}] {url}")
            print("=" * 80)

            result = _scrape_single_category(driver, url)
            if result is None:
                continue

            context, count = result
            total_products += count
            successful_cats += 1

        print("")
        print("-" * 80)
        print(
            f"[Auchan] Batch finished. {successful_cats}/{len(urls)} categories scraped "
            f"successfully, total products fetched: {total_products}"
        )
        print(f"[Auchan] Total wall-clock time: {format_elapsed_time(global_start)}")
        print("-" * 80)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

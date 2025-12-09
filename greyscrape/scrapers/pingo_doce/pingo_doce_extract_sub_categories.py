# greyscrape/scrapers/pingo_doce/pingo_doce_extract_sub_categories.py

import os
import json
from typing import List, Set

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.pingodoce.pt"
# Root where the global product menu vive (ajusta se for outra página)
START_URL = f"{BASE_URL}/home/produtos"
# We will save into: scrapers/pingo/links/pingo_sub_categories.json
LINK_DIR_NAME = "pingo/links"


def _build_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver with sane defaults."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


def _normalize_url(href: str) -> str:
    """Normalize Pingo Doce URLs to absolute, no query, no trailing slash."""
    if not href:
        return ""

    href = href.strip()

    # Relative → absolute
    if href.startswith("/"):
        href = BASE_URL + href

    # Only care about /home/produtos/ section
    if not href.startswith(f"{BASE_URL}/home/produtos"):
        return ""

    # Remove query strings and anchors
    href = href.split("?", 1)[0]
    href = href.split("#", 1)[0]

    # Remove trailing slash (except for base /home/produtos)
    base_root = f"{BASE_URL}/home/produtos"
    if href.endswith("/") and href != base_root and not href.endswith("?/"):
        href = href[:-1]

    return href


def _extract_subcategory_urls(html: str) -> List[str]:
    """
    From the Pingo Doce product root HTML, extract all subcategory URLs from
    the main menu.

    IMPORTANT:
      You MUST adjust the selector below to match the real menu elements.
      Start with DevTools and find the <a> tags for category links.

    Current heuristic:
      - any <a> with href starting with '/home/produtos/'
      - ignore links that look like product detail pages (e.g. containing '/p/')
    """
    soup = BeautifulSoup(html, "html.parser")
    urls: Set[str] = set()

    # TODO: tighten this selector once you inspect the DOM.
    for a in soup.select('a[href^="/home/produtos/"]'):
        raw = a.get("href") or ""
        # Skip product-detail links if they use '/p/' pattern, e.g. /.../p/544184
        if "/p/" in raw:
            continue

        href = _normalize_url(raw)
        if href:
            urls.add(href)

    return sorted(urls)


def _save_links(urls: List[str]) -> str:
    """Save extracted URLs as JSON into ./pingo/links/pingo_sub_categories.json."""
    # Base dir = greyscrape/scrapers
    base_dir = os.path.dirname(os.path.abspath(__file__))
    link_dir = os.path.join(base_dir, LINK_DIR_NAME)
    os.makedirs(link_dir, exist_ok=True)

    path = os.path.join(link_dir, "pingo_sub_categories.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)

    return path


def main() -> None:
    print(f"[Pingo][SubCats] Fetching menu from {START_URL}")
    driver = _build_driver()
    try:
        driver.get(START_URL)

        # Wait for menu links to appear in DOM.
        # Adjust CSS_SELECTOR once you know the correct class for the category links.
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    # TODO: refine selector for the left menu / main categories
                    (By.CSS_SELECTOR, 'a[href^="/home/produtos/"]')
                )
            )
        except Exception:
            print("[Pingo][SubCats] WARNING: No subcategory links found after waiting.")

        html = driver.page_source
        urls = _extract_subcategory_urls(html)

        path = _save_links(urls)
        print(f"[Pingo][SubCats] Saved {len(urls)} subcategory URLs -> {path}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

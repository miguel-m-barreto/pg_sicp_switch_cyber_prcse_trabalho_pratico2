# greyscrape/scrapers/auchan_extract_sub_categories.py
import os
import json
from typing import List, Set

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://www.auchan.pt"
START_URL = f"{BASE_URL}/pt"
LINK_DIR_NAME = "auchan/links"


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
    """Normalize Auchan URLs to absolute, no query, no trailing slash."""
    if not href:
        return ""

    href = href.strip()

    # Relative → absolute
    if href.startswith("/"):
        href = BASE_URL + href

    # We only care about /pt/ section
    if not href.startswith(f"{BASE_URL}/pt/"):
        return ""

    # Remove query strings and anchors
    href = href.split("?", 1)[0]
    href = href.split("#", 1)[0]

    # Remove trailing slash (except for /pt/)
    if href.endswith("/") and href != f"{BASE_URL}/pt/":
        href = href[:-1]

    return href


def _extract_subcategory_urls(html: str) -> List[str]:
    """
    From the Auchan homepage HTML, extract all SUBCATEGORY URLs
    from the main menu, based on IDs:

      - id="menu-subcategory-<something>"
    """
    soup = BeautifulSoup(html, "html.parser")
    urls: Set[str] = set()

    # Subcategories
    for a in soup.select('a[id^="menu-subcategory-"]'):
        href = _normalize_url(a.get("href"))
        if href:
            urls.add(href)

    return sorted(urls)


def _save_links(urls: List[str]) -> str:
    """Save extracted URLs as JSON into ./auchan/links/auchan_sub_categories.json."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    link_dir = os.path.join(base_dir, LINK_DIR_NAME)
    os.makedirs(link_dir, exist_ok=True)

    path = os.path.join(link_dir, "auchan_sub_categories.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)

    return path


def main() -> None:
    print(f"[Auchan][SubCats] Fetching menu from {START_URL}")
    driver = _build_driver()
    try:
        driver.get(START_URL)
        # Small wait to ensure the menu is rendered
        # Wait until subcategory menu links exist in DOM
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'a[id^="menu-subcategory-"]')
                )
            )
        except Exception:
            print("[Auchan][SubCats] WARNING: No subcategory links found after waiting.")


        html = driver.page_source
        urls = _extract_subcategory_urls(html)

        path = _save_links(urls)
        print(
            f"[Auchan][SubCats] Saved {len(urls)} subcategory URLs -> {path}"
        )
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

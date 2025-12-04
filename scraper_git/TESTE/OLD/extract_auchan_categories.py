# scraper_git/TESTE/extract_auchan_categories.py
import os
import json
from typing import List, Set

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_URL = "https://www.auchan.pt"
START_URL = f"{BASE_URL}/pt"
LINK_DIR_NAME = "links"


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

    # Ignore lixo que não é da área /pt/
    if not href.startswith(f"{BASE_URL}/pt/"):
        return ""

    # Tirar query strings e anchors
    href = href.split("?", 1)[0]
    href = href.split("#", 1)[0]

    # Tirar trailing slash (excepto o /pt/)
    if href.endswith("/") and href != f"{BASE_URL}/pt/":
        href = href[:-1]

    return href


def _extract_menu_urls(html: str) -> List[str]:
    """
    From the Auchan homepage HTML, extract all category and subcategory URLs
    from the main menu, based on IDs:

      - id="menu-category-<something>"
      - id="menu-subcategory-<something>"
    """
    soup = BeautifulSoup(html, "html.parser")
    urls: Set[str] = set()

    # Top-level categories
    for a in soup.select('a[id^="menu-category-"]'):
        href = _normalize_url(a.get("href"))
        if href:
            urls.add(href)

    # Caso haja mais anchors relevantes no futuro, é aqui que se podem adicionar.

    return sorted(urls)


def _save_links(urls: List[str]) -> str:
    """Save extracted URLs as JSON into ./links/auchan_categories.json."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    link_dir = os.path.join(base_dir, LINK_DIR_NAME)
    os.makedirs(link_dir, exist_ok=True)

    path = os.path.join(link_dir, "auchan_categories.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)

    return path


def main() -> None:
    print(f"[Auchan] Fetching menu from {START_URL}")
    driver = _build_driver()
    try:
        driver.get(START_URL)
        # Pequena pausa se for preciso; o menu normalmente vem já no HTML,
        # mas o headless às vezes precisa de um tick.
        driver.implicitly_wait(3)

        html = driver.page_source
        urls = _extract_menu_urls(html)

        path = _save_links(urls)
        print(f"[Auchan] Saved {len(urls)} category/subcategory URLs -> {path}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

# greyscrape/scrapers/pingo_doce/pingo_doce_extract_sub_categories.py

import os
import json
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.pingodoce.pt"
START_URL = f"{BASE_URL}/home/produtos"
LINK_DIR_NAME = "links"

IGNORE_EXACT = {
    "https://www.pingodoce.pt/home/produtos",
    "https://www.pingodoce.pt/home/produtos/promocoes/poupe-esta-semana",
}

IGNORE_PREFIX_PATHS = (
)

def _build_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def _abs_url(href: str) -> str:
    """Return absolute URL (or empty)."""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/"):
        href = BASE_URL + href
    if not href.startswith(BASE_URL):
        return ""
    # Drop fragments only. Keep query because cgid lives there.
    href = href.split("#", 1)[0]
    # Normalize trailing slash (but keep root paths sane)
    if href.endswith("/") and len(href) > len(BASE_URL) + 1:
        href = href[:-1]
    return href

def _should_ignore_url(url: str) -> bool:
    if not url:
        return True

    if url in IGNORE_EXACT:
        return True

    try:
        path = urlparse(url).path or ""
    except Exception:
        return False

    return any(path.startswith(prefix) for prefix in IGNORE_PREFIX_PATHS)


def _extract_cgid(url: str) -> Optional[str]:
    """Extract cgid=... if present."""
    try:
        qs = parse_qs(urlparse(url).query)
        cgid = (qs.get("cgid") or [None])[0]
        return cgid
    except Exception:
        return None


def _category_type(url: str) -> str:
    """Classify category URL."""
    cgid = _extract_cgid(url)
    if cgid:
        return "search"
    if "/home/produtos" in url:
        return "seo"
    return "other"


def _extract_leaf_categories(html: str) -> List[Dict]:
    """
    Extract ONLY leaf categories (final subcategories) from the menu.
    Leaf = <li> that contains an <a> but does NOT contain a nested <ul> with children.
    Keeps both SEO and Search-Show links, but prefers Search-Show when present.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict] = []
    seen: set[str] = set()

    # Leaf candidates are typically these <li> items
    leaf_lis = soup.select("li.nav-item.sub-category, li.nav-item")

    for li in leaf_lis:
        # If this <li> has a nested <ul>, it has children => not a leaf
        if li.select_one("ul"):
            continue

        a = li.select_one("a[href]")
        if not a:
            continue

        url = _abs_url(a.get("href") or "")
        if not url:
            continue

        if _should_ignore_url(url):
            continue


        # Ignore product pages
        if "/p/" in url or url.endswith(".html"):
            continue

        ctype = _category_type(url)
        if ctype == "other":
            continue

        cat_id = (a.get("id") or "").strip() or None
        name = " ".join(a.get_text(" ", strip=True).split())

        cgid = _extract_cgid(url)

        # Dedup: prefer cgid-based key when available
        key = f"cgid:{cgid}" if cgid else f"url:{url}"
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "id": cat_id,
                "name": name,
                "url": url,
                "type": ctype,  # "search" | "seo"
                "cgid": cgid,
            }
        )

    return out



def _extract_menu_categories(html: str) -> List[Dict]:
    """
    Extract categories from the left menu.
    Keeps BOTH SEO and Demandware Search-Show links.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict] = []
    seen: set[str] = set()

    # Menu anchors are basically these:
    # - main category: a.menu-item-event-click
    # - sub category:  a.nav-link.sub-category
    # - sub-category container: a.sub-category-container
    anchors = soup.select(
        "a.menu-item-event-click, a.nav-link.sub-category, a.sub-category-container"
    )

    for a in anchors:
        raw_href = a.get("href") or ""
        url = _abs_url(raw_href)
        if not url:
            continue

        if _should_ignore_url(url):
            continue


        # Ignore product pages if any slip through
        if "/p/" in url or url.endswith(".html"):
            continue

        ctype = _category_type(url)
        if ctype == "other":
            continue

        cat_id = (a.get("id") or "").strip() or None
        name = " ".join(a.get_text(" ", strip=True).split())

        # Dedup key: prefer cgid when present, otherwise URL
        cgid = _extract_cgid(url)
        key = f"cgid:{cgid}" if cgid else f"url:{url}"
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "id": cat_id,
                "name": name,
                "url": url,
                "type": ctype,   # "search" | "seo"
                "cgid": cgid,    # present when type == "search"
            }
        )

    return out


def _save_links(items: List[Dict]) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    link_dir = os.path.join(base_dir, LINK_DIR_NAME)
    os.makedirs(link_dir, exist_ok=True)
    path = os.path.join(link_dir, "pingo_doce_sub_categories.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return path


def main() -> None:
    print(f"[Pingo_Doce][MenuCats] Fetching menu from {START_URL}")
    driver = _build_driver()
    try:
        driver.get(START_URL)

        # Wait for the menu to exist (not only /home/produtos links).
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a.menu-item-event-click, a.nav-link.sub-category")
            )
        )
        time.sleep(2)

        html = driver.page_source
        items = _extract_leaf_categories(html)

        # Basic sanity output
        n_search = sum(1 for x in items if x["type"] == "search")
        n_seo = sum(1 for x in items if x["type"] == "seo")
        print(f"[Pingo_Doce][MenuCats] Extracted: {len(items)} (search={n_search}, seo={n_seo})")

        path = _save_links(items)
        print(f"[Pingo_Doce][MenuCats] Saved to: {path}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

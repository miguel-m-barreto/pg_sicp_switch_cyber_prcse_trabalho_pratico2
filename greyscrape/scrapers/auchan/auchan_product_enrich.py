# greyscrape/scrapers/auchan/auchan_product_enrich.py
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from common.store_common import log_msg, log_debug, log_warn

# Load .env.local from project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local")

# Feature flag for product-page enrichment
ENABLE_PRODUCT_ENRICH = os.getenv("AUCHAN_PRODUCT_ENRICH", "0") == "1"

_raw_max = (os.getenv("AUCHAN_PRODUCT_ENRICH_MAX_PER_CAT", "") or "").strip().lower()
if _raw_max in ("", "0", "-1", "none", "null"):
    PRODUCT_ENRICH_MAX_PER_CAT: Optional[int] = None  # unlimited
else:
    try:
        PRODUCT_ENRICH_MAX_PER_CAT = int(_raw_max)
    except ValueError:
        PRODUCT_ENRICH_MAX_PER_CAT = None

# Base wait after loading each product page
WAIT_PRODUCT_PAGE = float(os.getenv("AUCHAN_PRODUCT_WAIT", "0.8"))


def _parse_product_page_html(html: str, debug: bool = False) -> Dict[str, Any]:
    """
    Parse a single product page HTML and extract extra fields.

    NOTE:
        Selectors are best-effort and should be tuned against real Auchan HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, Any] = {}

    # Long description
    desc = (
        soup.select_one(".b-product-info__description")
        or soup.select_one("[itemprop='description']")
        or soup.select_one(".product-description")
    )
    if desc:
        text = " ".join(desc.get_text(" ", strip=True).split())
        if text:
            out["detail_long_description"] = text

    # Ingredients: look for a block that contains the word "Ingredientes"
    ing_label = soup.find(string=lambda s: isinstance(s, str) and "Ingredientes" in s)
    if ing_label:
        # Try to grab a reasonable container around that label
        container = ing_label.parent
        # Climb a bit if the parent is very small (just a <strong> or <span>)
        for _ in range(3):
            if container and len(container.get_text(strip=True)) < 40:
                container = container.parent
        if container:
            text = " ".join(container.get_text(" ", strip=True).split())
            if text:
                out["detail_ingredients_raw"] = text

    # Nutrition table: look for something with "Informação nutricional"
    nutri_label = soup.find(
        string=lambda s: isinstance(s, str) and "Informação nutricional" in s
    )
    if nutri_label:
        # Try to find a table or container near that label
        container = nutri_label.parent
        table = None
        if container:
            table = container.find("table")
        if not table and container:
            table = container.find_next("table")
        if table:
            # Store raw HTML so we can parse it later if needed
            out["detail_nutrition_table_html"] = str(table)

    if debug:
        log_debug(
            f"[Auchan][ProdEnrich][DEBUG] Parsed product page -> keys={list(out.keys())}"
        )

    return out


def enrich_products_with_product_pages(
    driver: Any,
    products: List[Dict[str, Any]],
    worker_id: Optional[int] = None,
    max_per_category: Optional[int] = None,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """
    Enrich products by visiting each product page and scraping extra info.

    Args:
        driver: Selenium WebDriver (already created in the worker).
        products: list of product dicts from category scraping.
        worker_id: optional worker id for logging.
        max_per_category: optional hard limit per category; if None uses env.
        debug: extra debug logs.

    Returns:
        Same list of products with extra keys:
            - detail_long_description
            - detail_ingredients_raw
            - detail_nutrition_table_html
    """
    if not ENABLE_PRODUCT_ENRICH:
        log_msg(
            "[Auchan][ProdEnrich] Product-page enrichment disabled "
            "(AUCHAN_PRODUCT_ENRICH != '1').",
            worker_id=worker_id,
        )
        return products

    if driver is None:
        log_warn(
            "[Auchan][ProdEnrich] Driver is None, cannot enrich product pages.",
            worker_id=worker_id,
        )
        return products

    # Decide effective max per category
    if max_per_category is None:
        effective_max = PRODUCT_ENRICH_MAX_PER_CAT
    else:
        if max_per_category <= 0:
            effective_max = None
        else:
            effective_max = max_per_category

    effective_debug = debug

    # Pick candidates with a valid product link
    candidates: List[Dict[str, Any]] = []
    for p in products:
        link = p.get("link")
        if isinstance(link, str) and "/pt/" in link:
            candidates.append(p)

    enriched_count = 0
    attempted = 0

    log_msg(
        f"[Auchan][ProdEnrich] Starting product-page enrichment "
        f"(candidates={len(candidates)}, max_per_category={effective_max})",
        worker_id=worker_id,
    )

    for p in candidates:
        if effective_max is not None and enriched_count >= effective_max:
            break

        link = p.get("link")
        if not link:
            continue

        attempted += 1

        try:
            driver.get(link)
            time.sleep(WAIT_PRODUCT_PAGE)
            html = driver.page_source
        except Exception as exc:
            log_warn(
                f"[Auchan][ProdEnrich] Failed to load product page '{link}': {exc}",
                worker_id=worker_id,
            )
            continue

        extra = _parse_product_page_html(html, debug=effective_debug)
        if not extra:
            if effective_debug:
                log_debug(
                    f"[Auchan][ProdEnrich][DEBUG] No extra data parsed for '{link}'",
                    worker_id=worker_id,
                )
            continue

        # Attach keys directly onto product dict (flat)
        for k, v in extra.items():
            # Do not overwrite if already present
            if k not in p and v is not None:
                p[k] = v

        enriched_count += 1

    log_msg(
        f"[Auchan][ProdEnrich] Enriched {enriched_count} products "
        f"(attempted={attempted}, total={len(products)}, "
        f"max_per_category={effective_max})",
        worker_id=worker_id,
    )

    return products

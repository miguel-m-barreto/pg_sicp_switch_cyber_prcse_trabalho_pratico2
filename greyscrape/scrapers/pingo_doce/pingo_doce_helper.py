import json
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load .env.local
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env.local")

BASE_URL = os.getenv("PINGO_DOCE_BASE_URL", "https://www.pingodoce.pt")


def extract_products_from_html(html: str, run_timestamp: str) -> List[Dict]:
    """
    Parse Pingo Doce HTML using the V2 architecture (GTM data priority).

    Target: data-gtm-info on div.product-tile-pd
    Structure:
      {
        "currency": "EUR",
        "value": 6.69,
        "items": [
          {
            "item_id": "...",
            "item_name": "...",
            ...
          }
        ]
      }
    """
    soup = BeautifulSoup(html, "html.parser")
    products: List[Dict] = []

    # Specific selector for Pingo Doce tiles
    for container in soup.select("div.product-tile-pd[data-pid]"):

        # ================================================================
        # Core GTM JSON data
        # ================================================================
        gtm_raw = container.get("data-gtm-info")
        gtm_item: Dict = {}
        gtm_root: Dict = {}

        if gtm_raw:
            try:
                # Pingo uses &quot; inside the attribute, replace before JSON load
                cleaned_json = gtm_raw.replace("&quot;", '"')
                gtm_root = json.loads(cleaned_json)

                # Product info is inside an 'items' list
                items = gtm_root.get("items")
                if isinstance(items, list) and items:
                    gtm_item = items[0]
            except Exception:
                gtm_item = {}

        # ================================================================
        # Identifiers & Categories
        # ================================================================
        product_id = gtm_item.get("item_id") or container.get("data-pid")
        brand = gtm_item.get("item_brand") or ""

        # Robust product name: GTM -> text link -> image alt
        name = gtm_item.get("item_name")

        if not name:
            name_tag_for_name = container.select_one("div.product-name-link a")
            if name_tag_for_name:
                name = name_tag_for_name.get_text(strip=True)

        if not name:
            img_tag_for_name = container.select_one("img.product-tile-component-image")
            if img_tag_for_name:
                name = (img_tag_for_name.get("alt") or "").strip()

        name = name or ""

        # Categories from GTM
        category_human_1 = gtm_item.get("item_category")
        category_human_2 = gtm_item.get("item_category2")
        category_human_3 = gtm_item.get("item_category3")
        category_human_4 = gtm_item.get("item_category4")

        # Category slug path is not directly exposed in Pingo GTM
        category_slug_path = None

        # ================================================================
        # Links & Images
        # ================================================================
        name_tag = container.select_one("div.product-name-link a")
        pdp_url_relative = name_tag.get("href") if name_tag else ""

        link = ""
        if pdp_url_relative:
            if pdp_url_relative.startswith("http"):
                link = pdp_url_relative
            else:
                link = BASE_URL + pdp_url_relative

        img_tag = container.select_one("img.product-tile-component-image")
        image_url = img_tag.get("src") if img_tag else None
        image_alt = img_tag.get("alt") if img_tag else None
        image_title = img_tag.get("title") if img_tag else None

        # ================================================================
        # Prices & Quantities
        # ================================================================
        # Numeric GTM price (usually final price or price per unit weight)
        gtm_price = gtm_item.get("price")
        if gtm_price is None:
            # Some implementations expose value at root level
            gtm_price = gtm_root.get("value")

        try:
            gtm_price = float(gtm_price) if gtm_price is not None else None
        except Exception:
            gtm_price = None

        gtm_discount = gtm_item.get("discount")
        try:
            gtm_discount = float(gtm_discount) if gtm_discount is not None else 0.0
        except Exception:
            gtm_discount = 0.0

        # Raw price strings for display/debug
        current_price_tag = container.select_one(".product-price .sales .value")
        current_price_raw: Optional[str] = None
        if current_price_tag:
            current_price_raw = (
                current_price_tag.get_text(strip=True)
                or current_price_tag.get("content")
            )
            if current_price_raw:
                # Keep a normalized "X.XX €" style string
                current_price_raw = current_price_raw.strip() + " €"

        old_price_tag = container.select_one(".product-price .strike-through .value")
        old_price_raw: Optional[str] = None
        if old_price_tag:
            old_price_raw = (
                old_price_tag.get_text(strip=True)
                or old_price_tag.get("content")
            )
            if old_price_raw:
                old_price_raw = old_price_raw.strip() + " €"

        # Unit price string (e.g. "0.6 Kg | 10,73 €/Kg")
        unit_div = container.select_one("div.product-unit")
        unit_price_raw: Optional[str] = None
        unit_suffix: Optional[str] = None
        min_quantity_raw: Optional[str] = None

        if unit_div:
            full_text = unit_div.get_text(strip=True)
            if "|" in full_text:
                parts = full_text.split("|")
                min_quantity_raw = parts[0].strip()  # "0.6 Kg"
                unit_price_raw = parts[1].strip()    # "10,73 €/Kg"

                # Try to extract a unit suffix such as Kg, L, Un from the unit price
                m_suffix = re.search(r"€/\s*([A-Za-z]+)", unit_price_raw)
                if m_suffix:
                    unit_suffix = m_suffix.group(1)
            else:
                # Only quantity present (e.g. "0.6 Kg" or "24 Un")
                min_quantity_raw = full_text

        # Fallback: data attributes on CTA (e.g. data-display-quantity="0.6", unit="Kg")
        cta_div = container.select_one("div.product-cta")
        if not min_quantity_raw and cta_div:
            qty = cta_div.get("data-display-quantity")
            unit = cta_div.get("data-display-unit")
            if qty and unit:
                min_quantity_raw = f"{qty} {unit}"
                if not unit_suffix:
                    unit_suffix = unit

        # If we still do not have a unit_suffix, try to infer from quantity string
        if not unit_suffix and min_quantity_raw:
            m_q = re.search(r"[0-9.,]+\s*([A-Za-z]+)", min_quantity_raw)
            if m_q:
                unit_suffix = m_q.group(1)

        # ================================================================
        # Promotions & Labels
        # ================================================================
        promo_badge = container.select_one("img.product-tile-promo-label")
        discount_badge_raw = promo_badge.get("title") if promo_badge else None

        promo_text_tag = container.select_one("span.promo-message")
        promotion_raw = promo_text_tag.get_text(strip=True) if promo_text_tag else None

        is_on_promotion = bool(
            discount_badge_raw or promotion_raw or (gtm_discount and gtm_discount > 0)
        )

        # No explicit Bio/National flags in tiles (would require extra heuristics)
        is_bio = False
        is_national = False

        # ================================================================
        # Ratings (Bazaarvoice)
        # ================================================================
        rating_div = container.select_one(".rating_summary")
        rating_pid = rating_div.get("data-bv-product-id") if rating_div else None

        # ================================================================
        # Final Dict (aligned with Auchan structure)
        # ================================================================
        products.append(
            {
                "name": name,
                "link": link,
                "min_quantity": min_quantity_raw,
                "unit_price_raw": unit_price_raw,
                "current_price_raw": current_price_raw,
                "old_price_raw": old_price_raw,
                "promotion_raw": promotion_raw,
                "timestamp": run_timestamp,

                # Core metadata
                "product_id": product_id,
                "brand": brand,
                "product_type": "standard",
                "category_slug_path": category_slug_path,
                "category_human_1": category_human_1,
                "category_human_2": category_human_2,
                "category_human_3": category_human_3,
                "category_human_4": category_human_4,

                # Image
                "image_url": image_url,
                "image_alt": image_alt,
                "image_title": image_title,

                # Numeric GTM fields
                "original_price": gtm_price,
                "discount_value": gtm_discount,
                "final_price": gtm_price,  # GTM value is usually the final price
                "gtm_quantity": gtm_item.get("quantity"),
                "unit_suffix": unit_suffix,

                # Status flags
                "is_on_promotion": is_on_promotion,
                "discount_badge_raw": discount_badge_raw,
                "stock_status": "in_stock",  # Pingo usually hides out-of-stock items
                "is_bio": is_bio,
                "is_national_product": is_national,
                "is_refrigerated": False,

                # Ratings
                "rating_product_id": rating_pid,
                "rating_url": None,

                # UI URLs
                "pdp_url_absolute": link,
                "pdp_url_relative": pdp_url_relative,

                # Raw labels list for future enrichment
                "labels_raw": [],
            }
        )

    return products


def parse_total_results(html: str) -> Optional[int]:
    """
    Parse result counters like: "1 - 24 de 312 produtos".
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try multiple possible selectors for the counter
    counter = soup.select_one(".search-results-count") or soup.select_one(
        ".results-count"
    )

    if not counter:
        return None

    text = counter.get_text(strip=True)
    m = re.search(r"de\s+(\d+)", text)  # "de 312"
    if not m:
        return None

    try:
        return int(m.group(1))
    except Exception:
        return None

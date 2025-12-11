# greyscrape/scrapers/auchan/auchan_helper.py

import json
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load .env.local from project root (Trabalho-Pratico2_SCRIPTS)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env.local")

BASE_URL = os.getenv("AUCHAN_BASE_URL", "https://www.auchan.pt")

def extract_products_from_html(html: str, run_timestamp: str) -> List[Dict]:
    """
    Parse an Auchan HTML page/fragment and extract product data.

    This extracts:
      - core product metadata (id, name, brand, categories, prices)
      - UI-related metadata (image, PDP URLs, quick-view, labels, ratings)
      - promotion and availability information
      - GTM structured data
    """

    soup = BeautifulSoup(html, "html.parser")
    products: List[Dict] = []

    for container in soup.select("div.product-tile.auc-product-tile"):

        # ================================================================
        # Core JSON metadata: data-gtm, data-gtm-new, data-urls
        # ================================================================
        gtm_raw = container.get("data-gtm")
        gtm: Dict = {}
        if gtm_raw:
            try:
                gtm = json.loads(gtm_raw)
            except json.JSONDecodeError:
                gtm = {}

        gtm_new_raw = container.get("data-gtm-new")
        gtm_new: Dict = {}
        if gtm_new_raw:
            try:
                gtm_new = json.loads(gtm_new_raw)
            except json.JSONDecodeError:
                gtm_new = {}

        urls_raw = container.get("data-urls")
        urls: Dict = {}
        if urls_raw:
            try:
                urls = json.loads(urls_raw)
            except json.JSONDecodeError:
                urls = {}

        # ================================================================
        # Identifiers, brand and categories
        # ================================================================
        product_id = (
            container.get("data-pid")
            or gtm_new.get("item_id")
            or gtm.get("id")
        )

        brand = gtm_new.get("item_brand") or gtm.get("brand")

        category_slug_path = gtm.get("category") or None

        category_human_1 = gtm_new.get("item_category")
        category_human_2 = gtm_new.get("item_category2")
        category_human_3 = gtm_new.get("item_category3")
        category_human_4 = gtm_new.get("item_category4")

        product_type = container.get("data-producttype") or None

        # Listing positions
        gtm_position = gtm.get("position") or container.get("data-position")
        try:
            if isinstance(gtm_position, str) and gtm_position.strip().isdigit():
                gtm_position = int(gtm_position.strip())
        except Exception:
            gtm_position = None

        list_index = gtm_new.get("index")
        try:
            if isinstance(list_index, str) and list_index.strip().isdigit():
                list_index = int(list_index.strip())
        except Exception:
            try:
                list_index = int(list_index)
            except Exception:
                list_index = None

        # ================================================================
        # PDP URLs and UI action URLs
        # ================================================================
        pdp_url_relative = urls.get("productUrl")
        pdp_url_absolute = urls.get("absoluteProductUrl")
        encoded_product_url = urls.get("encodedProductUrl")

        title_tag = container.select_one("div.auc-product-tile__name a")
        if pdp_url_absolute:
            link = pdp_url_absolute
        elif title_tag and title_tag.has_attr("href"):
            href = title_tag["href"]
            link = href if href.startswith("http") else BASE_URL + href
        elif pdp_url_relative:
            link = BASE_URL + pdp_url_relative
        else:
            link = ""

        quick_view_url = urls.get("quickViewUrl")
        add_to_cart_url = urls.get("addToCartUrl")
        update_quantity_url = urls.get("updateQuantityUrl")
        remove_from_cart_url = urls.get("removeFromCartUrl")
        quantity_selector_url = urls.get("quantitySelector")
        oney_simulator_url = urls.get("oneySimulatorUrl")

        # ================================================================
        # Product name
        # ================================================================
        name = (
            title_tag.get_text(strip=True)
            if title_tag
            else gtm_new.get("item_name") or gtm.get("name") or ""
        )

        # ================================================================
        # Image information
        # ================================================================
        img_tag = container.select_one("div.image-container img")
        image_url = None
        image_alt = None
        image_title = None

        if img_tag:
            src = img_tag.get("src", "").strip()
            data_src = img_tag.get("data-src", "").strip()

            image_url = data_src or src or None
            if image_url and image_url.startswith("/"):
                image_url = BASE_URL + image_url

            image_alt = img_tag.get("alt")
            image_title = img_tag.get("title")

        # ================================================================
        # Measures (unit price, minimum quantity, suffix)
        # ================================================================
        min_qty_tag = container.select_one("span.auc-measures--avg-weight")
        min_quantity = min_qty_tag.get_text(strip=True) if min_qty_tag else None

        unit_price_tag = container.select_one("span.auc-measures--price-per-unit")
        unit_price_raw = (
            unit_price_tag.get_text(strip=True) if unit_price_tag else None
        )

        unit_suffix_tag = container.select_one("span.auc-avgWeight")
        unit_suffix = unit_suffix_tag.get_text(strip=True) if unit_suffix_tag else None

        # ================================================================
        # Price fields (DOM + structured GTM numeric)
        # ================================================================
        price_tag = container.select_one("div.price span.sales span.value")
        if price_tag:
            text = price_tag.get_text(strip=True)
            current_price_raw = text or price_tag.get("content")
        else:
            current_price_raw = None

        old_price_tag = container.select_one("span.strike-through.value")
        if old_price_tag:
            text = old_price_tag.get_text(strip=True)
            old_price_raw = text or old_price_tag.get("content")
        else:
            old_price_raw = None

        # GTM numeric prices
        gtm_price = gtm_new.get("price")
        try:
            gtm_price = float(gtm_price) if gtm_price is not None else None
        except Exception:
            gtm_price = None

        gtm_discount_value = gtm_new.get("discount")
        try:
            gtm_discount_value = (
                float(gtm_discount_value) if gtm_discount_value is not None else None
            )
        except Exception:
            gtm_discount_value = None

        gtm_quantity = gtm_new.get("quantity")
        try:
            gtm_quantity = float(gtm_quantity) if gtm_quantity is not None else None
        except Exception:
            gtm_quantity = None

        # Compute the numeric final price only if values exist
        if gtm_price is not None and gtm_discount_value is not None:
            price_now_numeric = gtm_price - gtm_discount_value
        else:
            price_now_numeric = None

        # ================================================================
        # Promotions and promo flags
        # ================================================================
        promo = None

        discount_badge_tag = container.select_one(".auc-promo--discount--red")
        discount_badge_raw = (
            discount_badge_tag.get_text(strip=True) if discount_badge_tag else None
        )
        if discount_badge_raw:
            promo = discount_badge_raw

        if not promo:
            promo_tag = container.select_one(".auc-price__promotion__label")
            if promo_tag:
                promo = promo_tag.get_text(strip=True)

        if not promo:
            promo_tag_old = container.select_one(
                "div.auc-promo--comarch__label--text"
            )
            if promo_tag_old:
                promo = promo_tag_old.get_text(strip=True)

        is_on_promotion = bool(
            promo
            or discount_badge_raw
            or (gtm_discount_value is not None and gtm_discount_value > 0)
        )

        # ================================================================
        # Labels (badges: bio, national, refrigerated, etc.)
        # ================================================================
        labels_raw = []
        is_national_product = False
        is_bio = False
        is_refrigerated = False

        labels_container = container.select_one("div.auc-product-labels")
        if labels_container:
            for img in labels_container.select("img"):
                src = (img.get("src") or img.get("data-src") or "").strip()
                alt = img.get("alt") or ""
                title = img.get("title") or ""

                filename = src.rsplit("/", 1)[-1] if src else ""
                code = filename.split(".", 1)[0] if filename else None

                labels_raw.append({
                    "code": code,
                    "src": src or None,
                    "alt": alt or None,
                    "title": title or None,
                })

                lt = (alt + " " + title).lower()
                if "nacional" in lt:
                    is_national_product = True
                if "bio" in lt or "biológico" in lt:
                    is_bio = True
                if "refrigerado" in lt:
                    is_refrigerated = True

        # ================================================================
        # Ratings (Bazaarvoice)
        # ================================================================
        ratings_div = container.select_one(
            "div.auc-product-tile__bazaarvoice--ratings"
        )
        rating_product_id = (
            ratings_div.get("data-bv-product-id") if ratings_div else None
        )
        rating_url = (
            ratings_div.get("data-bv-redirect-url") if ratings_div else None
        )

        # ================================================================
        # Availability flags
        # ================================================================
        limited_modal = container.get("data-shown-limited-availability-modal")
        if limited_modal is not None:
            limited_modal = str(limited_modal).lower() == "true"

        delay_modal = container.get("data-shown-delay-delivery-modal")
        if delay_modal is not None:
            delay_modal = str(delay_modal).lower() == "true"

        # ================================================================
        # Final unified product dictionary
        # ================================================================
        products.append({
            "name": name,
            "link": link,
            "min_quantity": min_quantity,
            "unit_price_raw": unit_price_raw,
            "current_price_raw": current_price_raw,
            "old_price_raw": old_price_raw,
            "promotion_raw": promo,
            "timestamp": run_timestamp,

            # Core metadata
            "product_id": product_id,
            "brand": brand,
            "product_type": product_type,
            "category_slug_path": category_slug_path,
            "category_human_1": category_human_1,
            "category_human_2": category_human_2,
            "category_human_3": category_human_3,
            "category_human_4": category_human_4,

            # Image
            "image_url": image_url,
            "image_alt": image_alt,
            "image_title": image_title,

            # Numeric price structure
            "original_price": gtm_price,
            "discount_value": gtm_discount_value,
            "final_price": price_now_numeric,
            "gtm_quantity": gtm_quantity,
            "unit_suffix": unit_suffix,

            # Listing metadata
            "gtm_web_position": gtm_position,
            "gtm_list_index": list_index,

            # Promotion
            "discount_badge_raw": discount_badge_raw,
            "is_on_promotion": is_on_promotion,

            # Labels
            "labels_raw": labels_raw,
            "is_national_product": is_national_product,
            "is_bio": is_bio,
            "is_refrigerated": is_refrigerated,

            # Ratings
            "rating_product_id": rating_product_id,
            "rating_url": rating_url,

            # Availability
            "limited_availability_flag": limited_modal,
            "delay_delivery_flag": delay_modal,

            # UI URLs
            "pdp_url_relative": pdp_url_relative,
            "pdp_url_absolute": pdp_url_absolute,
            "encoded_product_url": encoded_product_url,
            "quick_view_url": quick_view_url,
            "add_to_cart_url": add_to_cart_url,
            "update_quantity_url": update_quantity_url,
            "remove_from_cart_url": remove_from_cart_url,
            "quantity_selector_url": quantity_selector_url,
            "oney_simulator_url": oney_simulator_url,
        })

    return products


def parse_total_results(html: str) -> Optional[int]:
    """
    Parse something like:
      <div class="auc-search-results auc-js-search-results-count" data-type="3">
        1 - 48 de 1181 resultados
      </div>
    and return 1181.
    """
    soup = BeautifulSoup(html, "html.parser")
    counter_div = soup.select_one(
        "div.auc-search-results.auc-js-search-results-count"
    )
    if not counter_div:
        return None

    text = counter_div.get_text(strip=True)
    m = re.search(r"de\s+(\d+)\s+resultados", text)
    if not m:
        return None

    try:
        return int(m.group(1))
    except ValueError:
        return None

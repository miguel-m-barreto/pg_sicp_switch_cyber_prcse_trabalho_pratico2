# greyscrape/scrapers/pingo_doce/pingo_doce_helper.py

import json
import os
import re
from typing import List, Dict, Optional
from pathlib import Path
import html as html_lib

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from common.unit_normalize import normalize_unit_suffix

# Load .env.local
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env.local")

BASE_URL = os.getenv("PINGO_DOCE_BASE_URL", "https://www.pingodoce.pt")

NON_PROMO_BADGES = {
            "apenas",
            "novidade",
            "exclusivo",
            "exclusivo online",
}


def _normalize_discount_badge(badge_text: Optional[str]) -> Optional[str]:
    if not badge_text:
        return None

    s = badge_text.strip()

    # If it's already like "-25%" or " -25% " normalize it
    m = re.search(r"(-?\s*\d+)\s*%", s)
    if m:
        n = m.group(1).replace(" ", "")
        n = n.lstrip("-")  # avoid "--25%"
        return f"-{n}%"

    # Handle "Poupe mais de 25%"
    m = re.search(r"(\d+)\s*%", s)
    if m:
        n = m.group(1)
        return f"-{n}%"

    return s or None


def _discount_percent_from_prices(old_price: Optional[float], cur_price: Optional[float]) -> Optional[str]:
    if old_price is None or cur_price is None:
        return None
    if old_price <= 0 or cur_price >= old_price:
        return None

    pct = int(round((old_price - cur_price) / old_price * 100))
    if pct <= 0:
        return None
    return f"-{pct}%"


def _parse_price_any(text: Optional[str]) -> Optional[float]:
    """
    Parse a price string like:
      - "12,99 €"
      - "12.99"
      - "1.234,56 €"
    into a float.
    """
    if not text:
        return None

    s = text.replace("€", "").replace("EUR", "")
    s = s.replace("\xa0", " ").strip()
    # Keep only digits, comma and dot
    s = re.sub(r"[^0-9,\.]", "", s)
    if not s:
        return None

    has_comma = "," in s
    has_dot = "." in s

    # European formats
    if has_comma and has_dot:
        # e.g. "1.234,56" -> "1234.56"
        s = s.replace(".", "").replace(",", ".")
    elif has_comma:
        # e.g. "1234,56" -> "1234.56"
        s = s.replace(".", "").replace(",", ".")
    # else: "." is decimal or no separator

    try:
        return float(s)
    except ValueError:
        return None



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
                cleaned_json = html_lib.unescape(gtm_raw)
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
        # Prices & Quantities (HTML-driven, GTM only as fallback)
        # ================================================================
        price_box = container.select_one(".product-price")

        current_price_tag = None
        old_price_tag = None
        if price_box:
            current_price_tag = price_box.select_one(".sales .value")
            old_price_tag = price_box.select_one(".strike-through .value")

        current_price_raw: Optional[str] = None
        old_price_raw: Optional[str] = None

        current_price: Optional[float] = None
        old_price: Optional[float] = None

        # Current price: prefer "content" attr, fallback to text
        if current_price_tag:
            content_attr = current_price_tag.get("content")
            if content_attr:
                current_price = _parse_price_any(content_attr)
                current_price_raw = content_attr.strip() + " €"
            else:
                txt = current_price_tag.get_text(strip=True)
                current_price = _parse_price_any(txt)
                if txt:
                    current_price_raw = txt.strip()
        # Old price (strike-through)
        if old_price_tag:
            content_attr = old_price_tag.get("content")
            if content_attr:
                old_price = _parse_price_any(content_attr)
                old_price_raw = content_attr.strip() + " €"
            else:
                txt = old_price_tag.get_text(strip=True)
                old_price = _parse_price_any(txt)
                if txt:
                    old_price_raw = txt.strip() + " €"

        # Fallback to GTM value if HTML parsing fails
        gtm_price_raw = gtm_item.get("price") or gtm_root.get("value")
        try:
            gtm_price_num = float(gtm_price_raw) if gtm_price_raw is not None else None
        except Exception:
            gtm_price_num = None

        if current_price is None and gtm_price_num is not None:
            current_price = gtm_price_num
            if not current_price_raw:
                current_price_raw = f"{gtm_price_num:.2f} €"

        # Compute original/final prices and discount (aligned with Supabase ingest contract)
        final_price = current_price

        # old_price must exist for DB/UX consistency:
        # - prefer strike-through when present
        # - else fallback to final_price
        old_price_value = old_price if old_price is not None else final_price

        # Price-based discount only if old > final
        has_price_discount = (
            old_price_value is not None
            and final_price is not None
            and old_price_value > final_price
        )

        discount_value = round(old_price_value - final_price, 2) if has_price_discount else 0.0


        # Kept old naming, but DB uses old_price
        original_price = old_price_value

        # Align with Auchan rule: price == final_price
        price = final_price


        # Unit price string (e.g. "0.6 Kg | 10,73 €/Kg")
        unit_div = container.select_one("div.product-unit")
        unit_price_raw: Optional[str] = None
        unit_suffix: Optional[str] = None
        min_quantity_raw: Optional[str] = None

        if unit_div:
            full_text = unit_div.get_text(" ", strip=True)
            if "|" in full_text:
                parts = full_text.split("|")
                min_quantity_raw = parts[0].strip()  # "0.6 Kg"
                unit_price_raw = parts[1].strip()    # "10,73 €/Kg"

                # Try to extract a unit suffix such as Kg, L, Un from the unit price
                m_suffix = re.search(r"€\s*/\s*([A-Za-z\.]+)", unit_price_raw)

                if m_suffix:
                    unit_suffix = re.sub(r"[^A-Za-z]", "", m_suffix.group(1))

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

        # Normalize unit suffix (kg, l, un, etc.)
        unit_suffix = normalize_unit_suffix(unit_suffix)

        # Numeric unit price used by DB/UI (e.g. 10.73 for "10,73 €/Kg")
        unit_price_value: Optional[float] = _parse_price_any(unit_price_raw)

        

        # ================================================================
        # Promotions & Labels
        # ================================================================
        promo_badge = container.select_one("img.product-tile-promo-label")

        promo_badge_label_raw = None
        if promo_badge:
            promo_badge_label_raw = (
                promo_badge.get("alt")
                or promo_badge.get("title")
                or ""
            ).strip() or None

        promo_text_tag = container.select_one("span.promo-message")
        promotion_raw = promo_text_tag.get_text(strip=True) if promo_text_tag else None

        # Badge is only "promotional" if it's not in the known non-promo set
        badge_is_promotional = bool(
            promo_badge_label_raw
            and promo_badge_label_raw.strip().lower() not in NON_PROMO_BADGES
        )

        # Labels exist if either:
        # - promotional badge, or
        # - promo message text exists (e.g., "Promoção até 15/12")
        has_label = bool(
            badge_is_promotional
            or (promotion_raw and promotion_raw.strip())
        )

        # discount_badge_raw must be a real discount (e.g. "-25%") or None.
        # Never store "Apenas"/"Novidade"/etc. in this field.
        discount_badge_raw: Optional[str] = None

        # 1) If we have a promotional badge, try normalize it (may still return non-% -> guard)
        if badge_is_promotional:
            normalized = _normalize_discount_badge(promo_badge_label_raw)
            if normalized and "%" in normalized:
                discount_badge_raw = normalized

        # 2) If no percent badge, but we have label + real price discount, compute from prices
        if has_label and not discount_badge_raw and has_price_discount:
            computed_pct = _discount_percent_from_prices(old_price_value, final_price)
            if computed_pct:
                discount_badge_raw = computed_pct

        # FINAL RULE: promotion only if label exists AND discount is real
        is_on_promotion = bool(has_label and has_price_discount)


        # No explicit Bio/National flags in tiles (would require extra heuristics)
        is_bio = False
        is_national = False

        # ================================================================
        # Ratings (Bazaarvoice)
        # ================================================================
        rating_div = container.select_one(".rating_summary")
        rating_pid = rating_div.get("data-bv-product-id") if rating_div else None

        # ================================================================
        # GTM numeric fields mapped for DB
        #   - gtm_price: treat as original price if there is discount,
        #                otherwise current price
        # ================================================================
        gtm_price_for_db = gtm_price_num if gtm_price_num is not None else final_price

        # Quantity: fallback to 1.0 when missing
        gtm_quantity_raw = gtm_item.get("quantity")
        try:
            gtm_quantity = float(gtm_quantity_raw) if gtm_quantity_raw is not None else 1.0
        except Exception:
            gtm_quantity = 1.0

        # ================================================================
        # Final Dict (aligned with Auchan structure)
        # ================================================================
        products.append(
            {
                "name": name,
                "link": link,
                "min_quantity": min_quantity_raw,
                # IMPORTANT: variants.quantity is driven by this field in supabase_client
                "quantity": min_quantity_raw,
                "unit_price_raw": unit_price_raw,
                "current_price_raw": current_price_raw,
                "old_price_raw": old_price_raw,
                "promotion_raw": promotion_raw,
                "timestamp": run_timestamp,

                "promo_badge_label_raw": promo_badge_label_raw,
                "discount_badge_raw": discount_badge_raw,


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

                # Numeric price fields (used by DB)
                "price": price,                         # NEW: always equals final_price
                "old_price": old_price_value,           # NEW: ingest expects old_price
                "unit_price_value": unit_price_value,   # NEW: ingest expects unit_price_value

                "original_price": original_price,       # optional
                "discount_value": discount_value,
                "final_price": final_price,

                # NOTE: gtm_price is analytics-reported price, not guaranteed to be old/original
                "gtm_price": gtm_price_for_db,
                "gtm_discount_value": discount_value,
                "gtm_quantity": gtm_quantity,
                "unit_suffix": unit_suffix,

                # Status flags
                "is_on_promotion": is_on_promotion,
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
    # Fallback: procurar números em padrões comuns (Demandware / analytics / JSON)
    m = re.search(r'("total"\s*:\s*|totalCount"\s*:\s*|total-count"\s*:\s*")(\d+)', html, re.IGNORECASE)
    if m:
        try:
            return int(m.group(2))
        except Exception:
            pass

    m = re.search(r'\b(\d+)\s+resultados\b', html, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    return None

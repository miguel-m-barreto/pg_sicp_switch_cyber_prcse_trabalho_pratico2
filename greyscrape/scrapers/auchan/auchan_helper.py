# greyscrape/scrapers/auchan/auchan_helper.py

import json
import os
import re
import html as html_lib
from typing import List, Dict, Optional, Tuple, Optional
from pathlib import Path

import time

import requests

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from common.unit_normalize import normalize_unit_suffix

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env.local")

BASE_URL = os.getenv("AUCHAN_BASE_URL", "https://www.auchan.pt")

_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_MIN_QTY_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml)\b", re.IGNORECASE)


_PROMO_DATE_RE = re.compile(r"\bde\s+\d{2}/\d{2}/\d{4}\s+a\s+\d{2}/\d{2}/\d{4}\b", re.IGNORECASE)

def _fetch_promotion_raw_from_pdp(pdp_url: str, timeout: float = 15.0) -> Optional[str]:
    if not pdp_url:
        return None

    try:
        r = requests.get(pdp_url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        })
        if r.status_code != 200 or not r.text:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # primary
        tag = soup.select_one(".auc-price__promotion--pdp__date")
        if tag:
            txt = tag.get_text(" ", strip=True)
            return txt or None

        # fallback: whole block then extract the date range
        block = soup.select_one(".auc-price__promotion--pdp")
        if block:
            txt = block.get_text(" ", strip=True) or ""
            txt = txt.replace("Promoção:", "").strip()
            m = _PROMO_DATE_RE.search(txt)
            return m.group(0) if m else (txt or None)

        return None
    except Exception:
        return None

def _to_float(num_str: Optional[str]) -> Optional[float]:
    if not num_str:
        return None
    s = str(num_str).strip().replace("\xa0", " ")
    # "1 234,56" -> "1234.56"
    s = s.replace(" ", "")
    if "," in s and "." in s:
        # decimal is rightmost separator
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _parse_price_text(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    t = html_lib.unescape(text).strip()
    m = _PRICE_RE.search(t)
    return _to_float(m.group(1)) if m else None


def _loads_escaped_json(attr_val: Optional[str]) -> Dict:
    if not attr_val:
        return {}
    # Attributes come HTML-escaped (&quot; etc.)
    s = html_lib.unescape(attr_val)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {}


def _pick_image_url(container: BeautifulSoup) -> Optional[str]:
    # Common: <img src=" " data-src="https://...jpg?...">
    img = container.select_one("div.image-container img")
    if img:
        url = (img.get("data-src") or img.get("src") or "").strip()
        if url and url != "":
            if url.startswith("/"):
                return BASE_URL + url
            return url

    # Fallback: <source data-srcset="https://...">
    src = container.select_one("picture source[data-srcset]")
    if src:
        url = (src.get("data-srcset") or "").strip()
        if url:
            return url

    return None


def _parse_unit_price_and_unit(unit_price_raw: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    # Examples:
    # "5.68 €/Kg", "1.99 €/L", "22.49 €/un", "69.2 €/Lt"
    if not unit_price_raw:
        return None, None

    text = html_lib.unescape(unit_price_raw).strip()

    value = _parse_price_text(text)

    unit = None
    if "€/" in text:
        unit = text.split("€/", 1)[1].strip()
    elif "/" in text:
        unit = text.split("/", 1)[1].strip()

    if unit:
        # keep only letters
        unit = re.sub(r"[^A-Za-z]", "", unit)
        unit = normalize_unit_suffix(unit)

    return value, unit


def _parse_min_qty(min_quantity_raw: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    # Example: "Quant. Mínima = 150g"
    if not min_quantity_raw:
        return None, None

    t = html_lib.unescape(min_quantity_raw).strip()
    m = _MIN_QTY_RE.search(t)
    if not m:
        return None, None

    val = _to_float(m.group(1))
    unit = m.group(2).lower()
    if val is None:
        return None, None

    # normalize to KG / L
    if unit == "g":
        return val / 1000.0, "kg"
    if unit == "ml":
        return val / 1000.0, "l"
    if unit in ("kg", "l"):
        return val, unit

    return None, None


def extract_products_from_html(html: str, run_timestamp: str) -> List[Dict]:
    """
    Parse an Auchan HTML page/fragment and extract product data.

    Key fixes:
      - Properly decode HTML-escaped JSON attributes before json.loads
      - Correctly distinguish unit price vs total price for variable-weight products
      - More robust image extraction (data-src / data-srcset)
      - Do not treat 'Promoção' label as authoritative promo flag
    """
    soup = BeautifulSoup(html, "html.parser")
    products: List[Dict] = []

    for container in soup.select("div.product-tile.auc-product-tile"):
        # ------------------------------------------------------------
        # Escaped JSON metadata
        # ------------------------------------------------------------
        gtm = _loads_escaped_json(container.get("data-gtm"))
        gtm_new = _loads_escaped_json(container.get("data-gtm-new"))
        urls = _loads_escaped_json(container.get("data-urls"))

        # ------------------------------------------------------------
        # Identifiers
        # ------------------------------------------------------------
        product_id = container.get("data-pid") or gtm_new.get("item_id") or gtm.get("id")
        brand = (gtm_new.get("item_brand") or gtm.get("brand") or None)

        category_slug_path = gtm.get("category") or None
        category_human_1 = gtm_new.get("item_category")
        category_human_2 = gtm_new.get("item_category2")
        category_human_3 = gtm_new.get("item_category3")
        category_human_4 = gtm_new.get("item_category4")

        product_type = container.get("data-producttype") or None

        # ------------------------------------------------------------
        # Listing positions
        # ------------------------------------------------------------
        gtm_position = gtm.get("position") or container.get("data-position")
        try:
            gtm_position = int(str(gtm_position).strip())
        except Exception:
            gtm_position = None

        list_index = gtm_new.get("index")
        try:
            list_index = int(str(list_index).strip())
        except Exception:
            list_index = None

        # ------------------------------------------------------------
        # URLs
        # ------------------------------------------------------------
        pdp_url_relative = urls.get("productUrl")
        pdp_url_absolute = urls.get("absoluteProductUrl")
        encoded_product_url = urls.get("encodedProductUrl")

        title_tag = container.select_one("div.auc-product-tile__name a.link") or container.select_one("div.auc-product-tile__name a")
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

        # ------------------------------------------------------------
        # Name
        # ------------------------------------------------------------
        if title_tag:
            name = html_lib.unescape(title_tag.get_text(strip=True))
        else:
            name = html_lib.unescape(gtm_new.get("item_name") or gtm.get("name") or "")

        # ------------------------------------------------------------
        # Image
        # ------------------------------------------------------------
        image_url = _pick_image_url(container)
        img_tag = container.select_one("div.image-container img")
        image_alt = img_tag.get("alt") if img_tag else None
        image_title = img_tag.get("title") if img_tag else None

        # ------------------------------------------------------------
        # Measures
        # ------------------------------------------------------------
        min_qty_tag = container.select_one("span.auc-measures--avg-weight")
        min_quantity_raw = min_qty_tag.get_text(" ", strip=True) if min_qty_tag else None

        unit_price_tag = container.select_one("span.auc-measures--price-per-unit")
        unit_price_raw = unit_price_tag.get_text(" ", strip=True) if unit_price_tag else None

        unit_price_value, unit_suffix = _parse_unit_price_and_unit(unit_price_raw)

        min_qty_norm, min_qty_unit = _parse_min_qty(min_quantity_raw)
        is_variable_weight = min_qty_norm is not None and min_qty_unit in ("kg", "l")

        # ------------------------------------------------------------
        # Prices (DOM)
        # ------------------------------------------------------------
        price_now_numeric: Optional[float] = None
        original_price_numeric: Optional[float] = None
        current_price_raw: Optional[str] = None
        old_price_raw: Optional[str] = None

        sales_val = container.select_one("div.price span.sales span.value")
        if sales_val:
            current_price_raw = sales_val.get_text(" ", strip=True)
            content = sales_val.get("content")
            if content:
                try:
                    price_now_numeric = float(content)
                except Exception:
                    price_now_numeric = _parse_price_text(current_price_raw)

        # Old price (only reliable when actually present as strike-through)
        old_val = (
            container.select_one("span.strike-through .value")
            or container.select_one(".strike-through .value")
            or container.select_one("span.strike-through.value")
        )
        if old_val:
            old_price_raw = old_val.get_text(" ", strip=True)
            content = old_val.get("content")
            if content:
                try:
                    original_price_numeric = float(content)
                except Exception:
                    original_price_numeric = _parse_price_text(old_price_raw)

        # ------------------------------------------------------------
        # GTM numeric
        # NOTE: In this endpoint, gtm_new.price is often MIN TOTAL for variable-weight,
        # while unit price is in DOM measures.
        # ------------------------------------------------------------
        gtm_price = None
        try:
            if gtm_new.get("price") is not None:
                gtm_price = float(gtm_new.get("price"))
        except Exception:
            gtm_price = None

        gtm_discount_value = None
        try:
            if gtm_new.get("discount") is not None:
                gtm_discount_value = float(gtm_new.get("discount"))
        except Exception:
            gtm_discount_value = None

        gtm_quantity = None
        try:
            if gtm_new.get("quantity") is not None:
                gtm_quantity = float(gtm_new.get("quantity"))
        except Exception:
            gtm_quantity = None

        # ------------------------------------------------------------
        # Semantic pricing fix:
        # - final_price is ALWAYS the TOTAL the user pays (or min total for variable weight)
        # - price is ALWAYS equal to final_price (your new rule)
        # - old_price is NEVER null:
        #     - prefer real DOM strike-through when available and valid
        #     - else derive from (final_price + discount_value) if discount exists
        #     - else fallback to final_price
        # ------------------------------------------------------------
        if is_variable_weight:
            # Prefer GTM min total when present
            min_total = gtm_price
            if min_total is None and unit_price_value is not None and min_qty_norm is not None:
                min_total = round(unit_price_value * min_qty_norm, 2)

            final_price = min_total
            dom_old_price = None  # strike-through total usually not reliable here
        else:
            # Fixed-weight product
            final_price = price_now_numeric if price_now_numeric is not None else gtm_price
            dom_old_price = original_price_numeric  # only if strike-through exists

        # Ensure numeric sanity
        if final_price is not None and final_price < 0:
            final_price = None
        if dom_old_price is not None and dom_old_price < 0:
            dom_old_price = None

        # Discount value (prefer real math from DOM old > final)
        discount_value = None
        if dom_old_price is not None and final_price is not None and dom_old_price > final_price:
            discount_value = round(dom_old_price - final_price, 2)
        elif gtm_discount_value is not None and gtm_discount_value > 0 and final_price is not None:
            discount_value = round(gtm_discount_value, 2)

        # old_price fallback rules:
        # 1) Real DOM old price if valid
        # 2) Derived old price if discount exists
        # 3) Fallback to final_price (never null)
        if dom_old_price is not None and final_price is not None and dom_old_price > final_price:
            old_price = round(dom_old_price, 2)
        elif discount_value is not None and discount_value > 0 and final_price is not None:
            old_price = round(final_price + discount_value, 2)
        else:
            old_price = round(final_price, 2) if final_price is not None else None

        # New rule: price == final_price always
        price = round(final_price, 2) if final_price is not None else None


        # ------------------------------------------------------------
        # Promotions (DB-compatible with Pingo dict)
        # - discount_badge_raw: "-NN%" (only if validated)
        # - promo_badge_label_raw: "Apenas", "Poupa metade", etc (keep as-is)
        # - promotion_raw: "Promoção até dd/mm" etc (keep as-is)
        # - is_on_promotion: ONLY if there is some label AND old_price > final_price
        # ------------------------------------------------------------
        promo_badge_label_raw = None
        promo_label_tag = container.select_one(".auc-price__promotion__label")
        if promo_label_tag:
            promo_badge_label_raw = promo_label_tag.get_text(" ", strip=True) or None

        # This is often the red badge. If it contains %, it belongs in discount_badge_raw.
        raw_badge_text = None
        badge_tag = container.select_one(".auc-promo--discount--red")
        if badge_tag:
            raw_badge_text = badge_tag.get_text(" ", strip=True) or None

        # Promo message (date/rules). Selector may vary; keep best-effort.
        promotion_raw = None
        promo_msg_tag = (
            container.select_one(".auc-price__promotion__message")
            or container.select_one(".auc-price__promotion__msg")
            or container.select_one(".auc-price__promotion__text")
            or container.select_one("span.promo-message")
        )
        if promo_msg_tag:
            promotion_raw = promo_msg_tag.get_text(" ", strip=True) or None

        # Gate: you can only claim promo if there is at least one label/message/badge.
        has_label = bool(
            (promo_badge_label_raw and promo_badge_label_raw.strip())
            or (raw_badge_text and raw_badge_text.strip())
            or (promotion_raw and promotion_raw.strip())
        )

        # Real discount check (your rule): old_price > final_price
        has_price_discount = bool(
            old_price is not None
            and final_price is not None
            and old_price > 0
            and old_price > final_price
        )

        # discount_badge_raw must be the percent (validated)
        discount_badge_raw = None

        if has_label and has_price_discount:
            # 1) If any visible text already has %, trust it.
            pct = None
            for s in (promo_badge_label_raw, raw_badge_text):
                if not s:
                    continue
                m = re.search(r"(\d+)\s*%", s)
                if m:
                    pct = int(m.group(1))
                    break

            # 2) Else compute from prices (uses derived old_price too — what you want)
            if pct is None:
                pct = int(round(((old_price - final_price) / old_price) * 100))

            if pct and pct > 0:
                discount_badge_raw = f"-{pct}%"

            is_on_promotion = True
        else:
            # Label exists but no real discount -> marketing only
            is_on_promotion = False

        # If we got a % from the site but prices don't confirm, nuke it (avoid lying)
        if (not has_price_discount) and raw_badge_text and re.search(r"\d+\s*%", raw_badge_text or ""):
            discount_badge_raw = None

        # ------------------------------------------------------------
        # Promotion fallback: SearchUpdateGrid doesn't include promo dates.
        # If product is on promotion but promotion_raw is missing, fetch PDP.
        # ------------------------------------------------------------
        if is_on_promotion and not promotion_raw:
            # Minimal throttle to reduce block risk
            time.sleep(0.15)
            promotion_raw = _fetch_promotion_raw_from_pdp(pdp_url_absolute or link)


        # ------------------------------------------------------------
        # Labels
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # Ratings
        # ------------------------------------------------------------
        ratings_div = container.select_one("div.auc-product-tile__bazaarvoice--ratings")
        rating_product_id = ratings_div.get("data-bv-product-id") if ratings_div else None
        rating_url = ratings_div.get("data-bv-redirect-url") if ratings_div else None

        # ------------------------------------------------------------
        # Availability flags
        # ------------------------------------------------------------
        limited_modal = container.get("data-shown-limited-availability-modal")
        limited_modal = str(limited_modal).lower() == "true" if limited_modal is not None else None

        delay_modal = container.get("data-shown-delay-delivery-modal")
        delay_modal = str(delay_modal).lower() == "true" if delay_modal is not None else None

        # ------------------------------------------------------------
        # Final dict (keeps your existing schema + adds clarity)
        # ------------------------------------------------------------
        products.append({
            "name": name,
            "link": link,
            "min_quantity": min_quantity_raw,
            "unit_price_raw": unit_price_raw,
            "current_price_raw": current_price_raw,
            "old_price_raw": old_price_raw,
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

            # Prices (semantic + DB alignment)
            "price": price,                 # ALWAYS equals final_price
            "old_price": old_price,         # NEVER null (fallback applied)
            "discount_value": discount_value,
            "final_price": final_price,


            # Extra price semantics (important for downstream fixes)
            "unit_price_value": unit_price_value,
            "is_variable_weight": is_variable_weight,
            "min_qty_norm": min_qty_norm,
            "min_qty_unit": min_qty_unit,

            "gtm_quantity": gtm_quantity,
            "unit_suffix": unit_suffix,

            "gtm_price": gtm_price,
            "gtm_discount_value": gtm_discount_value,


            # Listing metadata
            "gtm_web_position": gtm_position,
            "gtm_list_index": list_index,

            # Promotion
            "discount_badge_raw": discount_badge_raw,
            "promotion_raw": promotion_raw,
            "promo_badge_label_raw": promo_badge_label_raw,
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

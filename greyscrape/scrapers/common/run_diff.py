# greyscrape/scrapers/common/run_diff.py

import hashlib
from typing import Dict, List, Tuple, Optional, Callable
from urllib.parse import urlparse, urlunparse

ExtractIdFn = Callable[[str], Optional[str]]


def build_state_key(p: Dict) -> str:
    """
    Build a canonical 'state key' for a product at the PRICING state level.

    It only considers commercial state (prices, promotions, stock), not
    catalog identity (name, categories, etc.).
    """
    parts = [
        str(p.get("final_price") or ""),
        str(p.get("old_price") or ""),
        str(p.get("unit_price_value") or p.get("unit_price") or ""),
        str(p.get("promotion_raw") or ""),
        str(p.get("discount_badge_raw") or ""),
        str(p.get("stock_status") or ""),
    ]
    return "|".join(parts)


def build_state_hash(p: Dict) -> str:
    """
    Build a compact hash of the pricing state.
    """
    parts = [
        str(p.get("final_price") or ""),
        str(p.get("old_price") or ""),
        str(p.get("unit_price_value") or ""),
        str(p.get("is_on_promotion")),
        str(p.get("discount_badge_raw") or ""),
        str(p.get("promotion_raw") or ""),
        str(p.get("stock_status") or ""),
        str(p.get("limited_availability_flag") or ""),
        str(p.get("delay_delivery_flag") or ""),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_image_url(url: Optional[str]) -> str:
    """
    Normalize image URL for catalog hash:
      - empty if None
      - remove query and fragment (cache-busters)
    """
    if not url:
        return ""
    url = str(url).strip()
    try:
        parsed = urlparse(url)
        cleaned = parsed._replace(query="", fragment="")
        return urlunparse(cleaned)
    except Exception:
        return url


def _labels_key(labels_raw: Optional[List[Dict]]) -> str:
    """
    Build a stable key for labels_raw (list of dicts).
    Order-independent, based on (code, alt, title, src).
    """
    if not labels_raw or not isinstance(labels_raw, list):
        return ""

    tokens: List[str] = []

    for item in labels_raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        alt = str(item.get("alt") or "").strip()
        title = str(item.get("title") or "").strip()
        src = str(item.get("src") or "").strip()
        tokens.append("|".join([code, alt, title, src]))

    # Order-independent
    tokens.sort()
    return "||".join(tokens)


def build_catalog_key(p: Dict) -> str:
    """
    Build a 'catalog identity' key for a product.

    This is used only to decide if the catalog-level metadata changed
    (name, brand, categories, image, labels, flags, etc.).

    It deliberately ignores pricing fields, which are handled separately
    by build_state_hash().
    """
    def norm(value: Optional[str]) -> str:
        return str(value or "").strip()

    def norm_bool(value: Optional[bool]) -> str:
        return "1" if value else "0"

    image_url = _normalize_image_url(p.get("image_url"))

    labels_key = _labels_key(p.get("labels_raw"))

    parts = [
        norm(p.get("name")),
        norm(p.get("brand")),
        norm(p.get("product_type")),
        norm(p.get("category_slug_path")),
        norm(p.get("category_human_1")),
        norm(p.get("category_human_2")),
        norm(p.get("category_human_3")),
        norm(p.get("category_human_4")),
        norm(image_url),
        labels_key,
        norm_bool(p.get("is_bio")),
        norm_bool(p.get("is_national_product")),
        norm_bool(p.get("is_refrigerated")),
        norm(p.get("unit_suffix")),
        norm(p.get("min_quantity")),
    ]

    return "||".join(parts)


def _build_ext_map(
    produtos: List[Dict],
    extract_external_id: ExtractIdFn,
) -> Dict[str, Dict]:
    """
    Convert a list of product dicts into a map external_id -> product_dict.

    If there are duplicates for the same external_id, the last one wins.
    """
    result: Dict[str, Dict] = {}
    for p in produtos:
        ext_id = extract_external_id(p.get("link", ""))
        if not ext_id:
            continue
        result[ext_id] = p
    return result


def diff_runs(
    prev_products: List[Dict],
    curr_products: List[Dict],
    extract_external_id: ExtractIdFn,
) -> Tuple[List[Tuple[str, Dict]], List[Tuple[str, Dict]], List[str]]:
    """
    Compute diff between previous full run and current full run.

    Returns:
      new_items:      list of (external_id, product_dict) for products that only exist now
      changed_items:  list of (external_id, product_dict) for products that changed
                      pricing state OR catalog metadata
      deleted_ids:    list of external_ids that disappeared in the current run

    All decisions are based purely on the external_id, pricing state hash and
    catalog identity hash.
    """
    prev_map = _build_ext_map(prev_products, extract_external_id)
    curr_map = _build_ext_map(curr_products, extract_external_id)

    prev_ids = set(prev_map.keys())
    curr_ids = set(curr_map.keys())

    new_ids = curr_ids - prev_ids
    deleted_ids = list(prev_ids - curr_ids)
    common_ids = prev_ids & curr_ids

    new_items: List[Tuple[str, Dict]] = []
    changed_items: List[Tuple[str, Dict]] = []

    # New products: only exist in current
    for ext_id in new_ids:
        p = curr_map[ext_id]
        new_items.append((ext_id, p))

    # Changed products: exist in both but pricing OR catalog hash differs
    for ext_id in common_ids:
        prev_p = prev_map[ext_id]
        curr_p = curr_map[ext_id]

        prev_state_hash = build_state_hash(prev_p)
        curr_state_hash = build_state_hash(curr_p)

        prev_catalog_key = build_catalog_key(prev_p)
        curr_catalog_key = build_catalog_key(curr_p)

        if (prev_state_hash != curr_state_hash) or (prev_catalog_key != curr_catalog_key):
            changed_items.append((ext_id, curr_p))

    return new_items, changed_items, deleted_ids

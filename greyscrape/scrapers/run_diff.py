import hashlib
from typing import Dict, List, Tuple, Optional, Callable

ExtractIdFn = Callable[[str], Optional[str]]


def build_state_key(p: Dict) -> str:
    """
    Build a canonical 'state key' for a product at the PRICING state level.

    IMPORTANT:
      - This is used BOTH to:
          * decidir NEW/CHANGED no diff entre runs
          * construir o state_hash para product_snapshots

      - Só deve incluir campos que definem o estado comercial:
          preço, promoções, preço unitário, stock, etc.

      - NÃO inclui nome, categoria, quantidade_minima, etc., porque isso
        é identidade de catálogo / apresentação, não estado económico.
    """
    parts = [
        str(p.get("preco_atual") or "").strip(),
        str(p.get("preco_antigo") or "").strip(),
        str(p.get("preco_unitario") or "").strip(),
        str(p.get("promocao") or "").strip(),
        str(p.get("stock_status") or "").strip(),
    ]
    return "|".join(parts)


def build_state_hash(p: Dict) -> str:
    """
    Build a compact hash of the pricing state.
    """
    key = build_state_key(p)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


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
      changed_items:  list of (external_id, product_dict) for products that changed state
      deleted_ids:    list of external_ids that disappeared in the current run

    All decisions are based purely on the external_id and the pricing 'state hash'.
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

    # Changed products: exist in both but pricing state hash differs
    for ext_id in common_ids:
        prev_p = prev_map[ext_id]
        curr_p = curr_map[ext_id]

        prev_hash = build_state_hash(prev_p)
        curr_hash = build_state_hash(curr_p)

        if prev_hash != curr_hash:
            changed_items.append((ext_id, curr_p))

    return new_items, changed_items, deleted_ids

# greyscrape/scrapers/run_diff.py

import hashlib
from typing import Dict, List, Tuple, Optional, Callable

ExtractIdFn = Callable[[str], Optional[str]]


def build_state_key(p: Dict) -> str:
    """
    Build a canonical 'state key' for a product at the CATALOG level.

    IMPORTANT:
      - This is used ONLY to decidir NEW/CHANGED para a tabela 'products'.
      - NÃO deve incluir preço, promoções, stock, etc., porque isso
        é responsabilidade dos snapshots.

    Aqui consideramos estáveis:
      - nome
      - quantidade_minima (ex: '500 ml', '1 kg'), que representa a embalagem.
    """
    parts = [
        str(p.get("nome") or "").strip(),
        str(p.get("quantidade_minima") or "").strip(),
        # Se um dia quiseres tratar categoria como parte da identidade de catálogo,
        # podes acrescentar aqui p.get("source_page_path"), mas para já deixo fora.
    ]
    return "|".join(parts)


def build_state_hash(p: Dict) -> str:
    """
    Build a compact hash of the state key.
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

    All decisions are based purely on the external_id and the 'state hash'.
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

    # Changed products: exist in both but state hash differs
    for ext_id in common_ids:
        prev_p = prev_map[ext_id]
        curr_p = curr_map[ext_id]

        prev_hash = build_state_hash(prev_p)
        curr_hash = build_state_hash(curr_p)

        if prev_hash != curr_hash:
            changed_items.append((ext_id, curr_p))

    return new_items, changed_items, deleted_ids

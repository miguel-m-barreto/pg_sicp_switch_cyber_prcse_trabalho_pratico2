# greyscrape/scrapers/common/send_to_db.py

import os
import json
import shutil
from typing import List, Dict, Tuple, Optional, Callable

from store_common import log_msg
from run_diff import diff_runs
from supabase_client import (
    push_products_with_snapshots,
    mark_products_deleted,
)

# Type aliases for clarity
ExtractIdFn = Callable[[str], Optional[str]]
ParsePriceFn = Callable[[Optional[str]], Optional[float]]


def _list_run_dirs(logs_root: str) -> List[str]:
    """
    List available run directories under <logs_root>, sorted ascending.

    Each dir name should be the execution timestamp, e.g. '2025-12-04_23-17-04'.
    """
    if not os.path.isdir(logs_root):
        raise RuntimeError(f"Logs root does not exist: {logs_root}")

    runs = []
    for name in os.listdir(logs_root):
        full = os.path.join(logs_root, name)
        if os.path.isdir(full):
            runs.append(name)

    runs.sort()
    return runs


def _load_run_products(logs_root: str, run_name: str) -> List[Dict]:
    """
    Given a run name (timestamp dir), load all JSON files from its 'json' folder
    and return a flat list of product dicts.
    """
    json_dir = os.path.join(logs_root, run_name, "json")
    if not os.path.isdir(json_dir):
        raise RuntimeError(f"JSON dir not found for run '{run_name}': {json_dir}")

    all_products: List[Dict] = []
    files = sorted(f for f in os.listdir(json_dir) if f.endswith(".json"))

    if not files:
        log_msg(f"[sendToDB] No JSON files in run '{run_name}' ({json_dir})")
        return all_products

    for fname in files:
        path = os.path.join(json_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            log_msg(f"[sendToDB] Failed to load JSON '{path}': {exc}")
            continue

        if isinstance(data, list):
            all_products.extend(data)
        else:
            log_msg(f"[sendToDB] JSON '{path}' is not a list, skipping.")

    log_msg(
        f"[sendToDB] Loaded {len(all_products)} products from run '{run_name}' "
        f"({len(files)} JSON files)"
    )
    return all_products


def _select_runs(logs_root: str) -> Tuple[Optional[str], str]:
    """
    Pick previous and current runs, considering only runs marked as 'success'.

    Any run folder without a valid run_status.json or with status != 'success'
    is treated as invalid and deleted.
    """
    runs = _list_run_dirs(logs_root)
    if not runs:
        raise RuntimeError(f"No runs found under {logs_root}")

    valid_runs: List[str] = []

    for name in runs:
        status_path = os.path.join(logs_root, name, "run_status.json")
        status_value: Optional[str] = None

        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    status_json = json.load(f)
                status_value = status_json.get("status")
            except Exception as exc:
                log_msg(
                    f"[sendToDB] Failed to read run_status.json for '{name}': {exc}"
                )

        if status_value == "success":
            valid_runs.append(name)
        else:
            # Invalid run (no status or status != success): delete the folder
            run_path = os.path.join(logs_root, name)
            try:
                shutil.rmtree(run_path)
                log_msg(
                    f"[sendToDB] Deleted invalid/failed run folder: {run_path}"
                )
            except Exception as exc:
                log_msg(
                    f"[sendToDB] Failed to delete invalid run folder '{run_path}': {exc}"
                )

    if not valid_runs:
        raise RuntimeError(
            f"No valid runs (status=success) found under {logs_root}"
        )

    if len(valid_runs) == 1:
        # Only one valid run: treat everything as NEW vs 'no previous run'
        return None, valid_runs[-1]

    prev_run = valid_runs[-2]
    curr_run = valid_runs[-1]
    return prev_run, curr_run


def _combine_items(
    new_items: List[Tuple[str, Dict]],
    changed_items: List[Tuple[str, Dict]],
    curr_products: List[Dict],
    extract_external_id: ExtractIdFn,
) -> List[Dict]:
    """
    Given:
      - new_items / changed_items: listas (external_id, product_dict) vindas do diff
      - curr_products: lista COMPLETA de produtos da run atual

    Devolve:
      - todos os product_dict da run atual cujo external_id está em
        NEW ∪ CHANGED.

    Isto garante que, se tens várias variantes (links/categorias) com o
    mesmo external_id na mesma run, TODAS são enviadas para snapshots,
    mas continuas a não enviar produtos cujo external_id não mudou.
    """
    # Conjunto de external_ids que mudaram ou são novos
    target_ids = {ext_id for ext_id, _ in new_items}
    target_ids.update(ext_id for ext_id, _ in changed_items)

    if not target_ids:
        return []

    combined: List[Dict] = []
    for p in curr_products:
        ext_id = extract_external_id(p.get("link", ""))
        if not ext_id:
            continue
        if ext_id in target_ids:
            combined.append(p)

    return combined



def _cleanup_old_runs(logs_root: str, keep_last: int = 2) -> None:
    """
    Delete old run folders in <logs_root>, keeping only the most recent 'keep_last'.
    """
    runs = _list_run_dirs(logs_root)
    if len(runs) <= keep_last:
        log_msg(
            f"[sendToDB] Cleanup: nothing to delete "
            f"({len(runs)} runs <= keep_last={keep_last})"
        )
        return

    to_delete = runs[:-keep_last]
    for run_name in to_delete:
        path = os.path.join(logs_root, run_name)
        try:
            shutil.rmtree(path)
            log_msg(f"[sendToDB] Deleted old run folder: {path}")
        except Exception as exc:
            log_msg(f"[sendToDB] Failed to delete '{path}': {exc}")


def send_store_to_db(
    logs_root: str,
    store_id_env_var: str,
    store_label: str,
    extract_external_id: ExtractIdFn,
    parse_price: ParsePriceFn,
    diff_query_prefix: str,
    keep_last_runs: int = 2,
) -> None:
    """
    Generic pipeline for any store:

      logs_root:            root folder for runs, e.g. '<scrapers>/auchan/logs'
      store_id_env_var:     env var with the store_id (e.g. 'SUPABASE_AUCHAN_STORE_ID')
      store_label:          label for logs ('Auchan', 'Pingo Doce', ...)
      extract_external_id:  function to extract external_id from product link
      parse_price:          function to parse price strings into floats
      diff_query_prefix:    prefix for the diff query name (e.g. 'auchan_diff')
    """
    # Choose which runs to compare
    prev_run, curr_run = _select_runs(logs_root)

    if prev_run:
        log_msg(f"[sendToDB][{store_label}] Using previous run: {prev_run}")
    else:
        log_msg(
            f"[sendToDB][{store_label}] No previous run found, treating everything as NEW."
        )

    log_msg(f"[sendToDB][{store_label}] Using current run: {curr_run}")

    # Load products from JSON logs
    prev_products: List[Dict] = []
    if prev_run:
        prev_products = _load_run_products(logs_root, prev_run)

    curr_products = _load_run_products(logs_root, curr_run)

    if not curr_products:
        log_msg(f"[sendToDB][{store_label}] Current run has no products, aborting.")
        return

    # Compute diff (NEW, CHANGED, DELETED)
    new_items, changed_items, deleted_ids = diff_runs(
        prev_products,
        curr_products,
        extract_external_id=extract_external_id,
    )

    log_msg(
        f"[sendToDB][{store_label}] Diff result: "
        f"NEW={len(new_items)}, CHANGED={len(changed_items)}, "
        f"DELETED={len(deleted_ids)}"
    )

    #  Prepare list of products to send (only NEW + CHANGED),
    #    mas incluindo TODAS as variantes (mesmo external_id em várias categorias/links)
    produtos_to_send = _combine_items(
        new_items,
        changed_items,
        curr_products,
        extract_external_id,
    )

    # Push NEW + CHANGED to Supabase using the generic helper
    if produtos_to_send:
        query = f"{diff_query_prefix}:{prev_run or 'none'}->{curr_run}"

        log_msg(
            f"[sendToDB][{store_label}] Sending {len(produtos_to_send)} products "
            f"to Supabase with query='{query}'"
        )

        push_products_with_snapshots(
            produtos=produtos_to_send,
            query=query,
            store_id_env_var=store_id_env_var,
            extract_external_id=extract_external_id,
            parse_price=parse_price,
            store_label=store_label,
        )
    else:
        log_msg(f"[sendToDB][{store_label}] No NEW or CHANGED products to send.")

    # 6) Mark DELETED products in Supabase
    if deleted_ids:
        log_msg(
            f"[sendToDB][{store_label}] Marking {len(deleted_ids)} products as deleted "
            "in Supabase."
        )
        mark_products_deleted(
            deleted_ids=deleted_ids,
            store_id_env_var=store_id_env_var,
            store_label=store_label,
        )
    else:
        log_msg(f"[sendToDB][{store_label}] No DELETED products to mark.")

    # 7) Cleanup old run folders (keep only last N)
    _cleanup_old_runs(logs_root, keep_last=keep_last_runs)

    log_msg(f"[sendToDB][{store_label}] Done.")

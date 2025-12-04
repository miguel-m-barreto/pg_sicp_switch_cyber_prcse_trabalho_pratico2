#!/usr/bin/env python3
import sys
import json
from typing import Dict, Any, List


def load_dump(path: str) -> List[Dict[str, Any]]:
    """Load a JSON dump produced by the Auchan scraper."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected top-level JSON list of products.")

    return data


def analyze_products(produtos: List[Dict[str, Any]]) -> None:
    total = len(produtos)
    print(f"Total items in dump: {total}")

    missing_name = 0
    missing_link = 0
    invalid_items = 0

    seen_links = set()
    duplicate_links = 0

    for p in produtos:
        nome = (p.get("nome") or "").strip()
        link = (p.get("link") or "").strip()

        if not nome:
            missing_name += 1

        if not link:
            missing_link += 1

        if not nome and not link:
            invalid_items += 1

        if link:
            if link in seen_links:
                duplicate_links += 1
            else:
                seen_links.add(link)

    print(f"Items with missing name         : {missing_name}")
    print(f"Items with missing link         : {missing_link}")
    print(f"Items missing BOTH name and link: {invalid_items}")
    print(f"Duplicate link entries          : {duplicate_links}")
    print(f"Unique links                    : {len(seen_links)}")

    # Optionally, show a few problematic examples
    if missing_name > 0:
        print("\nExamples of items with missing name:")
        shown = 0
        for p in produtos:
            if not (p.get("nome") or "").strip():
                print(f"  - link={p.get('link')!r}, promo={p.get('promocao')!r}")
                shown += 1
                if shown >= 5:
                    break

    if invalid_items > 0:
        print("\nExamples of items missing BOTH name and link:")
        shown = 0
        for p in produtos:
            nome = (p.get("nome") or "").strip()
            link = (p.get("link") or "").strip()
            if not nome and not link:
                print(f"  - raw item: {p}")
                shown += 1
                if shown >= 3:
                    break


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_auchan_log.py path/to/log.json")
        sys.exit(1)

    path = sys.argv[1]
    produtos = load_dump(path)
    analyze_products(produtos)


if __name__ == "__main__":
    main()

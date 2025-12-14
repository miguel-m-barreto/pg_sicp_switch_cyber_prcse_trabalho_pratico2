# extract_links_only.py
# Reads a JSON file with link objects and extracts only the URLs into a new JSON file.

import json
from pathlib import Path

INPUT_FILE = Path("pingo_doce_sub_categories.json")
OUTPUT_FILE = Path("extracted_links_only.json")

def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected a list of objects in the input JSON")

    urls = [
        item["url"]
        for item in data
        if isinstance(item, dict) and "url" in item and item["url"]
    ]

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(urls)} URLs into {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

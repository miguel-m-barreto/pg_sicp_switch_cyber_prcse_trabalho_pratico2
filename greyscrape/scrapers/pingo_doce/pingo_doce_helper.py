# greyscrape/scrapers/pingo_doce/pingo_doce_helper.py

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

BASE_URL = os.getenv("PINGO_DOCE_BASE_URL", "https://www.pingodoce.pt")


def extract_products_from_html(html: str, run_timestamp: str) -> List[Dict]:
    """
    Parse one Pingo Doce HTML page/fragment and extract product info.

    NOTE: CSS selectors are based on current DOM:
      - outer container: div.product-tile.pd[data-pid]
      - name:           div.product-name-link a
      - brand:          div.product-brand-name
      - price:          div.product-price span.value (or similar)
      - unit price:     span.tile-conversion-unit-measure
      - min quantity:   span.tile-conversion-nd-one (or similar)

    If Pingo mudar classes, ajustas aqui e o resto do pipeline mantém-se.
    """
    soup = BeautifulSoup(html, "html.parser")
    produtos: List[Dict] = []

    for container in soup.select("div.product-tile.pd"):
        # Data PID (internal product id)
        data_pid = container.get("data-pid")

        # Name + link
        name_tag = container.select_one("div.product-name-link a")
        nome = name_tag.get_text(strip=True) if name_tag else ""

        link = ""
        if name_tag and name_tag.has_attr("href"):
            href = name_tag["href"].strip()
            if href.startswith("http"):
                link = href
            else:
                link = BASE_URL + href

        # Brand (optional)
        brand_tag = container.select_one("div.product-brand-name")
        brand = brand_tag.get_text(strip=True) if brand_tag else None

        # Current price
        price_tag = container.select_one("div.product-price span.value")
        preco_atual = price_tag.get_text(strip=True) if price_tag else None

        # Old price (promotional)
        old_price_tag = container.select_one("div.product-price span.was-price")
        preco_antigo = (
            old_price_tag.get_text(strip=True) if old_price_tag else None
        )

        # Price per unit (€/Kg, €/Un, ...)
        unit_tag = container.select_one("span.tile-conversion-unit-measure")
        preco_unitario = unit_tag.get_text(strip=True) if unit_tag else None

        # Minimum quantity / pack info (optional)
        qmin_tag = container.select_one("span.tile-conversion-nd-one")
        quantidade_minima = (
            qmin_tag.get_text(strip=True) if qmin_tag else None
        )

        # Promotion label (if any)
        promo_tag = container.select_one(".product-promo-label")
        promocao = promo_tag.get_text(strip=True) if promo_tag else None

        produtos.append(
            {
                "nome": nome,
                "brand": brand,
                "link": link,
                "data_pid": data_pid,
                "quantidade_minima": quantidade_minima,
                "preco_unitario": preco_unitario,
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "promocao": promocao,
                "data_execucao": run_timestamp,
            }
        )

    return produtos


def parse_total_results(html: str) -> Optional[int]:
    """
    Parse something like:
      "1 - 24 de 312 produtos"  -> 312

    Adjust selector and regex to match Pingo Doce counter.
    """
    soup = BeautifulSoup(html, "html.parser")

    # TODO: ajusta este selector ao counter real da página Pingo Doce
    counter_div = soup.select_one(".search-results-count, .results-count")
    if not counter_div:
        return None

    text = counter_div.get_text(strip=True)
    m = re.search(r"de\s+(\d+)\s+produtos", text)
    if not m:
        return None

    try:
        return int(m.group(1))
    except ValueError:
        return None

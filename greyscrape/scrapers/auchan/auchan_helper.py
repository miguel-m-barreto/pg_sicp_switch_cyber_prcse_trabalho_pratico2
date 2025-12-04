# greyscrape/scrapers/auchan/auchan_helper.py

import json
import re
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

BASE_URL = "https://www.auchan.pt"


def extract_products_from_html(html: str, run_timestamp: str) -> List[Dict]:
    """
    Parse one Auchan HTML page/fragment and extract product info.
    """
    soup = BeautifulSoup(html, "html.parser")
    produtos: List[Dict] = []

    for container in soup.select("div.product-tile.auc-product-tile"):
        gtm_new_raw = container.get("data-gtm-new")
        gtm_new = {}
        if gtm_new_raw:
            try:
                gtm_new = json.loads(gtm_new_raw)
            except json.JSONDecodeError:
                gtm_new = {}

        # Name and link
        nome_tag = container.select_one("div.auc-product-tile__name a")
        nome = (
            nome_tag.get_text(strip=True)
            if nome_tag
            else gtm_new.get("item_name", "")
        )

        link = ""
        if nome_tag and nome_tag.has_attr("href"):
            href = nome_tag["href"]
            if href.startswith("http"):
                link = href
            else:
                link = BASE_URL + href
        else:
            urls_raw = container.get("data-urls")
            if urls_raw:
                try:
                    urls = json.loads(urls_raw)
                    product_url = (
                        urls.get("absoluteProductUrl") or urls.get("productUrl")
                    )
                    if product_url:
                        link = product_url
                except json.JSONDecodeError:
                    pass

        # Minimum quantity
        quant_tag = container.select_one("span.auc-measures--avg-weight")
        quantidade_minima = quant_tag.get_text(strip=True) if quant_tag else None

        # Price per unit
        preco_unit_tag = container.select_one("span.auc-measures--price-per-unit")
        preco_unitario = (
            preco_unit_tag.get_text(strip=True) if preco_unit_tag else None
        )

        # Current price
        preco_tag = container.select_one("div.price span.sales span.value")
        if preco_tag:
            preco_text = preco_tag.get_text(strip=True)
            if preco_text:
                preco_atual = preco_text
            elif preco_tag.has_attr("content"):
                preco_atual = preco_tag["content"]
            else:
                preco_atual = None
        else:
            preco_atual = None

        # Old price
        preco_antigo_tag = container.select_one("span.strike-through.value")
        if preco_antigo_tag:
            preco_antigo_text = preco_antigo_tag.get_text(strip=True)
            if preco_antigo_text:
                preco_antigo = preco_antigo_text
            elif preco_antigo_tag.has_attr("content"):
                preco_antigo = preco_antigo_tag["content"]
            else:
                preco_antigo = None
        else:
            preco_antigo = None

        # Promotion
        promocao = None

        discount_badge = container.select_one(".auc-promo--discount--red")
        if discount_badge:
            promocao = discount_badge.get_text(strip=True)

        if not promocao:
            promo_label = container.select_one(".auc-price__promotion__label")
            if promo_label:
                promocao = promo_label.get_text(strip=True)

        if not promocao:
            old_promo_tag = container.select_one(
                "div.auc-promo--comarch__label--text"
            )
            if old_promo_tag:
                promocao = old_promo_tag.get_text(strip=True)

        produtos.append(
            {
                "nome": nome,
                "link": link,
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

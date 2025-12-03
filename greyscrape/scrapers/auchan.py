# scrapers/auchan.py
import time
from datetime import datetime
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def scrape_auchan(produto: Optional[str] = None) -> List[Dict]:
    """
    Scrape Auchan search results or landing page highlights.

    - If 'produto' is a non-empty string, hit the search page.
    - If 'produto' is empty or None, hit the landing page and
      scrape highlighted products (e.g. "Produtos em destaque").
    """

    produto = (produto or "").strip().lower()

    if produto.startswith("categoria"):
        if ":" in produto:
            categoria = produto.split(":", 1)[1].strip()
        elif "-" in produto:
            categoria = produto.split("-", 1)[1].strip()
        else:
            categoria = produto.split(" ", 1)[1].strip()

        url = f"https://www.auchan.pt/pt/{categoria}/"

    elif produto:
        url = (
            "https://www.auchan.pt/pt/pesquisa?"
            f"search-button=&q={produto}&lang=null"
        )

    else:
        # Landing page with highlighted products
        url = "https://www.auchan.pt/pt"

    options = Options()
    # Flags to run safely in headless/server environments
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Scroll to load products
    last_scroll = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_scroll = driver.execute_script("return window.pageYOffset;")
        if new_scroll == last_scroll:
            break
        last_scroll = new_scroll

    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    produtos: List[Dict] = []

    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for container in soup.select("div.auc-product-tile"):
        # Name and link
        nome_tag = container.select_one("div.auc-product-tile__name a")
        nome = nome_tag.get_text(strip=True) if nome_tag else ""
        link = "https://www.auchan.pt" + nome_tag["href"] if nome_tag else ""

        # Minimum quantity
        quant_tag = container.select_one("span.auc-measures--avg-weight")
        quantidade_minima = quant_tag.get_text(strip=True) if quant_tag else None

        # Price per unit
        preco_unit_tag = container.select_one("span.auc-measures--price-per-unit")
        preco_unit = preco_unit_tag.get_text(strip=True) if preco_unit_tag else None

        # Current price – prefer visible text ("2,99 €"), fallback to content
        preco_tag = container.select_one("div.price span.sales span.value")
        if preco_tag:
            preco_text = preco_tag.get_text(strip=True)
            if preco_text:
                preco = preco_text
            elif preco_tag.has_attr("content"):
                preco = preco_tag["content"]
            else:
                preco = None
        else:
            preco = None

        # Old price – same idea
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

        # Promo label
        promo_tag = container.select_one("div.auc-promo--comarch__label--text")
        promocao = promo_tag.get_text(strip=True) if promo_tag else None

        produtos.append(
            {
                "nome": nome,
                "link": link,
                "quantidade_minima": quantidade_minima,
                "preco_unitario": preco_unit,
                "preco_atual": preco,
                "preco_antigo": preco_antigo,
                "promocao": promocao,
                "data_execucao": run_timestamp,
            }
        )

    return produtos
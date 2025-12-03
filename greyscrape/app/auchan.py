# auchan.py
import time
from datetime import datetime
from typing import List, Dict

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def scrape_auchan(produto: str) -> List[Dict]:
    """
    Scrape Auchan search results for a given product/category.
    Returns a list of product dictionaries.
    """

    produto = produto.strip().lower()
    url = f"https://www.auchan.pt/pt/pesquisa?search-button=&q={produto}&lang=null"

    options = Options()
    # Flags para correr bem em servidor/headless
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Scroll para carregar todos os produtos (igual ao teu)
    ultimo_scroll = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        novo_scroll = driver.execute_script("return window.pageYOffset;")
        if novo_scroll == ultimo_scroll:
            break
        ultimo_scroll = novo_scroll

    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    produtos: List[Dict] = []

    data_execucao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for container in soup.select("div.auc-product-tile"):
        # Nome e link
        nome_tag = container.select_one("div.auc-product-tile__name a")
        nome = nome_tag.get_text(strip=True) if nome_tag else ""
        link = "https://www.auchan.pt" + nome_tag["href"] if nome_tag else ""

        # Quantidade mínima
        quant_tag = container.select_one("span.auc-measures--avg-weight")
        quantidade_minima = quant_tag.get_text(strip=True) if quant_tag else None

        # Preço por unidade
        preco_unit_tag = container.select_one("span.auc-measures--price-per-unit")
        preco_unit = preco_unit_tag.get_text(strip=True) if preco_unit_tag else None

        # Preço atual
        preco_tag = container.select_one("div.price span.sales span.value")
        preco = (
            preco_tag["content"]
            if preco_tag is not None and preco_tag.has_attr("content")
            else None
        )

        # Preço antigo
        preco_antigo_tag = container.select_one("span.strike-through.value")
        preco_antigo = (
            preco_antigo_tag["content"]
            if preco_antigo_tag is not None and preco_antigo_tag.has_attr("content")
            else None
        )

        # Promoção
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
                "data_execucao": data_execucao,
            }
        )

    return produtos

# scrapers/froiz.py
import time
from datetime import datetime
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_froiz(produto: Optional[str] = None) -> List[Dict]:
    """
    Scrape Froiz search results or landing-page highlights.

    - If 'produto' is non-empty: use search.php?q=...
    - If empty/None: use landing page and list highlighted products.
    """

    produto = (produto or "").strip().lower()

    if produto:
        url = f"https://loja.froiz.com/search.php?q={produto}"
    else:
        url = "https://loja.froiz.com/"

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Scroll + tentar clicar "Ver mais" se existir
    last_scroll = 0
    while True:
        try:
            ver_mais_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.more"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", ver_mais_btn)
            time.sleep(1)
            ver_mais_btn.click()
            time.sleep(2)
        except Exception:
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

    for container in soup.select("div.product-inner"):
        # Nome
        nome_tag = container.select_one("p.push-down-10.dproducto")
        nome = nome_tag.get_text(strip=True) if nome_tag else ""

        # Link absoluto
        link_tag = container.select_one("div.product-img a")
        link = (
            "https://loja.froiz.com/" + link_tag["href"]
            if link_tag and link_tag.has_attr("href")
            else ""
        )

        # Preço atual
        preco_tag = container.select_one("span.red-clr")
        preco_atual = preco_tag.get_text(strip=True) if preco_tag else None

        # Preço antigo
        preco_antigo_tag = container.select_one("span.striked small")
        preco_antigo = (
            preco_antigo_tag.get_text(strip=True) if preco_antigo_tag else None
        )

        # Preço por unidade
        preco_unit_tag = container.select_one("div.span8 small")
        preco_unitario = (
            preco_unit_tag.get_text(strip=True) if preco_unit_tag else None
        )

        produtos.append(
            {
                "nome": nome,
                "link": link,
                "quantidade_minima": None,
                "preco_unitario": preco_unitario,
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "promocao": None,
                "data_execucao": run_timestamp,
            }
        )

    return produtos

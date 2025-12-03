# scrapers/pingo_doce.py
import time
from datetime import datetime
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_pingo_doce(categoria: Optional[str] = None) -> List[Dict]:
    """
    Scrape Pingo Doce category results or landing-page highlights.

    - If 'categoria' is non-empty: /home/produtos/{categoria}
    - If empty/None: Pingo Doce homepage with featured products.
    """

    categoria = (categoria or "").strip().lower()

    if categoria:
        url = f"https://www.pingodoce.pt/home/produtos/{categoria}?"
    else:
        url = "https://www.pingodoce.pt/home/"

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Scroll + "Ver mais" se existir
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

    for container in soup.select("div.product"):
        # Nome + link
        a = container.select_one("div.product-name-link a")
        nome = a.get_text(strip=True) if a else ""
        link = (
            "https://www.pingodoce.pt" + a["href"]
            if a is not None and a.has_attr("href")
            else ""
        )

        # Preço atual
        preco_span = container.select_one("div.product-price span.sales")
        if preco_span:
            value_span = preco_span.select_one("span.value")
            if value_span and value_span.has_attr("content"):
                preco_atual = value_span["content"]
            else:
                preco_atual = preco_span.get_text(strip=True)
        else:
            preco_atual = None

        # Preço anterior
        preco_antigo_span = container.select_one("span.strike-through span.value")
        if preco_antigo_span and preco_antigo_span.has_attr("content"):
            preco_antigo = preco_antigo_span["content"]
        else:
            preco_antigo = (
                preco_antigo_span.get_text(strip=True)
                if preco_antigo_span
                else None
            )

        # Unidade (ex: €/kg, €/L) -> tratamos como "preco_unitario"
        unit_div = container.select_one("div.product-unit")
        preco_unitario = unit_div.get_text(strip=True) if unit_div else None

        # Promoção
        promo_span = container.select_one("span.promo-message")
        promocao = promo_span.get_text(strip=True) if promo_span else None

        produtos.append(
            {
                "nome": nome,
                "link": link,
                "quantidade_minima": None,
                "preco_unitario": preco_unitario,
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "promocao": promocao,
                "data_execucao": run_timestamp,
            }
        )

    return produtos

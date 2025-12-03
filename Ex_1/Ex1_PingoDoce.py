import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import sys
from datetime import datetime

# Pede a categoria ou usa argumento
categoria = sys.argv[1] if len(sys.argv) > 1 else input("Digite a categoria: ").strip().lower()

url = f"https://www.pingodoce.pt/home/produtos/{categoria}?"

options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
driver.get(url)

# Scroll e clicar 'Ver mais'
ultimo_scroll = 0
while True:
    try:
        ver_mais_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.more"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", ver_mais_btn)
        time.sleep(1)
        ver_mais_btn.click()
        time.sleep(2)
    except:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        novo_scroll = driver.execute_script("return window.pageYOffset;")
        if novo_scroll == ultimo_scroll:
            break
        ultimo_scroll = novo_scroll

html = driver.page_source
driver.quit()

soup = BeautifulSoup(html, "html.parser")
produtos = []

# Data de execução
data_execucao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for container in soup.select("div.product"):
    # Nome e link
    a = container.select_one("div.product-name-link a")
    nome = a.get_text(strip=True) if a else ""
    link = "https://www.pingodoce.pt" + a['href'] if a else ""

    # Preço atual
    preco_span = container.select_one("div.product-price span.sales")
    if preco_span:
        value_span = preco_span.select_one("span.value")
        preco = value_span["content"] if value_span and value_span.has_attr("content") else preco_span.get_text(strip=True)
    else:
        preco = None

    # Preço anterior
    preco_antigo_span = container.select_one("span.strike-through span.value")
    preco_anterior = preco_antigo_span["content"] if preco_antigo_span and preco_antigo_span.has_attr("content") else None

    # Unidade
    unit_div = container.select_one("div.product-unit")
    unidade = unit_div.get_text(strip=True) if unit_div else None

    # Promoção
    promo_span = container.select_one("span.promo-message")
    data_promocao = promo_span.get_text(strip=True) if promo_span else None

    produtos.append({
        "nome": nome,
        "link": link,
        "preco": preco,
        "preco_anterior": preco_anterior,
        "unidade": unidade,
        "data_promocao": data_promocao,
        "data_execucao": data_execucao  # <-- adiciona a data de execução
    })

# Salva em JSON
arquivo_json = f"pingo_doce_{categoria}.json"
with open(arquivo_json, "w", encoding="utf-8") as f:
    json.dump(produtos, f, ensure_ascii=False, indent=4)

print(f"{len(produtos)} produtos salvos em {arquivo_json} na data {data_execucao}")

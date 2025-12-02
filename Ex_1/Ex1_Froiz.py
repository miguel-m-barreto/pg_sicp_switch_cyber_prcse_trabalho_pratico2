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

# Produto ou categoria
produto = sys.argv[1] if len(sys.argv) > 1 else input("Digite o produto: ").strip().lower()

url = f"https://loja.froiz.com/search.php?q={produto}"

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

for container in soup.select("div.product-inner"):
    # Nome
    nome_tag = container.select_one("p.push-down-10.dproducto")
    nome = nome_tag.get_text(strip=True) if nome_tag else ""

    # Link
    link_tag = container.select_one("div.product-img a")
    link = "https://loja.froiz.com/" + link_tag['href'] if link_tag else ""

    # Preço atual
    preco_tag = container.select_one("span.red-clr")
    preco = preco_tag.get_text(strip=True) if preco_tag else None

    # Preço antigo
    preco_antigo_tag = container.select_one("span.striked small")
    preco_antigo = preco_antigo_tag.get_text(strip=True) if preco_antigo_tag else None

    # Preço por unidade
    preco_unit_tag = container.select_one("div.span8 small")
    preco_unit = preco_unit_tag.get_text(strip=True) if preco_unit_tag else None

    produtos.append({
        "nome": nome,
        "link": link,
        "preco_atual": preco,
        "preco_antigo": preco_antigo,
        "preco_unidade": preco_unit,
        "data_execucao": data_execucao  # <-- adiciona a data
    })

# Salva em JSON
arquivo_json = f"froiz_{produto}.json"
with open(arquivo_json, "w", encoding="utf-8") as f:
    json.dump(produtos, f, ensure_ascii=False, indent=4)

print(f"{len(produtos)} produtos salvos em {arquivo_json} na data {data_execucao}")

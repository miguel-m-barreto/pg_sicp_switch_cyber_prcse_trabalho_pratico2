# greyscrape/scrapers/pingo_doce/pingo_doce_extract_sub_categories.py

import os
import json
import time
from typing import List, Set

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.pingodoce.pt"
START_URL = f"{BASE_URL}/home/produtos"

# Pasta onde guarda o JSON
LINK_DIR_NAME = "links"


def _build_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)


def _normalize_url(href: str) -> str:
    if not href: return ""
    href = href.strip()
    if href.startswith("/"): href = BASE_URL + href
    if not href.startswith(f"{BASE_URL}/home/produtos"): return ""
    href = href.split("?", 1)[0].split("#", 1)[0]
    if href.endswith("/"): href = href[:-1]
    return href


def _extract_subcategory_urls(html: str) -> List[str]:
    """
    Agrupar URLs de Pingo Doce ao nível de sub-categoria.

    Estrutura (parts depois do domínio):
      parts[0] = "home"
      parts[1] = "produtos"
      parts[2] = categoria principal       (ex: "bebidas")
      parts[3] = sub-categoria             (ex: "agua")

    Regra:
      - Se houver subcategorias (depth >= 4), guardamos APENAS as subcategorias (nivel 4):
          /home/produtos/bebidas/agua
      - Se NÃO houver subcategorias para uma categoria, guardamos a categoria:
          /home/produtos/frutas-e-vegetais
    """
    soup = BeautifulSoup(html, "html.parser")

    depth3_candidates: Set[str] = set()  # /home/produtos/<cat>
    depth4_urls: Set[str] = set()        # /home/produtos/<cat>/<subcat> (alvo principal)

    for a in soup.select('a[href^="/home/produtos/"]'):
        raw = a.get("href") or ""

        # Ignorar páginas de produto
        if "/p/" in raw or raw.endswith(".html"):
            continue

        href = _normalize_url(raw)
        if not href:
            continue

        if href == START_URL:
            continue

        path = href.replace(BASE_URL, "")
        parts = [p for p in path.split("/") if p]

        # Esperamos pelo menos ["home", "produtos", "<cat>"]
        if len(parts) < 3:
            continue

        # Categoria principal: /home/produtos/<cat>
        if len(parts) == 3:
            depth3_candidates.add(href)
            continue

        # Mais fundo: /home/produtos/<cat>/<subcat>/... -> cortamos ao nível 4
        # parts[:4] = ["home", "produtos", "<cat>", "<subcat>"]
        truncated_path = "/".join(parts[:4])
        new_url = f"{BASE_URL}/{truncated_path}"
        depth4_urls.add(new_url)

    # Agora decidimos o conjunto final:
    # 1) Começamos com todas as subcategorias (depth 4).
    final_urls: Set[str] = set(depth4_urls)

    # 2) Para cada categoria principal (depth 3), só a mantemos se NÃO tiver filhos.
    for parent in depth3_candidates:
        has_child = any(u.startswith(parent + "/") for u in depth4_urls)
        if not has_child:
            final_urls.add(parent)

    print(f"[Debug] URLs finais (só subcats + categorias sem filhos): {len(final_urls)}")
    return sorted(final_urls)


def _save_links(urls: List[str]) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    link_dir = os.path.join(base_dir, LINK_DIR_NAME)
    os.makedirs(link_dir, exist_ok=True)
    path = os.path.join(link_dir, "pingo_doce_sub_categories.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)
    return path


def main() -> None:
    print(f"[Pingo_Doce][SubCats] Fetching menu from {START_URL}")
    driver = _build_driver()
    try:
        driver.get(START_URL)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href^="/home/produtos/"]'))
            )
            time.sleep(3)
        except Exception:
            print("[Warning] Timeout à espera de links, a tentar ler HTML mesmo assim.")

        html = driver.page_source
        urls = _extract_subcategory_urls(html)

        path = _save_links(urls)
        print(f"[Pingo_Doce][SubCats] SUCESSO! {len(urls)} categorias agregadas guardadas em:")
        print(f" -> {path}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
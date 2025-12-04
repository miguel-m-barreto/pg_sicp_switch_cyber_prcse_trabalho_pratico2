# scrapers/auchan.py
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_URL = "https://www.auchan.pt"


def _extract_products_from_html(html: str, run_timestamp: str) -> List[Dict]:
    """Parse one Auchan HTML page/fragment and extract product info."""
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
        nome = nome_tag.get_text(strip=True) if nome_tag else gtm_new.get("item_name", "")

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
                    product_url = urls.get("absoluteProductUrl") or urls.get("productUrl")
                    if product_url:
                        link = product_url
                except json.JSONDecodeError:
                    pass

        # Minimum quantity
        quant_tag = container.select_one("span.auc-measures--avg-weight")
        quantidade_minima = quant_tag.get_text(strip=True) if quant_tag else None

        # Price per unit
        preco_unit_tag = container.select_one("span.auc-measures--price-per-unit")
        preco_unitario = preco_unit_tag.get_text(strip=True) if preco_unit_tag else None

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
            old_promo_tag = container.select_one("div.auc-promo--comarch__label--text")
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


def _scroll_to_bottom(driver, max_tries: int = 10, wait: float = 1.5) -> None:
    """Scroll until no new content is loaded (for search / landing)."""
    last_height = driver.execute_script("return document.body.scrollHeight;")
    stagnant = 0

    for _ in range(max_tries):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)
        new_height = driver.execute_script("return document.body.scrollHeight;")

        if new_height == last_height:
            stagnant += 1
            if stagnant >= 2:
                break
        else:
            stagnant = 0
            last_height = new_height


def _scrape_category_with_api_and_selenium(
    driver, categoria_slug: str, run_timestamp: str
) -> List[Dict]:
    """
    Scrape a category:
      1) parse the main category page (first N products)
      2) then hit Search-UpdateGrid with the same Selenium session for the rest.
    """
    # 1) Load main category page and extract initial products
    category_url = f"{BASE_URL}/pt/{categoria_slug}/"
    driver.get(category_url)
    time.sleep(2)

    html = driver.page_source
    all_products = _extract_products_from_html(html, run_timestamp)
    seen_links = {p.get("link") for p in all_products if p.get("link")}

    # Number already obtained (this matches the "1–96 de 115 resultados" logic)
    start = len(all_products)

    # 2) Paginated chunks via Search-UpdateGrid in the SAME session
    api_base = (
        f"{BASE_URL}/on/demandware.store/"
        "Sites-AuchanPT-Site/pt_PT/Search-UpdateGrid"
    )

    sz = 24  # the site uses 24 in the requests you captured

    while True:
        params = {
            "cgid": categoria_slug,
            # replicate the filter used in your captures
            "prefn1": "soldInStores",
            "prefv1": "000",
            "start": start,
            "sz": sz,
            "next": "true",
        }
        api_url = f"{api_base}?{urlencode(params)}"

        driver.get(api_url)
        time.sleep(1.5)

        page_html = driver.page_source
        page_products = _extract_products_from_html(page_html, run_timestamp)

        if not page_products:
            break

        added = 0
        for p in page_products:
            link = p.get("link")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            all_products.append(p)
            added += 1

        if added < sz:
            # last chunk
            break

        start += added

    return all_products


def scrape_auchan(produto: Optional[str] = None) -> List[Dict]:
    """
    Scrape Auchan search results, category pages or landing page.

    - 'categoria:pao-embalado-1-1' -> category via main page + Search-UpdateGrid (all items)
    - 'categoria:marcas-auchan'    -> same
    - 'arroz'                      -> search page (selenium + scroll)
    - None/""                      -> landing page (selenium + scroll).
    """
    produto = (produto or "").strip().lower()
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")  # safe filename

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    try:
        # CATEGORY MODE
        if produto.startswith("categoria"):
            if ":" in produto:
                categoria = produto.split(":", 1)[1].strip()
            elif "-" in produto:
                categoria = produto.split("-", 1)[1].strip()
            else:
                categoria = produto.split(" ", 1)[1].strip()

            produtos = _scrape_category_with_api_and_selenium(
                driver, categoria, run_timestamp
            )

            # PRINT TOTAL
            print(f"[Auchan] CATEGORY '{categoria}' → fetched {len(produtos)} items")

            # SAVE JSON
            dump_path = f"auchan_dump_{categoria}_{run_timestamp}.json"
            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(produtos, f, ensure_ascii=False, indent=2)
            print(f"[Auchan] Saved dump → {dump_path}")

            return produtos

        # SEARCH / LANDING MODE
        if produto:
            url = (
                f"{BASE_URL}/pt/pesquisa?"
                f"search-button=&q={produto}&lang=null"
            )
        else:
            url = f"{BASE_URL}/pt"

        driver.get(url)
        _scroll_to_bottom(driver)

        html = driver.page_source
        produtos = _extract_products_from_html(html, run_timestamp)

        # basic dedup just in case
        seen_links = set()
        unique_produtos: List[Dict] = []
        for p in produtos:
            link = p.get("link")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            unique_produtos.append(p)

        # PRINT TOTAL
        mode = "search" if produto else "landing"
        print(f"[Auchan] {mode.upper()} '{produto}' → fetched {len(unique_produtos)} items")

        # SAVE JSON
        dump_path = f"auchan_dump_{mode}_{run_timestamp}.json"
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(unique_produtos, f, ensure_ascii=False, indent=2)
        print(f"[Auchan] Saved dump → {dump_path}")

        return unique_produtos

    finally:
        driver.quit()

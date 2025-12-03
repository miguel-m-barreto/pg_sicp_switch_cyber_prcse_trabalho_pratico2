# scrapers/__init__.py
from typing import List, Dict, Callable, Optional

from .auchan import scrape_auchan
from .froiz import scrape_froiz
from .pingo_doce import scrape_pingo_doce

ScraperFunc = Callable[[Optional[str]], List[Dict]]

SCRAPERS: dict[str, ScraperFunc] = {
    "auchan": scrape_auchan,
    "froiz": scrape_froiz,
    "pingo_doce": scrape_pingo_doce,
}


def run_scraper(store: str, query: str | None) -> List[Dict]:
    """
    Dispatch to the appropriate scraper based on the store name.

    - store: id da loja, e.g. "auchan", "froiz", "pingo_doce"
    - query: termo de pesquisa ou string vazia -> landing page
    """
    key = store.strip().lower()
    if key not in SCRAPERS:
        raise ValueError(f"Unsupported store: {store}")

    # Normalizar: "" ou só espaços -> None (landing page)
    q = query if query is not None and query.strip() != "" else None
    return SCRAPERS[key](q)

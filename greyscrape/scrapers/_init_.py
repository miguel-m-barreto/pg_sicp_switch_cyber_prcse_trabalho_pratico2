from typing import List, Dict, Callable

from scrapers.auchan import scrape_auchan
from scrapers.froiz import scrape_froiz
from scrapers.pingo_doce import scrape_pingo_doce

ScraperFunc = Callable[[str], List[Dict]]

SCRAPERS: dict[str, ScraperFunc] = {
    "auchan": scrape_auchan,
    "froiz": scrape_froiz,
    "pingo_doce": scrape_pingo_doce,
}


def run_scraper(store: str, query: str) -> List[Dict]:
    """
    Dispatch to the appropriate scraper based on the store name.
    """
    key = store.strip().lower()
    if key not in SCRAPERS:
        raise ValueError(f"Unsupported store: {store}")
    return SCRAPERS[key](query)

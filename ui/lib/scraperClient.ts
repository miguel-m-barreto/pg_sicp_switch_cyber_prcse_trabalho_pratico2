// lib/scraperClient.ts

const BASE_URL = process.env.SCRAPER_BASE_URL;

if (!BASE_URL) {
  throw new Error("SCRAPER_BASE_URL is not set");
}

export type AuchanItem = {
  nome: string;
  link: string;
  quantidade_minima?: string | null;
  preco_unitario?: string | null;
  preco_atual?: string | null;
  preco_antigo?: string | null;
  promocao?: string | null;
  data_execucao?: string;
};

export type ScrapeResponse = {
  store: string;
  query: string;
  count: number;
  items: AuchanItem[];
};

export async function scrapeAuchan(query: string): Promise<ScrapeResponse> {
  const url = `${BASE_URL}/scrape?store=auchan&query=${encodeURIComponent(
    query
  )}`;

  const res = await fetch(url, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Scrape failed with status ${res.status}`);
  }

  return res.json();
}

// lib/scraperClient.ts

const BASE_URL = process.env.SCRAPER_BASE_URL;

if (!BASE_URL) {
  throw new Error("SCRAPER_BASE_URL is not set");
}

export const SUPPORTED_STORES = ["auchan", "froiz", "pingo_doce"] as const;
export type StoreId = (typeof SUPPORTED_STORES)[number];

export type Item = {
  nome: string;
  link: string;
  quantidade_minima?: string | null;
  preco_unitario?: string | null;
  preco_atual?: string | null;
  preco_antigo?: string | null;
  promocao?: string | null;
  data_execucao?: string;
  // VER QUE OUTROS CAMPOS PRECISAM DE APARECER AQUI PARA AS VARIAS LOJAS
  [key: string]: unknown;
};

export type ScrapeResponse = {
  store: string;
  query: string;
  count: number;
  items: Item[];
};

export async function scrapeStore(
  store: StoreId,
  query: string
): Promise<ScrapeResponse> {
  const url = `${BASE_URL}/scrape?store=${encodeURIComponent(
    store
  )}&query=${encodeURIComponent(query)}`;

  const res = await fetch(url, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Scrape failed with status ${res.status}`);
  }

  return res.json();
}

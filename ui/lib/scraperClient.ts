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

  // DEBUG: ver exatamente o que o frontend está a pedir
  console.log("[scrapeStore] GET", url, "query=", JSON.stringify(query));

  const res = await fetch(url, {
    cache: "no-store",
  });

  // DEBUG: status + corpo em caso de erro
  if (!res.ok) {
    let body = "";
    try {
      body = await res.text();
    } catch {
      body = "<no body>";
    }

    console.error(
      "[scrapeStore] FAILED",
      res.status,
      res.statusText,
      "body=",
      body
    );

    throw new Error(`Scrape failed with status ${res.status}`);
  }

  console.log("[scrapeStore] OK", res.status);

  return res.json();
}

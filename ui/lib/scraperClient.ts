// ui/lib/scraperClient.ts
// Server-side data access for store items (Supabase).

import { supabaseServer } from "@/lib/supabaseServer";

export const SUPPORTED_STORES = ["auchan", "pingo_doce", "froiz"] as const;
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
};

export type PagedItemsResult = {
  items: Item[];
  totalCount: number;
};

// Sort options to be used by API and UI
export type SortField = "nome" | "preco" | "preco_unitario";
export type SortDir = "asc" | "desc";

/**
 * Resolve numeric store_id used in Supabase from the StoreId string.
 * Uses the same env vars as the Python scraper.
 */
function resolveStoreNumericId(store: StoreId): number {
  const envMap: Record<StoreId, string> = {
    auchan: "SUPABASE_AUCHAN_STORE_ID",
    pingo_doce: "SUPABASE_PINGO_DOCE_STORE_ID",
    froiz: "SUPABASE_FROIZ_STORE_ID",
  };

  const envName = envMap[store];
  const raw = process.env[envName];
  if (!raw) {
    throw new Error(`Missing env var ${envName} for store '${store}'`);
  }

  const id = Number(raw);
  if (!Number.isFinite(id)) {
    throw new Error(`Invalid numeric value in ${envName}: '${raw}'`);
  }

  return id;
}

/**
 * Fetch a page of products for a store, optionally filtered by search query
 * and sorted by one of the allowed fields.
 *
 * Calls the Postgres function `get_store_products` with parameters:
 *  - p_store_id
 *  - p_search
 *  - p_limit
 *  - p_offset
 *  - p_sort_field
 *  - p_sort_dir
 *  - p_only_promo
 *  - p_category
 *  - p_brand
 */
export async function fetchStoreItemsPage(
  store: StoreId,
  query: string,
  offset: number,
  limit: number,
  sortField: SortField = "nome",
  sortDir: SortDir = "asc"
): Promise<PagedItemsResult> {
  const storeId = resolveStoreNumericId(store);
  const trimmed = (query ?? "").trim();

  const { data, error } = await supabaseServer.rpc("get_store_products", {
    p_store_id: storeId,
    p_search: trimmed || null,
    p_limit: limit,
    p_offset: offset,
    p_sort_field: sortField,
    p_sort_dir: sortDir,
    p_only_promo: false,
    p_category: null,
    p_brand: null,
  });

  if (error) {
    throw new Error(`Supabase error: ${error.message}`);
  }
  if (!data) {
    return { items: [], totalCount: 0 };
  }

  const rows = data as any[];
  if (rows.length === 0) {
    return { items: [], totalCount: 0 };
  }

  const total = Number(rows[0].total_count) || rows.length;

  const items: Item[] = rows.map((row) => {
    const raw = (row.raw_json || {}) as any;

    const nome: string =
      raw.nome ?? (row.raw_name as string | undefined) ?? "";

    const link: string =
      raw.link ?? (row.product_url as string | undefined) ?? "";

    const preco_atual: string | null =
      raw.preco_atual ??
      (row.price != null ? `${Number(row.price).toFixed(2)} €` : null);

    const preco_antigo: string | null =
      raw.preco_antigo ??
      (row.old_price != null ? `${Number(row.old_price).toFixed(2)} €` : null);

    const preco_unitario: string | null =
      raw.preco_unitario ??
      (row.unit_price != null
        ? `${Number(row.unit_price).toFixed(2)} €/unit`
        : null);

    const quantidade_minima: string | null =
      raw.quantidade_minima ?? (row.quantity as string | undefined) ?? null;

    const promocao: string | null =
      raw.promocao ?? (row.promo_label as string | undefined) ?? null;

    return {
      nome,
      link,
      quantidade_minima,
      preco_unitario,
      preco_atual,
      preco_antigo,
      promocao,
      data_execucao: row.scraped_at as string,
    };
  });

  return { items, totalCount: total };
}

/**
 * Small helper used by the dashboard overview page:
 * fetch a small sample (first N items) for a store.
 */
export async function scrapeStore(
  store: StoreId,
  query: string
): Promise<PagedItemsResult> {
  // 5 items is enough for the overview cards; change if you want
  return fetchStoreItemsPage(store, query, 0, 5, "nome", "asc");
}

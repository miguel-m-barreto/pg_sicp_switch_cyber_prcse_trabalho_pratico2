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

  // extra metadata for tiles
  image_url?: string | null;
  brand?: string | null;
  category_human_1?: string | null;
};

export type PagedItemsResult = {
  items: Item[];
  totalCount: number;
};

// Sort options to be used by API and UI
export type SortField = "nome" | "preco" | "preco_unitario";
export type SortDir = "asc" | "desc";

// Promotions sort
export type PromoSortField = "discount_pct" | "discount_abs" | "preco";
export type PromoSortDir = "asc" | "desc";

export type StoreCategory = {
  category_human_1: string;
  total_products: number;
  total_on_promotion: number;
};

export type StoreBrand = {
  brand: string;
  total_variants: number;
  total_on_promotion: number;
};

export type PromotionItem = Item & {
  discount_abs?: string | null;
  discount_pct?: string | null;
  discount_raw_value: number;
  discount_raw_pct: number;
};

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
 * Helper to format euros with 2 decimals.
 */
function formatEuro(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(Number(value))) return null;
  return `${Number(value).toFixed(2)} €`;
}

/**
 * Helper to format discount percentage when DB returns 0–1.
 */
function formatPercent01(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(Number(value))) return null;
  return `${(Number(value) * 100).toFixed(0)}%`;
}

/**
 * Helper to format discount percentage when DB returns 0–100.
 */
function formatPercent100(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(Number(value))) return null;
  return `${Number(value).toFixed(0)}%`;
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
  sortDir: SortDir = "asc",
  options?: {
    onlyPromo?: boolean;
    category?: string | null;
    brand?: string | null;
  }
): Promise<PagedItemsResult> {
  const storeId = resolveStoreNumericId(store);
  const trimmed = (query ?? "").trim();

  const { onlyPromo = false, category = null, brand = null } = options ?? {};

  const { data, error } = await supabaseServer.rpc("get_store_products", {
    p_store_id: storeId,
    p_search: trimmed || null,
    p_limit: limit,
    p_offset: offset,
    p_sort_field: sortField,
    p_sort_dir: sortDir,
    p_only_promo: onlyPromo,
    p_category: category && category.trim() !== "" ? category : null,
    p_brand: brand && brand.trim() !== "" ? brand : null,
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
      raw.preco_atual ?? formatEuro(row.final_price ?? row.price ?? null);

    const preco_antigo: string | null =
      raw.preco_antigo ?? formatEuro(row.old_price ?? null);

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
      image_url: row.image_url ?? null,
      brand: row.brand ?? null,
      category_human_1: row.category_human_1 ?? null,
    };
  });

  return { items, totalCount: total };
}

/**
 * Small helper used by the dashboard overview page in the past:
 * kept for backwards-compatibility, currently just first 5 products.
 */
export async function scrapeStore(
  store: StoreId,
  query: string
): Promise<PagedItemsResult> {
  return fetchStoreItemsPage(store, query, 0, 5, "nome", "asc");
}

/**
 * Fetch categories for a store (for filters).
 * Uses get_store_categories.
 */
export async function fetchStoreCategories(
  store: StoreId,
  opts?: { query?: string; brand?: string | null; onlyPromo?: boolean }
): Promise<StoreCategory[]> {
  const storeId = resolveStoreNumericId(store);
  const { query, brand, onlyPromo = false } = opts ?? {};

  const { data, error } = await supabaseServer.rpc("get_store_categories", {
    p_store_id: storeId,
    p_search: query && query.trim() !== "" ? query : null,
    p_brand: brand && brand.trim() !== "" ? brand : null,
    p_only_promo: onlyPromo,
  });

  if (error) {
    throw new Error(`Supabase error (get_store_categories): ${error.message}`);
  }

  if (!data) return [];

  return (data as any[]).map((row) => ({
    category_human_1: row.category_human_1 as string,
    total_products: Number(row.total_products ?? 0),
    total_on_promotion: Number(row.total_on_promotion ?? 0),
  }));
}


/**
 * Fetch brands for a store, optionally filtered by category.
 * Uses get_store_brands.
 */
export async function fetchStoreBrands(
  store: StoreId,
  category: string | null
): Promise<StoreBrand[]> {
  const storeId = resolveStoreNumericId(store);

  const { data, error } = await supabaseServer.rpc("get_store_brands", {
    p_store_id: storeId,
    p_category: category && category.trim() !== "" ? category : null,
  });

  if (error) {
    throw new Error(`Supabase error (get_store_brands): ${error.message}`);
  }

  if (!data) return [];
  return (data as any[]).map((row) => ({
    brand: row.brand as string,
    total_variants: Number(row.total_variants ?? 0),
    total_on_promotion: Number(row.total_on_promotion ?? 0),
  }));
}

/**
 * Fetch promotions for a single store (for tiles and carrossel).
 * Uses get_store_promotions.
 */
export async function fetchStorePromotions(
  store: StoreId,
  {
    offset = 0,
    limit = 32,
    sortField = "discount_pct",
    sortDir = "desc",
    category = null,
    brand = null,
    minDiscountPct = null,
  }: {
    offset?: number;
    limit?: number;
    sortField?: PromoSortField;
    sortDir?: PromoSortDir;
    category?: string | null;
    brand?: string | null;
    minDiscountPct?: number | null; // 10 => 10%
  } = {}
): Promise<{ items: PromotionItem[]; totalCount: number }> {
  const storeId = resolveStoreNumericId(store);

  const { data, error } = await supabaseServer.rpc("get_store_promotions", {
    p_store_id: storeId,
    p_limit: limit,
    p_offset: offset,
    p_sort_field: sortField,
    p_sort_dir: sortDir,
    p_category: category && category.trim() !== "" ? category : null,
    p_brand: brand && brand.trim() !== "" ? brand : null,
    p_min_discount_pct: minDiscountPct,
  });

  if (error) {
    throw new Error(`Supabase error (get_store_promotions): ${error.message}`);
  }
  if (!data) {
    return { items: [], totalCount: 0 };
  }

  const rows = data as any[];
  if (rows.length === 0) {
    return { items: [], totalCount: 0 };
  }

  const total = Number(rows[0].total_count) || rows.length;

  const items: PromotionItem[] = rows.map((row) => {
    const raw = (row.raw_json || {}) as any;

    const nome: string =
      raw.nome ?? (row.raw_name as string | undefined) ?? "";

    const link: string =
      raw.link ?? (row.product_url as string | undefined) ?? "";

    const price = row.final_price ?? row.price ?? null;
    const oldPrice = row.old_price ?? null;

    const preco_atual = formatEuro(price);
    const preco_antigo = formatEuro(oldPrice);

    const discount_abs_raw: number = Number(row.discount_abs ?? 0);
    const discount_pct_raw: number = Number(row.discount_pct ?? 0);

    return {
      nome,
      link,
      preco_atual,
      preco_antigo,
      preco_unitario:
        row.unit_price != null
          ? `${Number(row.unit_price).toFixed(2)} €/unit`
          : null,
      quantidade_minima: (row.quantity as string | undefined) ?? null,
      promocao: row.promo_label ?? null,
      data_execucao: row.scraped_at as string,
      image_url: row.image_url ?? null,
      brand: row.brand ?? null,
      category_human_1: row.category_human_1 ?? null,
      discount_abs: formatEuro(discount_abs_raw),
      discount_pct: formatPercent01(discount_pct_raw),
      discount_raw_value: discount_abs_raw,
      discount_raw_pct: discount_pct_raw,
    };
  });

  return { items, totalCount: total };
}

/**
 * Fetch top promotions for all stores.
 * Uses get_all_store_promotions.
 * Ideal for the overview /dashboard page.
 */
export async function fetchAllStoresPromotions(
  limitPerStore: number
): Promise<Record<StoreId, PromotionItem[]>> {
  const stores: StoreId[] = ["auchan", "pingo_doce", "froiz"];

  const results = await Promise.all(
    stores.map(async (storeId) => {
      try {
        const { items } = await fetchStorePromotions(storeId, {
          limit: limitPerStore,
          sortField: "discount_pct",
          sortDir: "desc",
          minDiscountPct: null,
        });

        return { storeId, items };
      } catch {
        return { storeId, items: [] as PromotionItem[] };
      }
    })
  );

  const byStore: Record<StoreId, PromotionItem[]> = {
    auchan: [],
    pingo_doce: [],
    froiz: [],
  };

  for (const { storeId, items } of results) {
    byStore[storeId] = items;
  }

  return byStore;
}


export async function fetchStorePromotionsByCategory(
  store: StoreId,
  perCategory: number,
  {
    sortField = "discount_pct",
    sortDir = "desc",
    category = null,
    brand = null,
    minDiscountPct = null,
  }: {
    sortField?: PromoSortField;
    sortDir?: PromoSortDir;
    category?: string | null;
    brand?: string | null;
    minDiscountPct?: number | null;
  } = {}
): Promise<{ items: PromotionItem[]; totalCount: number }> {
  const storeId = resolveStoreNumericId(store);

  const { data, error } = await supabaseServer.rpc(
    "get_store_promotions_by_category",
    {
      p_store_id: storeId,
      p_per_category: perCategory,
      p_sort_field: sortField,
      p_sort_dir: sortDir,
      p_category:
        category && category.trim() !== "" ? category : null,
      p_brand: brand && brand.trim() !== "" ? brand : null,
      p_min_discount_pct: minDiscountPct,
    }
  );

  if (error) {
    throw new Error(
      `Supabase error (get_store_promotions_by_category): ${error.message}`
    );
  }

  if (!data) {
    return { items: [], totalCount: 0 };
  }

  const rows = data as any[];
  if (rows.length === 0) {
    return { items: [], totalCount: 0 };
  }

  const total = Number(rows[0].total_count) || rows.length;

  const items: PromotionItem[] = rows.map((row) => {
    const raw = (row.raw_json || {}) as any;

    const nome: string =
      raw.nome ?? (row.raw_name as string | undefined) ?? "";

    const link: string =
      raw.link ?? (row.product_url as string | undefined) ?? "";

    const price = row.final_price ?? row.price ?? null;
    const oldPrice = row.old_price ?? null;

    const preco_atual = formatEuro(price);
    const preco_antigo = formatEuro(oldPrice);

    const discount_abs_raw: number = Number(row.discount_abs ?? 0);
    const discount_pct_raw: number = Number(row.discount_pct ?? 0);

    return {
      nome,
      link,
      preco_atual,
      preco_antigo,
      preco_unitario:
        row.unit_price != null
          ? `${Number(row.unit_price).toFixed(2)} €/unit`
          : null,
      quantidade_minima: (row.quantity as string | undefined) ?? null,
      promocao: row.promo_label ?? null,
      data_execucao: row.scraped_at as string,
      image_url: row.image_url ?? null,
      brand: row.brand ?? null,
      category_human_1: row.category_human_1 ?? null,
      discount_abs: formatEuro(discount_abs_raw),
      discount_pct: formatPercent01(discount_pct_raw),
      discount_raw_value: discount_abs_raw,
      discount_raw_pct: discount_pct_raw,
    };
  });

  return { items, totalCount: total };
}

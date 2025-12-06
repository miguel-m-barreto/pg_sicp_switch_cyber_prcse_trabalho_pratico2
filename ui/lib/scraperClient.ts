// ui/lib/scraperClient.ts
// Frontend "scraper client" now reads from Supabase instead of calling Python.

import { supabaseServer } from "./supabaseServer";

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

/**
 * Resolve numeric store_id used in Supabase from the StoreId string.
 * Uses the same env vars as the Python scraper.
 */
function resolveStoreNumericId(store: StoreId): number {
  let envName: string;

  switch (store) {
    case "auchan":
      envName = "SUPABASE_AUCHAN_STORE_ID";
      break;
    case "froiz":
      envName = "SUPABASE_FROIZ_STORE_ID";
      break;
    case "pingo_doce":
      envName = "SUPABASE_PINGO_DOCE_STORE_ID";
      break;
    default:
      throw new Error(`Unsupported store '${store}'`);
  }

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
 * Fetch latest product state for a store from Supabase.
 *
 * Semantics:
 *  - Returns one "current" snapshot per active variant (dedup by variant_id).
 *  - Optional text search on product name (raw_name) using ILIKE.
 *  - Keeps the same shape ScrapeResponse/Item as when we were calling Python.
 */
export async function scrapeStore(
  store: StoreId,
  query: string
): Promise<ScrapeResponse> {
  const storeNumericId = resolveStoreNumericId(store);
  const trimmedQuery = (query ?? "").trim();

  // Base query: latest snapshots joined with product_variants and products
  // We ask for:
  //  - snapshot: price fields + scraped_at + raw_json
  //  - product_variants: name, URL, quantity, is_active
  //  - products: store_id, is_active, deleted_at
  let q = supabaseServer
    .from("product_snapshots")
    .select(
      `
        id,
        variant_id,
        price,
        old_price,
        unit_price,
        currency,
        promo_label,
        stock_status,
        scraped_at,
        raw_json,
        product_variants!inner (
          id,
          product_url,
          raw_name,
          normalized_name,
          quantity,
          is_active
        ),
        products!inner (
          id,
          store_id,
          external_id,
          is_active,
          deleted_at
        )
      `
    )
    // Ensure we are only looking at this store
    .eq("products.store_id", storeNumericId)
    // Only active products / variants
    .eq("products.is_active", true)
    .is("products.deleted_at", null)
    .eq("product_variants.is_active", true)
    // Newest snapshots first
    .order("scraped_at", { ascending: false })
    // Hard limit: we dedup in memory later, so we can fetch a bit more
    .limit(800);

  // Optional search on product name
  if (trimmedQuery.length > 0) {
    const pattern = `%${trimmedQuery}%`;
    q = q.ilike("product_variants.raw_name", pattern);
  }

  const { data, error } = await q;

  if (error) {
    throw new Error(`Supabase error: ${error.message}`);
  }

  if (!data || data.length === 0) {
    return {
      store,
      query: trimmedQuery,
      count: 0,
      items: [],
    };
  }

  // Deduplicate: keep the first snapshot per variant_id (because we ordered desc)
  const seenVariantIds = new Set<number>();
  const items: Item[] = [];

  for (const row of data as any[]) {
    const variantId: number | undefined = row.variant_id;
    if (!variantId) {
      continue;
    }
    if (seenVariantIds.has(variantId)) {
      continue;
    }
    seenVariantIds.add(variantId);

    const snap = row;
    const variant = snap.product_variants || {};
    const raw = (snap.raw_json || {}) as Record<string, unknown>;

    // Prefer raw_json strings (exact original from scraper), fallback to parsed values
    const priceNow =
      (raw.preco_atual as string | undefined) ??
      (snap.price != null ? `${Number(snap.price).toFixed(2)} €` : null);

    const priceOld =
      (raw.preco_antigo as string | undefined) ??
      (snap.old_price != null ? `${Number(snap.old_price).toFixed(2)} €` : null);

    const unitPrice =
      (raw.preco_unitario as string | undefined) ??
      (snap.unit_price != null ? `${Number(snap.unit_price).toFixed(2)} €/unit` : null);

    const nome =
      (raw.nome as string | undefined) ??
      (variant.raw_name as string | undefined) ??
      "";

    const link =
      (raw.link as string | undefined) ??
      (variant.product_url as string | undefined) ??
      "";

    const quantidadeMinima =
      (raw.quantidade_minima as string | undefined) ??
      (variant.quantity as string | undefined) ??
      null;

    const promocao =
      (raw.promocao as string | undefined) ??
      (snap.promo_label as string | undefined) ??
      null;

    const scrapedAt: string = snap.scraped_at as string;

    items.push({
      nome,
      link,
      quantidade_minima: quantidadeMinima,
      preco_unitario: unitPrice,
      preco_atual: priceNow,
      preco_antigo: priceOld,
      promocao,
      data_execucao: scrapedAt,
    });
  }

  return {
    store,
    query: trimmedQuery,
    count: items.length,
    items,
  };
}

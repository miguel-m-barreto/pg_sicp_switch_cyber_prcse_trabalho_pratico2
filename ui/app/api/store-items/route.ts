// ui/app/api/store-items/route.ts
import { NextResponse } from "next/server";
import {
  fetchStoreItemsPage,
  SUPPORTED_STORES,
  type StoreId,
  type SortField,
  type SortDir,
} from "@/lib/scraperClient";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);

  const store = searchParams.get("store") as StoreId | null;
  const q = searchParams.get("q") ?? "";
  const offset = Number(searchParams.get("offset") ?? "0");
  const limit = Number(searchParams.get("limit") ?? "128");

  const sort = (searchParams.get("sort") ?? "nome") as SortField;
  const dir = (searchParams.get("dir") ?? "asc") as SortDir;

  // new filters
  const onlyPromoParam = searchParams.get("onlyPromo");
  const onlyPromo = onlyPromoParam === "true";

  const category = searchParams.get("category");
  const brand = searchParams.get("brand");

  if (!store || !(SUPPORTED_STORES as readonly string[]).includes(store)) {
    return NextResponse.json({ error: "Invalid 'store'" }, { status: 400 });
  }

  try {
    const { items, totalCount } = await fetchStoreItemsPage(
      store,
      q,
      offset,
      limit,
      sort,
      dir,
      {
        onlyPromo,
        category: category && category.trim() !== "" ? category : null,
        brand: brand && brand.trim() !== "" ? brand : null,
      }
    );

    return NextResponse.json({ items, totalCount });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

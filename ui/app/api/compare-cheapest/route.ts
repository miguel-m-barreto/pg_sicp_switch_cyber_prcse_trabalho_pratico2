// ui/app/api/compare-cheapest/route.ts
import { NextResponse } from "next/server";
import { fetchCheapestProductAcrossStores } from "@/lib/scraperClient";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const q = (searchParams.get("q") ?? "").trim();

  if (!q) {
    return NextResponse.json({ items: [] }, { status: 200 });
  }

  try {
    const items = await fetchCheapestProductAcrossStores(q);
    return NextResponse.json({ items: items ?? [] }, { status: 200 });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export const dynamic = "force-dynamic";

// ui/app/dashboard/[store]/page.tsx

import type { Metadata } from "next";
import Header from "@/components/Header";
import {
  SUPPORTED_STORES,
  type StoreId,
  fetchStoreCategories,
  fetchStoreBrands,
} from "@/lib/scraperClient";
import StoreDashboardClient from "@/components/StoreDashboardClient";

type PageProps = {
  params: Promise<{ store: string }>;
  searchParams?: Promise<{
    q?: string;
    category?: string;
    brand?: string;
    onlyPromo?: string;
  }>;
};

export async function generateMetadata(
  props: PageProps
): Promise<Metadata> {
  const { store } = await props.params;
  const raw = store.toLowerCase();
  const isValidStore =
    (SUPPORTED_STORES as readonly string[]).includes(raw as StoreId);

  if (!isValidStore) {
    return { title: "Loja inválida" };
  }

  return {
    title: `Dashboard ${raw}`,
  };
}

export default async function StoreDashboardPage(props: PageProps) {
  const { store } = await props.params;
  const rawStore = store.toLowerCase();

  const sp = (await props.searchParams) ?? {};
  const initialQuery = (sp.q ?? "").trim();
  const initialCategory = (sp.category ?? "").trim();
  const initialBrand = (sp.brand ?? "").trim();
  const initialOnlyPromo = sp.onlyPromo === "true";

  const isValidStore =
    (SUPPORTED_STORES as readonly string[]).includes(rawStore as StoreId);

  if (!isValidStore) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
        <p className="text-red-400">Loja inválida.</p>
      </main>
    );
  }

  const storeId = rawStore as StoreId;

  // Categories and brands are fetched on the server; products are client-side.
  const [categories, brands] = await Promise.all([
    // New version that already applies search / brand / onlyPromo to the counts
    fetchStoreCategories(storeId, {
      query: initialQuery,
      brand: initialBrand || null,
      onlyPromo: initialOnlyPromo,
    }),
    // Brands are filtered only by category for now
    fetchStoreBrands(storeId, initialCategory || null),
  ]);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto max-w-5xl px-4 pt-6 pb-10 min-h-screen">
        <Header subtitle={`Pesquisa de preços · ${storeId}`} />

        <StoreDashboardClient
          storeId={storeId}
          initialQuery={initialQuery}
          initialCategory={initialCategory}
          initialBrand={initialBrand}
          initialOnlyPromo={initialOnlyPromo}
          categories={categories}
          brands={brands}
        />
      </section>
    </main>
  );
}

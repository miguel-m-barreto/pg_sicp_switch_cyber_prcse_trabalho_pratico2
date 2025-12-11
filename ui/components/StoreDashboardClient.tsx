// ui/components/StoreDashboardClient.tsx
"use client";

import { useState, type FormEvent, type ChangeEvent } from "react";
import StoreItemsGrid from "@/components/StoreItemsGrid";
import type {
  StoreId,
  StoreCategory,
  StoreBrand,
} from "@/lib/scraperClient";

/**
 * Client shell for a single store dashboard.
 * Sidebar (filters) is fully interactive; grid reacts to state changes.
 */
type Props = {
  storeId: StoreId;
  initialQuery: string;
  initialCategory: string;
  initialBrand: string;
  initialOnlyPromo: boolean;
  categories: StoreCategory[];
  brands: StoreBrand[];
};

export default function StoreDashboardClient({
  storeId,
  initialQuery,
  initialCategory,
  initialBrand,
  initialOnlyPromo,
  categories,
  brands,
}: Props) {
  // Input text value (what the user is typing)
  const [queryInput, setQueryInput] = useState(initialQuery);
  // Effective query used for fetching data
  const [query, setQuery] = useState(initialQuery);

  const [category, setCategory] = useState(initialCategory);
  const [brand, setBrand] = useState(initialBrand);
  const [onlyPromo, setOnlyPromo] = useState(initialOnlyPromo);

  function handleSearchSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setQuery(queryInput.trim());
  }

  function handleCategoryChange(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    setCategory(value);
    // Opcional: limpar marca quando mudas de categoria
    setBrand("");
  }

  function handleBrandChange(e: ChangeEvent<HTMLSelectElement>) {
    setBrand(e.target.value);
  }

  function handleOnlyPromoChange(e: ChangeEvent<HTMLInputElement>) {
    setOnlyPromo(e.target.checked);
  }

  return (
    <div className="mt-6 flex gap-4 items-start">
      {/* SIDEBAR: search + filters (client-side, no page reload) */}
      <aside className="w-full sm:w-64 lg:w-72 shrink-0">
        <form
          className="space-y-3 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-3 text-xs"
          onSubmit={handleSearchSubmit}
        >
          {/* Search box: only applies on submit / Enter */}
          <div className="flex flex-col gap-2">
            <input
              type="text"
              name="q"
              placeholder="ex.: leite, massa, sumo..."
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            />
            <button
              type="submit"
              className="rounded-xl bg-zinc-100 px-4 py-2 text-sm text-zinc-900"
            >
              Pesquisar
            </button>
          </div>

          {/* Category selector (applies immediately) */}
          <div className="flex flex-col gap-1">
            <label className="text-[0.7rem] uppercase tracking-wide text-zinc-500">
              Categoria
            </label>
            <select
              name="category"
              value={category}
              onChange={handleCategoryChange}
              className="rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100"
            >
              <option value="">Todas</option>
              {categories.map((c) => (
                <option key={c.category_human_1} value={c.category_human_1}>
                  {c.category_human_1} ({c.total_variants})
                </option>
              ))}
            </select>
          </div>

          {/* Brand selector (applies immediately) */}
          <div className="flex flex-col gap-1">
            <label className="text-[0.7rem] uppercase tracking-wide text-zinc-500">
              Marca
            </label>
            <select
              name="brand"
              value={brand}
              onChange={handleBrandChange}
              className="rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100"
            >
              <option value="">Todas</option>
              {brands.map((b) => (
                <option key={b.brand} value={b.brand}>
                  {b.brand} ()
                </option>
              ))}
            </select>
          </div>

          {/* Only promotions (applies immediately) */}
          <label className="flex items-center gap-2 text-[0.75rem] text-zinc-300">
            <input
              type="checkbox"
              name="onlyPromo"
              checked={onlyPromo}
              onChange={handleOnlyPromoChange}
              className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-zinc-100"
            />
            Apenas promoções
          </label>
        </form>
      </aside>

      {/* MAIN: grid with infinite scroll, driven by current state */}
      <div className="flex-1">
        <StoreItemsGrid
          storeId={storeId}
          query={query}
          pageSize={64}
          onlyPromo={onlyPromo}
          category={category}
          brand={brand}
        />
      </div>
    </div>
  );
}

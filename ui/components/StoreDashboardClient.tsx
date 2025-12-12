// ui/components/StoreDashboardClient.tsx
"use client";

import { useState } from "react";
import StoreItemsGrid from "@/components/StoreItemsGrid";
import type {
  StoreId,
  StoreCategory,
  StoreBrand,
} from "@/lib/scraperClient";

/**
 * Client shell for a single store dashboard.
 * Search + filters em cima, grid em baixo. Tudo client-side.
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
  // Typed query in the input
  const [queryInput, setQueryInput] = useState(initialQuery);
  // Effective query used to fetch products
  const [query, setQuery] = useState(initialQuery);

  const [category, setCategory] = useState(initialCategory);
  const [brand, setBrand] = useState(initialBrand);
  const [onlyPromo, setOnlyPromo] = useState(initialOnlyPromo);

  function handleSearchSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setQuery(queryInput.trim());
  }

  function handleCategoryChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    setCategory(value);
    // Optional: reset brand when category changes
    setBrand("");
  }

  function handleBrandChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setBrand(e.target.value);
  }

  function handleOnlyPromoChange(e: React.ChangeEvent<HTMLInputElement>) {
    setOnlyPromo(e.target.checked);
  }

  return (
    <div className="mt-6 space-y-4">
      {/* Search + filters block on top */}
      <form
        className="space-y-3 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-3 text-xs"
        onSubmit={handleSearchSubmit}
      >
        {/* Search box (applies only on submit / Enter) */}
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            name="q"
            placeholder="ex.: leite, massa, sumo..."
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            className="flex-1 rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
          <button
            type="submit"
            className="rounded-xl bg-zinc-100 px-4 py-2 text-sm text-zinc-900"
          >
            Pesquisar
          </button>
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap gap-3">
          {/* Category selector (applies immediately) */}
          <div className="flex flex-col gap-1 min-w-[160px]">
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
                  {c.category_human_1} ({c.total_products})
                </option>
              ))}
            </select>
          </div>

          {/* Brand selector (applies immediately) */}
          <div className="flex flex-col gap-1 min-w-[160px]">
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
                  {b.brand} ({b.total_variants})
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
        </div>
      </form>

      {/* Products grid underneath, driven by current state */}
      <StoreItemsGrid
        storeId={storeId}
        query={query}
        pageSize={64}
        onlyPromo={onlyPromo}
        category={category}
        brand={brand}
      />
    </div>
  );
}

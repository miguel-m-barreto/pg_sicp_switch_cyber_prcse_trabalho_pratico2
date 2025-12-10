// app/dashboard/[store]/page.tsx

import Header from "@/components/Header";
import StoreItemsTable from "@/components/StoreItemsTable";
import { type StoreId, fetchStoreItemsPage } from "@/lib/scraperClient";

type PageProps = {
  params: { store?: string };
  searchParams?: { q?: string };
};

export default async function StoreDashboardPage({ params, searchParams }: PageProps) {
  const debugParams = JSON.stringify({ params, searchParams }, null, 2);

  // Se NÃO houver params.store, mostra isso claramente
  if (!params.store) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center justify-center gap-4">
        <p className="text-red-400 text-sm">Faltou params.store</p>
        <pre className="text-xs text-zinc-300 bg-zinc-900/60 rounded-lg p-4 max-w-xl overflow-auto">
          {debugParams}
        </pre>
      </main>
    );
  }

  const storeId = params.store.toLowerCase() as StoreId;
  const query = (searchParams?.q ?? "").trim();

  const firstPage = await fetchStoreItemsPage(storeId, query, 0, 32, "nome", "asc");

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto max-w-5xl px-4 pt-6 pb-10 min-h-screen">
        <Header subtitle={`Pesquisa de preços · ${storeId}`} />

        <div className="mt-6 space-y-4">
          <pre className="text-xs text-zinc-400 bg-zinc-900/60 rounded-lg p-3 overflow-auto">
            {debugParams}
          </pre>

          <form className="flex gap-2" method="GET">
            <input
              type="text"
              name="q"
              placeholder="ex.: leite, massa, sumo..."
              defaultValue={query}
              className="flex-1 rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            />
            <button className="rounded-xl bg-zinc-100 px-4 py-2 text-sm text-zinc-900">
              Pesquisar
            </button>
          </form>

          <p className="text-xs text-zinc-500">
            {firstPage.totalCount} itens encontrados
          </p>

          <StoreItemsTable
            storeId={storeId}
            query={query}
            initialItems={firstPage.items}
            totalCount={firstPage.totalCount}
            pageSize={64}
          />
        </div>
      </section>
    </main>
  );
}

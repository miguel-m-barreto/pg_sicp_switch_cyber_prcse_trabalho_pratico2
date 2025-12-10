// ui/app/dashboard/[store]/page.tsx

import Header from "@/components/Header";
import StoreItemsTable from "@/components/StoreItemsTable";
import {
  SUPPORTED_STORES,
  type StoreId,
  fetchStoreItemsPage,
} from "@/lib/scraperClient";

type PageProps = {
  // Next passa params como Promise
  params: Promise<{ store: string }>;
  // searchParams também pode vir como Promise
  searchParams?: Promise<{ q?: string }>;
};

export default async function StoreDashboardPage(props: PageProps) {
  // Desembrulhar params
  const { store } = await props.params;
  const rawStore = store.toLowerCase();

  // Desembrulhar searchParams (pode ser undefined)
  const sp = (await props.searchParams) ?? {};
  const query = (sp.q ?? "").trim();

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

  // Primeiro load: sort por nome ascendente
  const firstPage = await fetchStoreItemsPage(
    storeId,
    query,
    0,
    32,
    "nome",
    "asc"
  );

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto max-w-5xl px-4 pt-6 pb-10 min-h-screen">
        <Header subtitle={`Pesquisa de preços · ${storeId}`} />

        <div className="mt-6 space-y-4">
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

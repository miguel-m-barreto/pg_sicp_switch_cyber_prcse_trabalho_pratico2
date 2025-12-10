// ui/app/dashboard/page.tsx

export const dynamic = "force-dynamic";

import { scrapeStore } from "@/lib/scraperClient";
import { STORES } from "@/lib/stores";
import Header from "@/components/Header";

export default async function DashboardOverviewPage() {
  const results = await Promise.all(
    STORES.map((store) =>
      scrapeStore(store.id, store.defaultQuery)
        .then((data) => ({ ok: true as const, store, data }))
        .catch((err: unknown) => ({
          ok: false as const,
          store,
          error:
            err instanceof Error ? err.message : "Erro inesperado ao fazer scraping.",
        }))
    )
  );

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pt-6 pb-10">
        <Header subtitle="Visão geral · Produtos em destaque de cada loja" sticky />

        <div className="flex flex-1 flex-col justify-center gap-8">
          {/* Title */}
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              Visão geral das lojas
            </h1>
            <p className="mt-1 max-w-xl text-sm text-zinc-400">
              Cada cartão mostra uma pequena amostra de produtos (até 5 itens)
              obtida a partir de uma pesquisa padrão de cada loja.
              Clica numa loja para abrir o painel completo com pesquisa.
            </p>
          </div>

          {/* Grid de lojas */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((result) => {
              const { store } = result;
              const href = `/dashboard/${store.id}`;

              if (!result.ok) {
                return (
                  <div
                    key={store.id}
                    className="flex flex-col justify-between rounded-xl border border-red-900/60 bg-red-950/20 p-3 text-sm"
                  >
                    <div>
                      <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-red-400">
                        {store.label}
                      </p>
                      <p className="text-red-300 text-xs">
                        Erro ao obter os produtos: {result.error}
                      </p>
                    </div>
                    <div className="mt-3">
                      <a
                        href={href}
                        className="text-xs font-medium text-red-300 underline underline-offset-4 hover:text-red-200"
                      >
                        Abrir painel completo
                      </a>
                    </div>
                  </div>
                );
              }

              const items = result.data.items.slice(0, 5);

              return (
                <div
                  key={store.id}
                  className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/40 p-3 text-sm"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                        {store.label}
                      </p>
                      <p className="text-xs text-zinc-400">{store.description}</p>
                    </div>
                    <a
                      href={href}
                      className="text-[0.7rem] font-medium text-zinc-100 underline underline-offset-4 hover:text-zinc-50"
                    >
                      Abrir
                    </a>
                  </div>

                  <div className="mt-2 space-y-1.5">
                    {items.length === 0 && (
                      <p className="text-xs text-zinc-500">
                        Nenhum produto encontrado para a pesquisa padrão.
                      </p>
                    )}

                    {items.map((item, i) => (
                      <a
                        key={i}
                        href={item.link || "#"}
                        target="_blank"
                        rel="noreferrer"
                        className="group flex items-baseline justify-between gap-2 rounded-md px-2 py-1 hover:bg-zinc-900/70"
                      >
                        <span className="truncate text-xs text-zinc-100 group-hover:text-zinc-50">
                          {item.nome || "Sem nome"}
                        </span>

                        <div className="flex flex-col items-end">
                          <span className="text-xs text-zinc-100">
                            {item.preco_atual || "-"}
                          </span>

                          {item.preco_unitario && (
                            <span className="text-[0.65rem] text-zinc-500">
                              {item.preco_unitario}
                            </span>
                          )}
                        </div>
                      </a>
                    ))}
                  </div>

                  {items.length > 0 && items[0].data_execucao && (
                    <p className="mt-3 text-[0.65rem] text-zinc-500">
                      Dados obtidos em{" "}
                      <span className="text-zinc-300">
                        {items[0].data_execucao}
                      </span>
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}

export const dynamic = "force-dynamic";

import Header from "@/components/Header";
import { SUPPORTED_STORES, StoreId, fetchStoreItemsPage, PromotionItem } from "@/lib/scraperClient";

type StoreResult = {
  storeLabel: string;
  storeId: StoreId;
  items: PromotionItem[];
};

function normalizeText(text: string) {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function parsePrice(price: string | null | undefined): number {
  if (!price) return 0;
  return parseFloat(price.replace(" €", "").replace(",", "."));
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams?: { q?: string; limit?: string } | Promise<{ q?: string; limit?: string }>;
}) {
  const resolvedParams = await searchParams;
  const query = (resolvedParams?.q ?? "").toLowerCase().trim();
  const limitPerStore = parseInt(resolvedParams?.limit ?? "10", 10);

  if (!query) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100">
        <section className="mx-auto max-w-4xl px-4 pt-6 pb-10">
          <Header subtitle="Comparar preços entre lojas" sticky />
          <form className="mt-6 mb-10">
            <input
              name="q"
              defaultValue=""
              placeholder="Pesquisar produto (ex: leite, arroz, café...)"
              className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-4 py-3 text-sm"
            />
            <button
              type="submit"
              className="mt-3 rounded-xl bg-zinc-200 text-zinc-900 px-4 py-2 text-sm font-semibold"
            >
              Comparar
            </button>
          </form>
          <p className="text-zinc-400 text-sm">
            Introduz um nome de produto para comparar preços entre lojas.
          </p>
        </section>
      </main>
    );
  }

  // Buscar produtos de cada loja
  const storeResults: StoreResult[] = await Promise.all(
    SUPPORTED_STORES.map(async (storeId) => {
      let items: PromotionItem[] = [];
      try {
        const { items: fetchedItems } = await fetchStoreItemsPage(storeId, query, 0, 500, "nome", "asc");

        items = fetchedItems.map((i) => ({
          ...i,
          discount_raw_value: 0,
          discount_raw_pct: 0,
          discount_abs: null,
          discount_pct: null,
        })) as PromotionItem[];

        items = items
          .filter((i) => normalizeText(i.nome ?? "").includes(normalizeText(query)))
          .sort((a, b) => parsePrice(a.preco_atual) - parsePrice(b.preco_atual));
      } catch (err) {
        console.error(`Erro ao buscar loja ${storeId}:`, err);
      }

      return { storeLabel: storeId, storeId, items };
    })
  );

  // Lojas que têm produtos válidos
  const validStores = storeResults.filter((s) => s.items.length > 0);

  // Determinar produto mais barato por loja
  const cheapestByStore: Record<StoreId, PromotionItem | null> = {
    auchan: null,
    pingo_doce: null,
    froiz: null,
  };
  validStores.forEach((store) => {
    cheapestByStore[store.storeId] = store.items.reduce((min, item) => {
      const price = parsePrice(item.preco_atual);
      return !min || price < parsePrice(min.preco_atual) ? item : min;
    }, null as PromotionItem | null);
  });

  // Determinar preço mais barato global
  const globalMinPrice = Math.min(
    ...Object.values(cheapestByStore)
      .filter(Boolean)
      .map((item) => parsePrice(item!.preco_atual))
  );

  // Ordenar lojas para pódio (mais barato primeiro)
  const podiumStores = validStores
    .map((store) => ({
      ...store,
      cheapestItem: cheapestByStore[store.storeId]!,
    }))
    .sort((a, b) => parsePrice(a.cheapestItem.preco_atual) - parsePrice(b.cheapestItem.preco_atual));

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto max-w-6xl px-4 pt-6 pb-10">
        <Header subtitle={`Comparar preços: "${query}"`} sticky />
        <form className="mt-6 mb-10 flex gap-2">
          <input
            name="q"
            defaultValue={query}
            placeholder="Pesquisar produto (ex: leite, arroz, café...)"
            className="flex-1 rounded-xl bg-zinc-900 border border-zinc-800 px-4 py-3 text-sm"
          />
          <button
            type="submit"
            className="rounded-xl bg-zinc-200 text-zinc-900 px-4 py-3 text-sm font-semibold"
          >
            Comparar
          </button>
        </form>

        {/* Pódio */}
        {podiumStores.length > 0 && (
          <div className="flex justify-center items-end gap-6 mb-10 h-56">
            {podiumStores.map((store, idx) => {
              const price = parsePrice(store.cheapestItem.preco_atual);
              const maxPrice = Math.max(...podiumStores.map((s) => parsePrice(s.cheapestItem.preco_atual)));
              const heightPerc = Math.max((price / maxPrice) * 100, 20);
              const isGlobalCheapest = price === globalMinPrice;

              const colors = ["#FFD700", "#C0C0C0", "#CD7F32"]; // ouro, prata, bronze
              return (
                <div key={store.storeId} className="flex flex-col items-center w-28 relative">
                  <div
                    className={`w-full rounded-t-xl shadow-lg`}
                    style={{
                      height: `${heightPerc}%`,
                      backgroundColor: colors[idx] || "#4F46E5",
                      transition: "height 0.5s",
                    }}
                    title={`${store.storeLabel}: ${store.cheapestItem.nome} - ${store.cheapestItem.preco_atual}`}
                  ></div>
                  <div className="mt-2 text-center">
                    <p className="text-sm font-semibold">{store.storeLabel}</p>
                    <p className="text-xs text-zinc-200">{store.cheapestItem.nome}</p>
                    <p className="text-sm font-bold">{store.cheapestItem.preco_atual}</p>
                  </div>
                  {isGlobalCheapest && (
                    <span className="absolute -top-6 text-green-400 font-bold text-sm">Mais barato</span>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Produtos por loja */}
        <div className="flex flex-col gap-6">
          {storeResults.map((store) => {
            const itemsToShow = store.items.slice(0, limitPerStore);
            const hasMore = store.items.length > limitPerStore;
            return (
              <div key={store.storeLabel} className="rounded-xl border border-zinc-800 p-4 bg-zinc-900/40">
                <h2 className="text-lg font-semibold mb-2">{store.storeLabel}</h2>
                {itemsToShow.length === 0 && <p className="text-zinc-500 text-sm">Sem resultados.</p>}
                {itemsToShow.map((item) => {
                  const isCheapest = item === cheapestByStore[store.storeId];
                  return (
                    <div
                      key={item.link}
                      className={`flex justify-between items-center bg-zinc-900 rounded-xl p-3 border border-zinc-800 ${
                        isCheapest ? "border-green-400" : ""
                      }`}
                    >
                      <div>
                        <p className="font-medium">{item.nome}</p>
                        <p className="text-xs text-zinc-500">{item.category_human_1 ?? ""}</p>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${isCheapest ? "text-green-400" : "text-white"}`}>
                          {item.preco_atual ?? "-"}
                        </p>
                        {item.discount_raw_value > 0 && (
                          <p className="text-xs text-zinc-500 line-through">{item.preco_antigo ?? "-"}</p>
                        )}
                        {item.discount_raw_pct > 0 && (
                          <p className="text-xs text-red-400 font-semibold">
                            -{item.discount_raw_pct.toFixed(0)}%
                          </p>
                        )}
                        {item.link && (
                          <a
                            href={`/product/${store.storeId}?link=${encodeURIComponent(item.link)}`}
                            className="text-xs text-blue-400 underline block mt-1"
                          >
                            Ver detalhes
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
                {hasMore && (
                  <form method="get" className="mt-2">
                    <input type="hidden" name="q" value={query} />
                    <input type="hidden" name="limit" value={(limitPerStore + 10).toString()} />
                    <button
                      type="submit"
                      className="rounded-xl bg-zinc-200 text-zinc-900 px-4 py-2 text-sm font-semibold"
                    >
                      Ver mais
                    </button>
                  </form>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}
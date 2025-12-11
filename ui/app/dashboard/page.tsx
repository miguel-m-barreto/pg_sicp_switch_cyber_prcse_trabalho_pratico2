// ui/app/dashboard/page.tsx

export const dynamic = "force-dynamic";

import Header from "@/components/Header";
import { STORES } from "@/lib/stores";
import {
  fetchStorePromotions,
  type StoreId,
  type PromotionItem,
  fetchStorePromotionsByCategory,
} from "@/lib/scraperClient";
import StorePromotionsRow from "@/components/StorePromotionsRow";

export default async function DashboardOverviewPage() {
  // Quantos registos pedimos à DB por loja
  const PROMOS_PER_STORE = 750;
  // Máximo de produtos por categoria (para variedade)
  const MAX_PER_CATEGORY = 5;

  const results = await Promise.all(
    STORES.map(async (store) => {
      const storeId = store.id as StoreId;

      // Já vem ordenado por discount_pct desc da função get_store_promotions
      const { items } = await fetchStorePromotionsByCategory(storeId, 5, {
        sortField: "discount_pct",
        sortDir: "desc",
      });


      // Limitar a 5 por categoria SEM estragar a ordenação global
      const countsByCategory = new Map<string, number>();
      const limitedItems: PromotionItem[] = [];      

      return { store, items: items };
    })
  );

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pt-6 pb-10">
        <Header subtitle="Visão geral · Top promoções por loja" sticky />

        <div className="flex flex-1 flex-col justify-center gap-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              Visão geral das lojas
            </h1>
            <p className="mt-1 max-w-xl text-sm text-zinc-400">
              Cada cartão mostra as maiores promoções de cada supermercado,
              com um limite de produtos por categoria para dar variedade.
              A lista mantém a ordenação pelo maior desconto primeiro.
            </p>
          </div>

          <div className="flex flex-col gap-6">
            {results.map(({ store, items }) => (
              <StorePromotionsRow
                key={store.id}
                storeId={store.id as StoreId}
                label={store.label}
                description={store.description}
                items={items}
              />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

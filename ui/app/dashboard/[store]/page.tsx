// app/dashboard/[store]/page.tsx

import Link from "next/link";
import {
  scrapeStore,
  SUPPORTED_STORES,
  type StoreId,
} from "@/lib/scraperClient";

type PageProps = {
  params: { store: string };
  searchParams: Promise<{ q?: string }>;
};

const STORE_LABEL: Record<StoreId, string> = {
  auchan: "Auchan",
  froiz: "Froiz",
  pingo_doce: "Pingo Doce",
};

export default async function StoreDashboardPage({
  params,
  searchParams,
}: PageProps) {
  const rawStore = params.store.toLowerCase();
  const isSupported = (SUPPORTED_STORES as readonly string[]).includes(
    rawStore
  );

  if (!isSupported) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100">
        <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10">
          <nav className="mb-8 flex items-center justify-between text-sm text-zinc-400">
            <Link href="/" className="font-semibold tracking-tight text-zinc-200">
              GreyScrape
            </Link>
          </nav>
          <p className="text-sm text-red-400">
            Store &quot;{rawStore}&quot; is not supported.
          </p>
        </section>
      </main>
    );
  }

  const store = rawStore as StoreId;
  const sp = await searchParams;
  const query = (sp.q ?? "").trim();

  let errorMessage: string | null = null;
  let data: Awaited<ReturnType<typeof scrapeStore>> | null = null;

  if (query) {
    try {
      data = await scrapeStore(store, query);
    } catch (err) {
      errorMessage =
        err instanceof Error ? err.message : "Unexpected error while scraping.";
    }
  }

  const storeLabel = STORE_LABEL[store];

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10">
        <nav className="mb-8 flex items-center justify-between text-sm text-zinc-400">
          <Link href="/" className="font-semibold tracking-tight text-zinc-200">
            GreyScrape
          </Link>
          <span className="text-xs text-zinc-500">
            Backend: {storeLabel} · Live scraping
          </span>
        </nav>

        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            {storeLabel} price lookup
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Type a product name and we will scrape {storeLabel} in real time and
            list the current prices.
          </p>

          <form className="mt-4 flex gap-2" method="GET">
            <input
              type="text"
              name="q"
              placeholder="e.g. leite, massa, sumo..."
              defaultValue={query}
              className="flex-1 rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
            />
            <button
              type="submit"
              className="rounded-xl bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
            >
              Search
            </button>
          </form>
        </div>

        <div className="flex-1">
          {!query && (
            <p className="text-sm text-zinc-500">
              Start by typing a product name above and hitting Search.
            </p>
          )}

          {query && errorMessage && (
            <p className="text-sm text-red-400">
              Failed to scrape {storeLabel}: {errorMessage}
            </p>
          )}

          {query && data && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-zinc-500">
                <span>
                  Query: <span className="text-zinc-200">{data.query}</span>
                </span>
                <span>{data.count} items found</span>
              </div>

              <div className="rounded-xl border border-zinc-900 bg-zinc-950/60">
                <div className="grid grid-cols-[minmax(0,2fr),minmax(0,1fr),minmax(0,1fr)] gap-3 border-b border-zinc-900 px-4 py-2 text-xs uppercase tracking-wide text-zinc-500">
                  <span>Nome</span>
                  <span className="text-right">Preço</span>
                  <span className="text-right">Preço unitário</span>
                </div>

                <div className="divide-y divide-zinc-900">
                  {data.items.map((item, idx) => (
                    <a
                      key={idx}
                      href={item.link || "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="grid grid-cols-[minmax(0,2fr),minmax(0,1fr),minmax(0,1fr)] gap-3 px-4 py-2 text-sm hover:bg-zinc-900/60"
                    >
                      <span className="truncate text-zinc-100">
                        {item.nome || "Sem nome"}
                      </span>
                      <span className="text-right text-zinc-100">
                        {item.preco_atual || "-"}
                      </span>
                      <span className="text-right text-xs text-zinc-400">
                        {item.preco_unitario || "-"}
                      </span>
                    </a>
                  ))}

                  {data.items.length === 0 && (
                    <div className="px-4 py-3 text-sm text-zinc-500">
                      No items found for this query.
                    </div>
                  )}
                </div>
              </div>

              {data.items.length > 0 && data.items[0].data_execucao && (
                <p className="text-[0.7rem] text-zinc-500">
                  Data scraped at:{" "}
                  <span className="text-zinc-300">
                    {data.items[0].data_execucao as string}
                  </span>
                </p>
              )}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

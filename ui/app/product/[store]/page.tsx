// ui/app/product/[store]/page.tsx

export const dynamic = "force-dynamic";

import Header from "@/components/Header";
import {
  fetchProductByLink,
  SUPPORTED_STORES,
  type StoreId,
  type Item,
} from "@/lib/scraperClient";

async function fetchProductDetails(
  storeId: StoreId,
  link: string
): Promise<Item | null> {
  return fetchProductByLink(storeId, link);
}

export default async function ProductPage(props: {
  params: Promise<{ store: string }>;
  searchParams: Promise<{ link?: string }>;
}) {
  const params = await props.params;
  const searchParams = await props.searchParams;

  const rawStore = (params.store ?? "").toLowerCase();
  const isValidStore = (SUPPORTED_STORES as readonly string[]).includes(rawStore);

  if (!isValidStore) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100">
        <section className="mx-auto max-w-4xl px-4 pt-6 pb-10">
          <Header subtitle="Loja inválida" sticky />
          <p className="mt-6 text-sm text-red-400">Loja inválida: "{rawStore}".</p>
        </section>
      </main>
    );
  }

  const storeId = rawStore as StoreId;
  const productLink = (searchParams.link ?? "").trim();

  if (!productLink) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100">
        <section className="mx-auto max-w-4xl px-4 pt-6 pb-10">
          <Header subtitle={`Detalhes do produto · ${storeId}`} sticky />
          <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
            <p className="text-sm text-red-400">Link do produto não fornecido ou inválido.</p>
            <p className="mt-2 text-xs text-zinc-500">
              Volta atrás e abre o produto novamente a partir do dashboard/compare.
            </p>
          </div>
        </section>
      </main>
    );
  }

  const product = await fetchProductDetails(storeId, productLink);

  if (!product) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100">
        <section className="mx-auto max-w-4xl px-4 pt-6 pb-10">
          <Header subtitle={`Detalhes do produto · ${storeId}`} sticky />
          <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
            <p className="text-sm text-zinc-300">
              Não foi possível encontrar o produto com o link fornecido nesta loja.
            </p>
            <p className="mt-2 text-xs text-zinc-500 break-all">
              {productLink}
            </p>
          </div>
        </section>
      </main>
    );
  }

  const hasPrice = !!product.preco_atual;
  const hasOld = !!product.preco_antigo;
  const hasPromo = !!product.promocao;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto max-w-4xl px-4 pt-6 pb-10">
        <Header subtitle={`Detalhes do produto · ${storeId}`} sticky />

        <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 sm:p-6">
          <div className="flex flex-col gap-5 sm:flex-row">
            {/* Image */}
            <div className="w-full sm:w-[220px] shrink-0">
              <div className="relative w-full overflow-hidden rounded-2xl bg-white border border-zinc-200 shadow-sm pb-[100%]">
                {product.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={product.image_url}
                    alt={product.nome || ""}
                    loading="lazy"
                    className="absolute inset-0 m-auto max-h-full max-w-full object-contain p-2"
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-xs text-zinc-400">
                    Sem imagem
                  </div>
                )}
              </div>

              {hasPromo && (
                <div className="mt-3 inline-flex items-center rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
                  {product.promocao}
                </div>
              )}
            </div>

            {/* Details */}
            <div className="min-w-0 flex-1">
              <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-zinc-100">
                {product.nome || "Sem nome"}
              </h1>

              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                {/* Current price */}
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/50 p-4">
                  <p className="text-xs uppercase tracking-wide text-zinc-500">
                    Preço atual
                  </p>
                  <p className="mt-1 text-3xl font-black text-zinc-100">
                    {hasPrice ? product.preco_atual : "N/A"}
                  </p>

                  {product.preco_unitario && (
                    <p className="mt-1 text-xs text-zinc-400">
                      {product.preco_unitario}
                    </p>
                  )}
                </div>

                {/* Old price */}
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/50 p-4">
                  <p className="text-xs uppercase tracking-wide text-zinc-500">
                    Preço antigo
                  </p>
                  <p className={`mt-1 text-xl font-semibold ${hasOld ? "text-zinc-300 line-through" : "text-zinc-600"}`}>
                    {hasOld ? product.preco_antigo : "—"}
                  </p>

                  {!hasPrice && (
                    <p className="mt-2 text-xs text-red-400">
                      Sem preço atual disponível (estado atual em falta).
                    </p>
                  )}
                </div>
              </div>

              {/* Meta */}
              <div className="mt-5 rounded-2xl border border-zinc-800 bg-zinc-950/50 p-4">
                <p className="text-xs uppercase tracking-wide text-zinc-500">
                  Informação
                </p>

                <div className="mt-3 grid gap-2 text-sm">
                  <div className="flex gap-2">
                    <span className="text-zinc-500 w-24">Loja</span>
                    <span className="text-zinc-200">{storeId}</span>
                  </div>

                  <div className="flex gap-2">
                    <span className="text-zinc-500 w-24">Marca</span>
                    <span className="text-zinc-200">{product.brand ?? "N/A"}</span>
                  </div>

                  <div className="flex gap-2">
                    <span className="text-zinc-500 w-24">Categoria</span>
                    <span className="text-zinc-200">{product.category_human_1 ?? "N/A"}</span>
                  </div>

                  {product.quantidade_minima && (
                    <div className="flex gap-2">
                      <span className="text-zinc-500 w-24">Quantidade</span>
                      <span className="text-zinc-200">{product.quantidade_minima}</span>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <span className="text-zinc-500 w-24">Link</span>
                    <a
                      href={product.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline truncate"
                    >
                      Aceder à loja original
                    </a>
                  </div>

                  {product.data_execucao && (
                    <div className="flex gap-2">
                      <span className="text-zinc-500 w-24">Scraped</span>
                      <span className="text-zinc-400 truncate">{product.data_execucao}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* CTA */}
              <div className="mt-4 flex flex-wrap gap-2">
                <a
                  href={`/dashboard/${storeId}`}
                  className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-900"
                >
                  Voltar ao painel
                </a>

                <a
                  href={product.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-xl bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-950 hover:bg-zinc-200"
                >
                  Abrir na loja
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

// ui/app/product/[store]/page.tsx

export const dynamic = "force-dynamic";

import Header from "@/components/Header";
import { fetchProductByLink, StoreId, Item } from "@/lib/scraperClient"; 

async function fetchProductDetails(storeId: StoreId, link: string): Promise<Item | null> {
    const product = await fetchProductByLink(storeId, link);
    return product;
}

// No Next.js 15+, params e searchParams são Promises que DEVEM ser aguardadas
export default async function ProductPage(props: {
    params: Promise<{ store: string }>;
    searchParams: Promise<{ link?: string }>;
}) {
    // 1. Aguardar as Promises para obter os valores reais
    const params = await props.params;
    const searchParams = await props.searchParams;

    const storeId = params.store as StoreId;
    const productLink = searchParams.link;

    // Log de Debug para confirmar que agora os valores aparecem
    console.log(`[DEBUG] Store ID resolvido: ${storeId}, Link resolvido: ${productLink}`);

    if (!productLink || productLink.trim() === "") {
        return (
            <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
                <Header subtitle={`Detalhes do Produto na Loja ${storeId ?? 'indefinida'}`} />
                <p className="mt-4 text-red-400">Link do produto não fornecido ou inválido.</p>
            </main>
        );
    }

    const product = await fetchProductDetails(storeId, productLink);

    if (!product) {
        return (
            <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
                <Header subtitle={`Detalhes do Produto na Loja ${storeId}`} />
                <p className="mt-4 text-zinc-400">
                    Não foi possível encontrar o produto com o link fornecido na loja {storeId}.
                </p>
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-zinc-950 text-zinc-100">
            <section className="mx-auto max-w-4xl px-4 pt-6 pb-10">
                <Header subtitle={`Detalhes do Produto: ${product.nome}`} sticky />
                
                <div className="rounded-xl border border-zinc-700 p-6 mt-6 bg-zinc-900 shadow-lg">
                    <h1 className="text-3xl font-bold mb-4 text-green-400">{product.nome}</h1>
                    
                    {product.image_url && (
                        <img 
                            src={product.image_url} 
                            alt={product.nome} 
                            className="w-full max-h-64 object-contain mb-4 rounded-lg bg-white p-2"
                        />
                    )}

                    <div className="grid grid-cols-2 gap-4">
                        <div className="col-span-2 sm:col-span-1">
                            <p className="text-zinc-400">Preço Atual</p>
                            <p className="text-4xl font-extrabold text-white">
                                {product.preco_atual ?? "N/A"}
                            </p>
                        </div>

                        {product.preco_antigo && (
                            <div className="col-span-2 sm:col-span-1">
                                <p className="text-zinc-400">Preço Antigo</p>
                                <p className="text-xl line-through text-zinc-500">
                                    {product.preco_antigo}
                                </p>
                            </div>
                        )}
                        
                        <div className="col-span-2 border-t border-zinc-800 pt-4 mt-4">
                            <h3 className="text-lg font-semibold mb-2">Informações Adicionais</h3>
                            <p className="text-sm">
                                <span className="font-semibold text-zinc-300">Loja:</span> {storeId}
                            </p>
                            <p className="text-sm">
                                <span className="font-semibold text-zinc-300">Categoria:</span> {product.category_human_1 ?? "N/A"}
                            </p>
                            <p className="text-sm truncate">
                                <span className="font-semibold text-zinc-300">Link:</span> 
                                <a href={product.link} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline ml-1">
                                    Aceder à Loja Original
                                </a>
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    );
}
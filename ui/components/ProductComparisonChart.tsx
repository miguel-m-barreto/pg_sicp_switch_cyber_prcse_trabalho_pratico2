// ui/components/ProductComparisonChart.tsx
'use client';

import { useEffect, useState } from 'react';
import { fetchCheapestProductAcrossStores } from '@/lib/scraperClient';

// Definir o tipo de dados esperado da comparação (deve ser o mesmo que o scraperClient)
interface ComparisonItem {
    storeName: string;
    price: number;
    formattedPrice: string;
    productName: string;
    link: string;
}

interface ProductComparisonChartProps {
    productName: string;
}

export default function ProductComparisonChart({ productName }: ProductComparisonChartProps) {
    const [comparisonData, setComparisonData] = useState<ComparisonItem[] | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        if (!productName) {
            setIsLoading(false);
            return;
        }

        // Função de fetch que será executada após a montagem do componente (Client-Side)
        const fetchComparison = async () => {
            try {
                // A função de busca é importada do módulo server-side, mas é executada no cliente
                const data = await fetchCheapestProductAcrossStores(productName);
                setComparisonData(data);
            } catch (error) {
                console.error("Failed to fetch comparison data:", error);
                setComparisonData(null);
            } finally {
                setIsLoading(false);
            }
        };

        fetchComparison();
    }, [productName]); // Dependência no nome do produto

    // --- Renderização de Carregamento ---
    if (isLoading) {
        return (
            <div className="mt-12">
                <h2 className="text-2xl font-bold text-zinc-200 mb-4 border-b border-zinc-800 pb-2">
                    Comparação de Preços
                </h2>
                <div className="space-y-4">
                    <div className="h-16 bg-zinc-800/50 rounded-lg animate-pulse"></div>
                    <div className="h-16 w-5/6 bg-zinc-800/50 rounded-lg animate-pulse"></div>
                    <div className="h-16 w-4/6 bg-zinc-800/50 rounded-lg animate-pulse"></div>
                </div>
            </div>
        );
    }
    
    // --- Renderização de Dados Não Encontrados ---
    if (!comparisonData || comparisonData.length === 0) {
        return (
            <div className="mt-12">
                <h2 className="text-2xl font-bold text-zinc-200 mb-4 border-b border-zinc-800 pb-2">
                    Comparação de Preços
                </h2>
                <p className="text-zinc-500">Não foi possível encontrar produtos similares noutras lojas para comparação.</p>
            </div>
        );
    }

    // --- Renderização do Gráfico/Lista (Client-Side) ---
    return (
        <div className="mt-12">
            <h2 className="text-2xl font-bold text-zinc-200 mb-4 border-b border-zinc-800 pb-2">
                Comparação de Preços (Produto Similar)
            </h2>
            
            <div className="space-y-4">
                {comparisonData.map((item, index) => (
                    <a 
                        key={item.storeName}
                        href={`/product/${item.storeName.toLowerCase().replace(/\s/g, '_')}?link=${encodeURIComponent(item.link)}`}
                        className={`flex justify-between items-center p-4 rounded-lg transition-all ${index === 0 
                            ? 'bg-green-700/50 border border-green-500 shadow-xl' // Mais barato
                            : 'bg-zinc-800 border border-zinc-700 hover:bg-zinc-700'
                        }`}
                    >
                        <div className="flex flex-col">
                            <span className="font-bold text-lg">{item.storeName}</span>
                            <span className="text-xs text-zinc-400 truncate w-48 sm:w-auto">
                                {item.productName}
                            </span>
                        </div>
                        <div className="text-right">
                            <span className={`font-black text-2xl ${index === 0 ? 'text-green-300' : 'text-white'}`}>
                                {item.formattedPrice}
                            </span>
                            {index === 0 && (
                                <span className="block text-xs text-green-300 font-semibold">MAIS BARATO</span>
                            )}
                        </div>
                    </a>
                ))}
            </div>
        </div>
    );
}
// ui/components/StoreItemsGrid.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import type {
    Item,
    StoreId,
    SortField,
    SortDir,
} from "@/lib/scraperClient";

type Props = {
    storeId: StoreId;
    query: string;
    pageSize?: number;
    onlyPromo: boolean;
    category: string;
    brand: string;
};

type SortOption = {
    field: SortField;
    label: string;
};

const SORT_OPTIONS: SortOption[] = [
    { field: "nome", label: "Nome" },
    { field: "preco", label: "Preço" },
    { field: "preco_unitario", label: "Preço unitário" },
];

function SortDirIcon({ dir }: { dir: SortDir }) {
    return (
        <span className="text-[0.7rem] text-zinc-400">
            {dir === "asc" ? "▲" : "▼"}
        </span>
    );
}

export default function StoreItemsGrid({
    storeId,
    query,
    pageSize = 64,
    onlyPromo,
    category,
    brand,
}: Props) {
    const [items, setItems] = useState<Item[]>([]);
    const [totalCount, setTotalCount] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(false);
    const [showBackToTop, setShowBackToTop] = useState(false);

    const [sortField, setSortField] = useState<SortField>("nome");
    const [sortDir, setSortDir] = useState<SortDir>("asc");

    const sentinelRef = useRef<HTMLDivElement | null>(null);

    // Core fetch helper (no state changes here)
    async function fetchPageFromApi(
        nextOffset: number,
        nextLimit: number,
        field: SortField,
        dir: SortDir
    ): Promise<{ items: Item[]; count: number }> {
        const params = new URLSearchParams();
        params.set("store", storeId);
        params.set("q", query);
        params.set("offset", String(nextOffset));
        params.set("limit", String(nextLimit));
        params.set("sort", field);
        params.set("dir", dir);
        if (onlyPromo) params.set("onlyPromo", "true");
        if (category.trim() !== "") params.set("category", category);
        if (brand.trim() !== "") params.set("brand", brand);

        const res = await fetch(`/api/store-items?${params.toString()}`);
        if (!res.ok) {
            return { items: [], count: 0 };
        }

        const json = await res.json();
        return {
            items: (json.items ?? []) as Item[],
            count: Number(json.totalCount ?? 0),
        };
    }

    // Load first page whenever filters or sort change
    useEffect(() => {
        let cancelled = false;

        async function loadFirstPage() {
            setLoading(true);
            try {
                const { items: firstItems, count } = await fetchPageFromApi(
                    0,
                    pageSize,
                    sortField,
                    sortDir
                );
                if (cancelled) return;

                setItems(firstItems);
                setTotalCount(count);
                setOffset(firstItems.length || 0);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadFirstPage();

        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [storeId, query, onlyPromo, category, brand, sortField, sortDir, pageSize]);

    async function loadMore() {
        if (loading) return;
        if (offset >= totalCount) return;

        setLoading(true);
        try {
            const { items: newItems } = await fetchPageFromApi(
                offset,
                pageSize,
                sortField,
                sortDir
            );

            if (newItems.length > 0) {
                setItems((prev) => [...prev, ...newItems]);
                setOffset((prev) => prev + newItems.length);
            }
        } finally {
            setLoading(false);
        }
    }

    async function changeSort(nextField: SortField) {
        const nextDir: SortDir =
            nextField === sortField ? (sortDir === "asc" ? "desc" : "asc") : "asc";

        setSortField(nextField);
        setSortDir(nextDir);
        // First page será recarregada automaticamente pelo useEffect acima
    }

    // Infinite scroll observer
    useEffect(() => {
        if (!sentinelRef.current) return;

        const obs = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) {
                    loadMore();
                }
            },
            { rootMargin: "400px" }
        );

        obs.observe(sentinelRef.current);
        return () => obs.disconnect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [offset, totalCount, sortField, sortDir, pageSize, query, storeId, onlyPromo, category, brand]);

    // Show / hide "Voltar ao topo" button
    useEffect(() => {
        const onScroll = () => {
            setShowBackToTop(window.scrollY > 400);
        };

        onScroll();
        window.addEventListener("scroll", onScroll);
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    return (
        <div className="space-y-3">
            {/* Sort controls */}
            <div className="flex items-center justify-between gap-3 text-xs text-zinc-400">
                <div className="flex items-center gap-2">
                    <span>Ordenar por</span>
                    <div className="flex items-center gap-1 rounded-xl border border-zinc-800 bg-zinc-950/80 px-2 py-1">
                        {SORT_OPTIONS.map((opt) => (
                            <button
                                key={opt.field}
                                type="button"
                                onClick={() => changeSort(opt.field)}
                                className={`px-2 py-0.5 rounded-lg transition text-[0.7rem] ${sortField === opt.field
                                    ? "bg-zinc-800 text-zinc-100"
                                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
                                    }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                        <button
                            type="button"
                            onClick={() =>
                                changeSort(sortField)
                            }
                            className="ml-1 inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2 py-0.5 text-[0.7rem] text-zinc-200 hover:bg-zinc-900"
                        >
                            <span>{sortDir === "asc" ? "Asc" : "Desc"}</span>
                            <SortDirIcon dir={sortDir} />
                        </button>
                    </div>
                </div>

                <span className="text-[0.7rem] text-zinc-500">
                    Mostrados {items.length} de {totalCount} produtos
                </span>
            </div>

            {/* Grid of tiles */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-3">
                {items.length === 0 && !loading ? (
                    <p className="text-xs text-zinc-500">
                        Nenhum produto encontrado com estes filtros.
                    </p>
                ) : (
                    <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
                        {items.map((item, idx) => (
                            <a
                                key={`${item.link}-${idx}`}
                                href={item.link || "#"}
                                target="_blank"
                                rel="noreferrer"
                                className="group flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/80 p-2 text-xs hover:border-zinc-600 hover:bg-zinc-900/90"
                            >
                                {/* Square image area with white background, lazy load and hover zoom */}
                                <div className="relative mb-2 w-full overflow-hidden rounded-lg bg-white border border-zinc-200 shadow-sm pb-[100%]">
                                    {item.image_url ? (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img
                                            src={item.image_url}
                                            alt={item.nome || ""}
                                            loading="lazy"
                                            className="absolute inset-0 m-auto max-h-full max-w-full object-contain transition-transform duration-200 ease-out group-hover:scale-[1.05]"
                                        />
                                    ) : (
                                        <div className="absolute inset-0 flex items-center justify-center text-[0.65rem] text-zinc-400">
                                            Sem imagem
                                        </div>
                                    )}
                                </div>


                                <div className="flex-1 space-y-1">
                                    <p className="line-clamp-2 text-xs font-medium text-zinc-100">
                                        {item.nome || "Sem nome"}
                                    </p>

                                    {item.brand && (
                                        <p className="text-[0.65rem] uppercase tracking-wide text-zinc-500">
                                            {item.brand}
                                        </p>
                                    )}

                                    {item.category_human_1 && (
                                        <p className="text-[0.65rem] text-zinc-500">
                                            {item.category_human_1}
                                        </p>
                                    )}
                                </div>

                                <div className="mt-2 flex items-baseline justify-between gap-2">
                                    <div className="flex flex-col">
                                        <span className="text-sm font-semibold text-zinc-100">
                                            {item.preco_atual || "-"}
                                        </span>
                                        {item.preco_antigo && (
                                            <span className="text-[0.65rem] text-zinc-500 line-through">
                                                {item.preco_antigo}
                                            </span>
                                        )}
                                        {item.preco_unitario && (
                                            <span className="text-[0.65rem] text-zinc-500">
                                                {item.preco_unitario}
                                            </span>
                                        )}
                                    </div>

                                    {item.promocao && (
                                        <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-0.5 text-[0.65rem] font-medium text-green-400 border border-green-500/40">
                                            {item.promocao}
                                        </span>
                                    )}
                                </div>
                            </a>
                        ))}
                    </div>
                )}

                {/* Sentinel for infinite scroll */}
                <div ref={sentinelRef} className="h-8 w-full" />

                {offset < totalCount ? (
                    loading ? (
                        <p className="mt-2 text-center text-[0.7rem] text-zinc-500">
                            A carregar mais produtos…
                        </p>
                    ) : null
                ) : (
                    <p className="mt-2 text-center text-[0.7rem] text-zinc-500">
                        Mostrados {items.length} de {totalCount}.
                    </p>
                )}
            </div>

            {showBackToTop && (
                <button
                    type="button"
                    onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
                    className="fixed bottom-22 left-1/2 z-40 -translate-x-1/2 rounded-full border border-zinc-700 bg-zinc-900/90 px-4 py-2 text-xs font-medium text-zinc-100 shadow-lg hover:bg-zinc-800"
                >
                    Voltar ao topo
                </button>
            )}
        </div>
    );
}

// components/StoreItemsTable.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import type { Item, StoreId, SortField, SortDir } from "@/lib/scraperClient";

type Props = {
    storeId: StoreId;
    query: string;
    initialItems: Item[];
    totalCount: number;
    pageSize?: number; // default for FOLLOW-UP loads
};

// Small helper to render ▲ / ▼ on the active sorted column
function SortIcon({ dir }: { dir: SortDir }) {
    return (
        <span className="text-[0.6rem] text-zinc-500">
            {dir === "asc" ? "▲" : "▼"}
        </span>
    );
}

export default function StoreItemsTable({
    storeId,
    query,
    initialItems,
    totalCount,
    pageSize = 128,
}: Props) {
    const [items, setItems] = useState<Item[]>(initialItems);
    const [offset, setOffset] = useState(initialItems.length);
    const [loading, setLoading] = useState(false);
    const [showBackToTop, setShowBackToTop] = useState(false);

    const [sortField, setSortField] = useState<SortField>("nome");
    const [sortDir, setSortDir] = useState<SortDir>("asc");

    const sentinelRef = useRef<HTMLDivElement | null>(null);

    async function fetchPage(
        nextOffset: number,
        nextLimit: number,
        field: SortField,
        dir: SortDir
    ) {
        const url = `/api/store-items?store=${storeId}` +
            `&q=${encodeURIComponent(query)}` +
            `&offset=${nextOffset}` +
            `&limit=${nextLimit}` +
            `&sort=${field}` +
            `&dir=${dir}`;

        const res = await fetch(url);
        if (!res.ok) {
            // In a real app you might want to report the error to the user
            return { items: [] as Item[], count: 0 };
        }
        const json = await res.json();
        return {
            items: (json.items ?? []) as Item[],
            count: Number(json.totalCount ?? 0),
        };
    }

    async function loadMore() {
        if (loading) return;
        if (offset >= totalCount) return;

        setLoading(true);
        const { items: newItems } = await fetchPage(
            offset,
            pageSize,
            sortField,
            sortDir
        );

        if (newItems.length > 0) {
            setItems((prev) => [...prev, ...newItems]);
            setOffset((prev) => prev + newItems.length);
        }
        setLoading(false);
    }

    // Change sort (by clicking header): reset to first page
    async function changeSort(nextField: SortField) {
        const nextDir: SortDir =
            nextField === sortField ? (sortDir === "asc" ? "desc" : "asc") : "asc";

        setLoading(true);
        setSortField(nextField);
        setSortDir(nextDir);

        const { items: firstItems } = await fetchPage(0, pageSize, nextField, nextDir);

        setItems(firstItems);
        setOffset(firstItems.length);
        setLoading(false);

        // Scroll back to top so the user sees the new order from the beginning
        window.scrollTo({ top: 0, behavior: "smooth" });
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
    }, [offset, totalCount, sortField, sortDir, pageSize, query, storeId]);

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
        <>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 overflow-hidden">
                {/* Table header with sortable columns */}
                <div className="grid grid-cols-[2fr,1fr,1fr] items-center border-b border-zinc-900 px-4 py-2 text-xs uppercase text-zinc-500 bg-zinc-950/80">
                    <button
                        type="button"
                        onClick={() => changeSort("nome")}
                        className="flex items-center gap-1 text-left"
                    >
                        <span>Nome</span>
                        {sortField === "nome" && <SortIcon dir={sortDir} />}
                    </button>

                    <button
                        type="button"
                        onClick={() => changeSort("preco")}
                        className="flex items-center gap-1 justify-end"
                    >
                        <span>Preço</span>
                        {sortField === "preco" && <SortIcon dir={sortDir} />}
                    </button>

                    <button
                        type="button"
                        onClick={() => changeSort("preco_unitario")}
                        className="flex items-center gap-1 justify-end"
                    >
                        <span>Preço unitário</span>
                        {sortField === "preco_unitario" && <SortIcon dir={sortDir} />}
                    </button>
                </div>

                {/* Rows */}
                <div className="divide-y divide-zinc-900">
                    {items.map((item, i) => (
                        <a
                            key={`${item.link}-${i}`}
                            href={item.link || "#"}
                            target="_blank"
                            rel="noreferrer"
                            className="grid grid-cols-[2fr,1fr,1fr] px-4 py-3 hover:bg-zinc-900/60 text-sm min-h-[48px]"
                        >
                            {/* Name - vertically centered */}
                            <div className="flex h-full items-center">
                                <span className="truncate text-zinc-100 leading-snug">
                                    {item.nome}
                                </span>
                            </div>

                            {/* Price - vertically centered */}
                            <div className="flex h-full items-center justify-end">
                                <span className="text-zinc-100 leading-snug">
                                    {item.preco_atual || "-"}
                                </span>
                            </div>

                            {/* Unit price - vertically centered */}
                            <div className="flex h-full items-center justify-end">
                                <span className="text-xs text-zinc-400 leading-snug">
                                    {item.preco_unitario || "-"}
                                </span>
                            </div>
                        </a>
                    ))}
                </div>

                {/* Sentinel for infinite scroll */}
                <div ref={sentinelRef} className="h-8 w-full" />

                {offset < totalCount ? (
                    <p className="text-center pb-3 text-xs text-zinc-500">
                        A carregar mais produtos…
                    </p>
                ) : (
                    <p className="text-center pb-3 text-xs text-zinc-500">
                        Mostrados {items.length} de {totalCount}.
                    </p>
                )}
            </div>

            {showBackToTop && (
                <button
                    type="button"
                    onClick={() =>
                        window.scrollTo({ top: 0, behavior: "smooth" })
                    }
                    className="fixed bottom-22 left-1/2 z-40 -translate-x-1/2 rounded-full border border-zinc-700 bg-zinc-900/90 px-4 py-2 text-xs font-medium text-zinc-100 shadow-lg hover:bg-zinc-800"
                >
                    Voltar ao topo
                </button>
            )}
        </>
    );
}

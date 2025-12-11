// ui/components/StorePromoCarousel.tsx
"use client";

import { useState } from "react";
import type { PromotionItem } from "@/lib/scraperClient";

type Props = {
    items: PromotionItem[];
};

const VISIBLE = 5;

export default function StorePromoCarousel({ items }: Props) {
    const [index, setIndex] = useState(0);

    if (!items || items.length === 0) {
        return (
            <p className="text-xs text-zinc-500">
                Sem promoções ativas nesta loja neste momento.
            </p>
        );
    }

    const total = items.length;

    function next() {
        setIndex((prev) => (prev + 1) % total);
    }

    function prev() {
        setIndex((prev) => (prev - 1 + total) % total);
    }

    const visibleCount = Math.min(VISIBLE, total);
    const visible: PromotionItem[] = [];
    for (let i = 0; i < visibleCount; i += 1) {
        visible.push(items[(index + i) % total]);
    }

    return (
        <div className="mt-3 flex items-center gap-2">
            <button
                type="button"
                onClick={prev}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-700 bg-zinc-950 text-xs text-zinc-200 hover:bg-zinc-900"
            >
                ‹
            </button>

            <div className="flex-1 overflow-hidden">
                <div className="grid grid-flow-col auto-cols-[minmax(0,1fr)] gap-3">
                    {visible.map((item, idx) => (
                        <a
                            key={`${item.link}-${idx}`}
                            href={item.link || "#"}
                            target="_blank"
                            rel="noreferrer"
                            className="group flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/80 p-2 text-xs hover:border-zinc-600 hover:bg-zinc-900/90"
                        >
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


                            <p className="line-clamp-2 text-xs font-medium text-zinc-100">
                                {item.nome || "Sem nome"}
                            </p>

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
                                </div>

                                <div className="flex flex-col items-end gap-1">
                                    {item.discount_pct && (
                                        <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 text-[0.65rem] font-semibold text-emerald-400 border border-emerald-500/40">
                                            {item.discount_pct}
                                        </span>
                                    )}
                                    {item.promocao && (
                                        <span className="text-[0.6rem] text-zinc-400 line-clamp-1">
                                            {item.promocao}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </a>
                    ))}
                </div>
            </div>

            <button
                type="button"
                onClick={next}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-700 bg-zinc-950 text-xs text-zinc-200 hover:bg-zinc-900"
            >
                ›
            </button>
        </div>
    );
}

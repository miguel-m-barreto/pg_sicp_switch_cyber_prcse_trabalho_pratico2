// ui/components/StorePromotionsRow.tsx
"use client";

import Link from "next/link";
import Image from "next/image";
import { useState, useMemo } from "react";
import type { PromotionItem, StoreId } from "@/lib/scraperClient";

type Props = {
  storeId: StoreId;
  label: string;
  description: string;
  items: PromotionItem[];
};

const VISIBLE_COUNT = 5;

export default function StorePromotionsRow({
  storeId,
  label,
  description,
  items,
}: Props) {
  const [startIndex, setStartIndex] = useState(0);
  const total = items.length;

  const visibleItems = useMemo(() => {
    if (total === 0) return [];
    return Array.from({ length: Math.min(VISIBLE_COUNT, total) }, (_, i) => {
      const idx = (startIndex + i) % total;
      return items[idx];
    });
  }, [items, startIndex, total]);

  function handleNext() {
    if (total === 0) return;
    setStartIndex((prev) => (prev + 1) % total);
  }

  function handlePrev() {
    if (total === 0) return;
    setStartIndex((prev) => (prev - 1 + total) % total);
  }

  const panelHref = `/dashboard/${storeId}`;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm">
      {/* Header da loja */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
            {label}
          </p>
          <p className="text-xs text-zinc-400">{description}</p>
        </div>

        <Link
          href={panelHref}
          className="text-[0.7rem] font-medium text-zinc-100 underline underline-offset-4 hover:text-zinc-50"
        >
          Abrir painel
        </Link>
      </div>

      {/* Carrossel */}
      {total === 0 ? (
        <p className="text-xs text-zinc-500">
          Sem promoções ativas nesta loja neste momento.
        </p>
      ) : (
        <div className="flex items-center gap-3">
          {/* Botão esquerdo */}
          <button
            type="button"
            onClick={handlePrev}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900/70 text-xs text-zinc-300 hover:bg-zinc-800"
            aria-label="Anterior"
          >
            ‹
          </button>

          {/* Tiles visíveis */}
          <div className="flex flex-1 gap-3 overflow-hidden">
            {visibleItems.map((item, i) => (
              <PromotionTile key={`${item.link}-${i}`} item={item} />
            ))}
          </div>

          {/* Botão direito */}
          <button
            type="button"
            onClick={handleNext}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900/70 text-xs text-zinc-300 hover:bg-zinc-800"
            aria-label="Seguinte"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

function PromotionTile({ item }: { item: PromotionItem }) {
  const {
    nome,
    link,
    image_url,
    preco_atual,
    preco_antigo,
    promocao,
    discount_pct,
    discount_abs,
  } = item;

  const hasDiscount = !!discount_pct || !!discount_abs;

  return (
    <a
      href={link || "#"}
      target="_blank"
      rel="noreferrer"
      className="group flex min-w-[140px] max-w-[160px] flex-col rounded-xl border border-zinc-800 bg-zinc-950/80 p-2 hover:border-zinc-600"
    >
      {/* Square image area with white background, lazy load and hover zoom */}
      <div className="relative mb-2 w-full overflow-hidden rounded-lg bg-white border border-zinc-200 shadow-sm pb-[100%]">
        {image_url ? (
          <Image
            src={image_url}
            alt={nome || ""}
            fill
            sizes="160px"
            loading="lazy"
            placeholder="blur"
            blurDataURL="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
            className="object-contain transition-transform duration-200 ease-out group-hover:scale-[1.05]"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-[0.6rem] text-zinc-400">
            Sem imagem
          </div>
        )}
      </div>

      {/* Nome */}
      <p className="line-clamp-2 text-[0.7rem] font-medium text-zinc-100">
        {nome || "Sem nome"}
      </p>

      {/* Preços */}
      <div className="mt-1 flex flex-col items-start">
        <span className="text-sm font-semibold text-zinc-100">
          {preco_atual ?? "-"}
        </span>
        {preco_antigo && (
          <span className="text-[0.65rem] text-zinc-500 line-through">
            {preco_antigo}
          </span>
        )}
      </div>

      {/* Promo label + desconto */}
      <div className="mt-1 flex items-center justify-between gap-1">
        {promocao && (
          <span className="truncate text-[0.6rem] text-zinc-500">
            {promocao}
          </span>
        )}

        {hasDiscount && (
          <span className="ml-auto rounded-full bg-emerald-900/40 px-1.5 py-0.5 text-[0.6rem] font-semibold text-emerald-300">
            {discount_pct ?? discount_abs ?? ""}
          </span>
        )}
      </div>
    </a>
  );
}

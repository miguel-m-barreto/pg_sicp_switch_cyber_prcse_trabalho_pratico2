// ui/components/StoreCard.tsx
import Link from "next/link";
import { Item } from "@/lib/scraperClient";

export default function StoreCard({
  id,
  label,
  description,
  items,
  error,
}: {
  id: string;
  label: string;
  description: string;
  items?: Item[];
  error?: string;
}) {
  const href = `/dashboard/${id}`;

  return (
    <div className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/40 p-3 text-sm">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
            {label}
          </p>
          <p className="text-xs text-zinc-400">{description}</p>
        </div>

        <Link
          href={href}
          className="text-[0.7rem] font-medium text-zinc-100 underline underline-offset-4 hover:text-zinc-50"
        >
          Open →
        </Link>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-red-400 mb-2">
          Failed to fetch: {error}
        </p>
      )}

      {/* Product preview */}
      <div className="space-y-1.5">
        {!items || items.length === 0 ? (
          <p className="text-xs text-zinc-500">No sample items.</p>
        ) : (
          items.slice(0, 5).map((item, i) => (
            <a
              key={i}
              href={item.link || "#"}
              target="_blank"
              className="group flex items-baseline justify-between gap-2 rounded-md px-2 py-1 hover:bg-zinc-900/70"
            >
              <span className="truncate text-xs text-zinc-100 group-hover:text-zinc-50">
                {item.nome}
              </span>

              <div className="flex flex-col items-end">
                <span className="text-xs text-zinc-100">
                  {item.preco_atual || "-"}
                </span>

                {item.preco_unitario && (
                  <span className="text-[0.65rem] text-zinc-500">
                    {item.preco_unitario}
                  </span>
                )}
              </div>
            </a>
          ))
        )}
      </div>

      {items && items.length > 0 && items[0].data_execucao && (
        <p className="mt-3 text-[0.65rem] text-zinc-500">
          Scraped at{" "}
          <span className="text-zinc-300">
            {items[0].data_execucao}
          </span>
        </p>
      )}
    </div>
  );
}

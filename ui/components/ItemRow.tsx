// components/ItemRow.tsx

import { Item } from "@/lib/scraperClient";

export default function ItemRow({ item }: { item: Item }) {
  return (
    <a
      href={item.link || "#"}
      target="_blank"
      rel="noreferrer"
      className="grid grid-cols-[minmax(0,2fr),minmax(0,1fr),minmax(0,1fr)] gap-3 px-4 py-2 text-sm hover:bg-zinc-900/60"
    >
      <span className="truncate text-zinc-100">{item.nome || "Sem nome"}</span>

      <span className="text-right text-zinc-100">
        {item.preco_atual || "-"}
      </span>

      <span className="text-right text-xs text-zinc-400">
        {item.preco_unitario || "-"}
      </span>
    </a>
  );
}

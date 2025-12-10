// lib/stores.ts

import { StoreId } from "./scraperClient";

export const STORES: {
  id: StoreId;
  label: string;
  description: string;
  defaultQuery: string;
}[] = [
    {
      id: "auchan",
      label: "Auchan",
      description: "Produtos em destaque Auchan.",
      defaultQuery: "", // empty = landing page
    },
    {
      id: "pingo_doce",
      label: "Pingo Doce",
      description: "Produtos em destaque Pingo Doce.",
      defaultQuery: "",
    },
    {
      id: "froiz",
      label: "Froiz",
      description: "Produtos em destaque Froiz.",
      defaultQuery: "",
    },
  ];

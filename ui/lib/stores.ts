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
    description: "Highlighted products from Auchan.",
    defaultQuery: "", // empty = landing page
  },
  {
    id: "froiz",
    label: "Froiz",
    description: "Highlighted products from Froiz.",
    defaultQuery: "", // depois adaptamos o scraper de Froiz
  },
  {
    id: "pingo_doce",
    label: "Pingo Doce",
    description: "Highlighted products from Pingo Doce.",
    defaultQuery: "", // idem
  },
];

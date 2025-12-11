// ui/app/page.tsx

import Link from "next/link";
import Image from "next/image";
import Header from "@/components/Header";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero section */}
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pt-6 pb-10">
        <Header
          subtitle={
            <div className="flex items-center gap-4">
              <Link href="#how-it-works" className="hover:text-zinc-200 transition">
                Como funciona
              </Link>
              <Link href="#about" className="hover:text-zinc-200 transition">
                Projeto
              </Link>
            </div>
          }
        />

        <div className="flex flex-1 flex-col items-start justify-center gap-8">
          <div className="space-y-6">
            {/* Hero badge */}
            <p className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1 text-xs uppercase tracking-wide text-zinc-400">
              Comparador de preços de supermercado. {""}
              Parece meio ilegal, mas como o nosso professor diria: “é grey”.
            </p>

            {/* Main heading */}
            <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              Gasta menos.{" "}
              <span className="text-zinc-300">
                Enche o saco.
              </span>
            </h1>

            {/* Subheading / description */}
            <p className="max-w-xl text-sm text-zinc-400 sm:text-base">
              O <span className="text-zinc-100 font-medium">SacoCheio</span> compara os preços
              de produtos de supermercado entre várias lojas e mostra onde o teu carrinho fica
              mais barato. Os dados são recolhidos automaticamente via web scraping e organizados
              num painel simples de usar.
            </p>
          </div>

          {/* CTAs */}
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-full bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
            >
              Entrar no painel
            </Link>
            <Link
              href="#how-it-works"
              className="rounded-full border border-zinc-700 px-5 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-zinc-900"
            >
              Ver como funciona
            </Link>
          </div>

          {/* Store cards */}
          <div className="mt-4 grid gap-4 text-xs text-zinc-400 sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Auchan
              </p>
              <p>Recolha automática de preços e produtos da Auchan.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Pingo Doce 
              </p>
              <p>Recolha automática de preços e produtos do Pingo Doce.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Froiz (em desenvolvimento)
              </p>
              <p>Recolha automática de preços e produtos do Froiz.</p>
            </div>
          </div>
        </div>

        <footer className="mt-8 border-t border-zinc-900 pt-4 text-xs text-zinc-500 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <span>
          </span>

          <div className="flex items-center gap-3">
            <a href="/policies/privacy" className="hover:underline">
              Política de Privacidade
            </a>
            <a href="/policies/terms" className="hover:underline">
              Termos de Serviço
            </a>
          </div>
        </footer>
      </section>

      {/* How it works section */}
      <section
        id="how-it-works"
        className="border-t border-zinc-900 bg-zinc-950/95"
      >
        <div className="mx-auto max-w-5xl px-4 py-10">
          <h2 className="text-lg font-medium text-zinc-100">
            Como funciona o SacoCheio
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            Um conjunto de scrapers em Python recolhe os preços de cada loja,
            grava os resultados em ficheiros JSON e envia-os para a base de dados.
            O website lê esses dados e apresenta-os num painel onde é fácil filtrar,
            ordenar e comparar produtos entre supermercados.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Etapa 1 · Scraping
              </p>
              <p className="mt-1">
                Scripts em Python utilizam bibliotecas como{" "}
                <code>BeautifulSoup</code> e <code>selenium</code> para recolher
                dados estruturados das páginas públicas das lojas.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Etapa 2 · Armazenamento
              </p>
              <p className="mt-1">
                Os produtos são normalizados, guardados em JSON e enviados
                em batches para a base de dados central.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Etapa 3 · Dashboard
              </p>
              <p className="mt-1">
                A aplicação Next.js consome a API/BD e apresenta os preços
                num painel claro, permitindo comparar rapidamente entre lojas.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* About section */}
      <section id="about" className="border-t border-zinc-900 bg-zinc-950">
        <div className="mx-auto max-w-5xl px-4 py-10">
          <h2 className="text-lg font-medium text-zinc-100">
            Sobre este projeto
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            O SacoCheio é um projeto académico focado em experimentar técnicas de
            web scraping e visualização de dados aplicadas a preços de supermercado.
            A arquitetura separa claramente a recolha de dados (Python) da
            visualização (Next.js), mantendo o painel simples, rápido e fácil de manter.
          </p>
        </div>
      </section>
    </main>
  );
}

// app/page.tsx

import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero section */}
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10">
        <nav className="mb-10 flex items-center justify-between text-sm text-zinc-400">
          <span className="font-semibold tracking-tight text-zinc-200">
            Saco Cheio
          </span>

          <div className="flex items-center gap-4">
            <Link
              href="#how-it-works"
              className="hover:text-zinc-200 transition-colors"
            >
              Como funciona
            </Link>
            <Link
              href="#about"
              className="hover:text-zinc-200 transition-colors"
            >
              Projeto
            </Link>
          </div>
        </nav>

        <div className="flex flex-1 flex-col items-start justify-center gap-8">
          <div className="space-y-4">

            <p className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1 text-xs uppercase tracking-wide text-zinc-400">
              Pode parecer meio ilegal, mas como o nosso professor diria: “é grey”.
            </p>

            <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              Um painel “grey” para{" "}
              <span className="text-zinc-300 underline decoration-zinc-600">
                dados de web scraping
              </span>
              .
            </h1>

            <p className="max-w-xl text-sm text-zinc-400 sm:text-base">
              PRECISAMOS DE UMA DESCRIÇÃO AQUI{" "}
              <span className="text-zinc-200">O QUE ACHAM?</span> BLA BLA BLA
              BLA BLA BLA BLA BLA BLA BLA BLA BLA BLA.
            </p>
          </div>

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

          <div className="mt-4 grid gap-4 text-xs text-zinc-400 sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Auchan
              </p>
              <p>Scraping dos dados da Auchan.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Froiz
              </p>
              <p>Scraping dos dados da Froiz.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Pingo Doce (TODO)
              </p>
              <p>Scraping dos dados do Pingo Doce.</p>
            </div>
          </div>
        </div>

        <footer className="mt-8 border-t border-zinc-900 pt-4 text-xs text-zinc-500 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <span>
            Desenvolvido por Bruno Carrulo, Duarte Ferreira, Eduardo Bártolo, Miguel Barreto
          </span>

          <div className="flex items-center gap-3">
            <a href="/policies/privacy" className="hover:underline">Política de Privacidade</a>
            <a href="/policies/terms" className="hover:underline">Termos de Serviço</a>
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
            Como funciona o pipeline
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            Um script em Python faz scraping da página pública da loja escolhida,
            extrai a informação necessária e grava-a num ficheiro JSON.
            O ficheiro JSON é depois enviado para a Base de Dados em batches.
            O website lê os produtos da BD e apresenta os dados
            num painel organizado.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Etapa 1 · Scraping
              </p>
              <p className="mt-1">
                Python utiliza bibliotecas como{" "}
                <code>BeautifulSoup</code> para recolher dados estruturados de
                páginas públicas.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Etapa 2 · Armazenamento
              </p>
              <p className="mt-1">
                O scraper guarda os resultados processados.
                Envia batches para a base de dados
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Etapa 3 · Dashboard
              </p>
              <p className="mt-1">
                A aplicação Next.js carrega os produtos da BD e apresenta os
                dados num painel claro e intuitivo.
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
            Este é um projeto académico focado em Web Scraping.
            Criámos uma separação clara entre recolha de dados e visualização.
            A lógica de scraping corre em Python,
            enquanto o frontend consome apenas os JSONs,
            mantendo o site simples, rápido e limpo.
          </p>
        </div>
      </section>
    </main>
  );
}

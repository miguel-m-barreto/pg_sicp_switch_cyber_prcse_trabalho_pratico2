// app/page.tsx

import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero section */}
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10">
        <nav className="mb-10 flex items-center justify-between text-sm text-zinc-400">
          <span className="font-semibold tracking-tight text-zinc-200">
            GreyScrape
          </span>

          <div className="flex items-center gap-4">
            <Link
              href="#how-it-works"
              className="hover:text-zinc-200 transition-colors"
            >
              How it works
            </Link>
            <Link
              href="#about"
              className="hover:text-zinc-200 transition-colors"
            >
              Project
            </Link>
          </div>
        </nav>

        <div className="flex flex-1 flex-col items-start justify-center gap-8">
          <div className="space-y-4">

            <p className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1 text-xs uppercase tracking-wide text-zinc-400">
              It might seem a little illegal, but as our professor would say, "It's gray."
            </p>

            <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              A grey dashboard for{" "}
              <span className="text-zinc-300 underline decoration-zinc-600">
                web scraping data
              </span>
              .
            </h1>

            <p className="max-w-xl text-sm text-zinc-400 sm:text-base">
              WE NEED SOME DESCRIPTION HERE{" "}
              <span className="text-zinc-200">WHAT DO YOU THINK?</span> BLA BLA
              BLA BLA BLA BLA BLA BLA BLA BLA BLA BLA BLA BLA.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-full bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
            >
              Enter dashboard
            </Link>
            <Link
              href="#how-it-works"
              className="rounded-full border border-zinc-700 px-5 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-zinc-900"
            >
              See how it works
            </Link>
          </div>

          <div className="mt-4 grid gap-4 text-xs text-zinc-400 sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Auchan
              </p>
              <p>Scrape data from Auchan.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Froiz (TODO)
              </p>
              <p>Scrape data from Froiz</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Pingo Doce (TODO)
              </p>
              <p>Scrape data from Pingo Doce</p>
            </div>
          </div>
        </div>

        <footer className="mt-8 border-t border-zinc-900 pt-4 text-xs text-zinc-500">
          Built by Bruno Carrulo, Duarte Ferreira, Eduardo Bártolo, Miguel Barreto
        </footer>
      </section>

      {/*
          <div className="mt-4 grid gap-4 text-xs text-zinc-400 sm:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Backend
              </p>
              <p>Python scraper → JSON in <code>data/scraped.json</code>.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Frontend
              </p>
              <p>Next.js App Router + Tailwind, fully server-rendered.</p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
              <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-zinc-500">
                Scope
              </p>
              <p>Read-only dashboard for academic, non-commercial use.</p>
            </div>
          </div>
        </div>

        <footer className="mt-8 border-t border-zinc-900 pt-4 text-xs text-zinc-500">
          Built for a school assignment using public or synthetic data only.
        </footer>
      </section>
      */}

      {/* How it works section */}
      <section
        id="how-it-works"
        className="border-t border-zinc-900 bg-zinc-950/95"
      >
        <div className="mx-auto max-w-5xl px-4 py-10">
          <h2 className="text-lg font-medium text-zinc-100">
            How the pipeline works
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            A Python script will scrape the chosen store public page, extracts the
            required information, and writes it to a JSON file.
            The website reads that file on the server side and renders
            the data in a dashboard page.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Step 1 · Scraping
              </p>
              <p className="mt-1">
                Python uses libraries like {" "}
                <code>BeautifulSoup</code> to collect structured data from
                public pages.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Step 2 · Storage
              </p>
              <p className="mt-1">
                The scraper saves the processed results.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Step 3 · Dashboard
              </p>
              <p className="mt-1">
                The Next.js app loads the JSON on the server and displays it in
                a "grey" dashboard for analysis and presentation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* About section */}
      <section id="about" className="border-t border-zinc-900 bg-zinc-950">
        <div className="mx-auto max-w-5xl px-4 py-10">
          <h2 className="text-lg font-medium text-zinc-100">
            About this project
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            This is a school project focused on Data Scraping.
            We made it while still demonstrating a clean separation
            between data collection and visualization.
            The scraping logic runs in Python,
            while the frontend only consumes the generated JSON,
            which keeps the website simple, fast, and clean.
          </p>
        </div>
      </section>
    </main>
  );
}

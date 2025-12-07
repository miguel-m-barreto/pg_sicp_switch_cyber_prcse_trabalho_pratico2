// ui/app/dashboard/[store]/loading.tsx
export default function StoreLoading() {
  return (
    <main className="relative min-h-screen bg-zinc-950 text-zinc-100">
      {/* OVERLAY CENTRAL */}
      <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-zinc-950/0 backdrop-blur-sm">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-zinc-700 border-t-zinc-300"></div>
        <p className="mt-3 text-sm text-zinc-400">A carregar</p>
      </div>

      {/* SKELETON CONTENT */}
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-10">
        {/* Header skeleton */}
        <nav className="mb-8 flex items-center justify-between text-sm text-zinc-400">
          <div className="h-4 w-24 rounded bg-zinc-800 animate-pulse" />
          <div className="h-3 w-52 rounded bg-zinc-900 animate-pulse" />
        </nav>

        {/* Title + description skeleton */}
        <div className="mb-6 space-y-3">
          <div className="h-7 w-64 rounded bg-zinc-800 animate-pulse" />
          <div className="h-3 w-96 rounded bg-zinc-900 animate-pulse" />

          {/* Search bar fake */}
          <div className="mt-2 flex gap-2">
            <div className="h-9 flex-1 rounded-xl bg-zinc-900 animate-pulse" />
            <div className="h-9 w-24 rounded-xl bg-zinc-800 animate-pulse" />
          </div>
        </div>

        {/* Table skeleton */}
        <div className="flex-1">
          <div className="space-y-3 animate-pulse">
            <div className="flex items-center justify-between text-xs text-zinc-500">
              <div className="h-3 w-40 rounded bg-zinc-900" />
              <div className="h-3 w-24 rounded bg-zinc-900" />
            </div>

            <div className="rounded-xl border border-zinc-900 bg-zinc-950/60">
              {/* Header row */}
              <div className="grid grid-cols-[minmax(0,2fr),minmax(0,1fr),minmax(0,1fr)] gap-3 border-b border-zinc-900 px-4 py-2">
                <div className="h-3 w-24 rounded bg-zinc-900" />
                <div className="h-3 w-16 rounded bg-zinc-900 justify-self-end" />
                <div className="h-3 w-24 rounded bg-zinc-900 justify-self-end" />
              </div>

              {/* Fake rows */}
              <div className="divide-y divide-zinc-900">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[minmax(0,2fr),minmax(0,1fr),minmax(0,1fr)] gap-3 px-4 py-3"
                  >
                    <div className="h-3 w-56 rounded bg-zinc-900" />
                    <div className="h-3 w-10 rounded bg-zinc-900 justify-self-end" />
                    <div className="h-3 w-16 rounded bg-zinc-900 justify-self-end" />
                  </div>
                ))}
              </div>
            </div>

            <div className="h-2 w-40 rounded bg-zinc-900" />
          </div>
        </div>
      </section>
    </main>
  );
}

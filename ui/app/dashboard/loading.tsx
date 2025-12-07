// ui/app/dashboard/loading.tsx
export default function DashboardLoading() {
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
        <nav className="mb-8 flex items-center justify-between text-sm 
                text-zinc-300 bg-zinc-900/40 px-3 py-2 rounded-xl">          <div className="h-4 w-24 rounded bg-zinc-800 animate-pulse" />
          <div className="h-3 w-40 rounded bg-zinc-900 animate-pulse" />
        </nav>

        {/* Title skeleton */}
        <div className="mb-8 space-y-3">
          <div className="h-7 w-56 rounded bg-zinc-800 animate-pulse" />
          <div className="h-3 w-96 rounded bg-zinc-900 animate-pulse" />
          <div className="h-3 w-80 rounded bg-zinc-900 animate-pulse" />
        </div>

        {/* Cards skeleton */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-3 text-sm animate-pulse"
            >
              <div className="mb-3 space-y-1.5">
                <div className="h-3 w-20 rounded bg-zinc-800" />
                <div className="h-3 w-32 rounded bg-zinc-900" />
              </div>

              <div className="space-y-1.5">
                {Array.from({ length: 4 }).map((_, j) => (
                  <div
                    key={j}
                    className="flex items-center justify-between gap-2 rounded-md px-2 py-1"
                  >
                    <div className="h-3 w-32 rounded bg-zinc-900" />
                    <div className="h-3 w-10 rounded bg-zinc-900" />
                  </div>
                ))}
              </div>

              <div className="mt-3 h-2 w-28 rounded bg-zinc-900" />
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

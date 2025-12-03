// components/Header.tsx
import Link from "next/link";

export default function Header({ subtitle }: { subtitle?: string }) {
  return (
    <nav className="mb-8 flex items-center justify-between text-sm text-zinc-400">
      <Link href="/" className="font-semibold tracking-tight text-zinc-200">
        GreyScrape
      </Link>

      {subtitle && (
        <span className="text-xs text-zinc-500">{subtitle}</span>
      )}
    </nav>
  );
}

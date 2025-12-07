// components/Header.tsx
import Link from "next/link";
import Image from "next/image";

export default function Header({
  subtitle,
  sticky = true,
}: {
  subtitle?: React.ReactNode;
  sticky?: boolean;
}) {
  return (
    <header
      className={`w-full px-6 py-4 flex items-center justify-between text-zinc-200 bg-zinc-950/80 backdrop-blur-sm border-b border-zinc-900
      ${sticky ? "sticky top-0 z-30" : ""}`}
    >
      <Link href="/" className="flex items-center gap-3">
        <Image src="/favicon.png" width={24} height={24} alt="" />
        <span className="text-lg font-semibold tracking-tight">Saco Cheio</span>
      </Link>

      {subtitle && (
        <span className="text-sm text-zinc-400">{subtitle}</span>
      )}
    </header>
  );
}


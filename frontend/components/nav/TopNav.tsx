import Link from "next/link";
import { Activity } from "lucide-react";
import { WalletButton } from "@/components/wallet/WalletButton";

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 backdrop-blur bg-zinc-950/70 border-b border-zinc-800">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Activity className="w-5 h-5 text-violet-400" />
          <span className="bg-gradient-to-r from-violet-300 to-emerald-300 bg-clip-text text-transparent">
            AgentVault
          </span>
        </Link>
        <nav className="hidden md:flex items-center gap-1 text-sm text-zinc-400">
          <Link href="/browse" className="px-3 py-1 hover:text-zinc-100">Browse</Link>
          <Link href="/list" className="px-3 py-1 hover:text-zinc-100">List</Link>
          <Link href="/agent" className="px-3 py-1 hover:text-zinc-100">Agent demo</Link>
          <Link href="/dashboard" className="px-3 py-1 hover:text-zinc-100">Dashboard</Link>
        </nav>
        <WalletButton />
      </div>
    </header>
  );
}

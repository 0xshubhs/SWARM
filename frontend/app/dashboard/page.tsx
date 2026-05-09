"use client";
import Link from "next/link";
import { useWallet } from "@solana/wallet-adapter-react";
import { Wallet } from "lucide-react";

import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import { ListingGrid } from "@/components/listings/ListingGrid";
import { Button } from "@/components/ui/Button";

export default function DashboardPage() {
  const wallet = useWallet();
  if (!wallet.publicKey) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <EmptyState
          icon={Wallet}
          title="Connect a wallet"
          description="Sign in with Phantom or Solflare to see your listings, purchases, and audit trail."
        />
      </main>
    );
  }
  const seller = wallet.publicKey.toBase58();

  return (
    <main className="max-w-6xl mx-auto px-6 py-10 space-y-10">
      <header>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-zinc-400 mt-1">
          Your listings, purchases, earnings, and decision audit trail.
        </p>
      </header>

      <Section title="Your listings" cta={<Link href="/list"><Button size="sm">New listing</Button></Link>}>
        <ListingGrid filters={{ seller, active: true }} />
      </Section>

      <Section title="Recent purchases">
        <Card>
          <CardContent>
            <p className="text-sm text-zinc-400">
              Your active licenses appear here as the indexer mirrors on-chain MemoryLicense PDAs.
            </p>
          </CardContent>
        </Card>
      </Section>

      <Section title="Audit trail">
        <Card>
          <CardContent>
            <p className="text-sm text-zinc-400">
              Decisions you've anchored on-chain via{" "}
              <Link href="/dashboard/decisions" className="underline">/dashboard/decisions</Link>{" "}
              show their context hashes and Arweave links here.
            </p>
          </CardContent>
        </Card>
      </Section>
    </main>
  );
}

function Section({
  title,
  cta,
  children,
}: {
  title: string;
  cta?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xl font-semibold">{title}</h2>
        {cta}
      </div>
      {children}
    </section>
  );
}

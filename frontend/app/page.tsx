import Link from "next/link";
import { ArrowRight, Database, Lock, Activity } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function LandingPage() {
  return (
    <main>
      <section className="relative px-6 py-24 md:py-40">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
            Persistent memory for{" "}
            <span className="bg-gradient-to-r from-violet-400 to-emerald-400 bg-clip-text text-transparent">
              autonomous Solana agents
            </span>
          </h1>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto mb-10">
            AgentVault makes AI agent memory ownable, transferable, and verifiable.
            TurboQuant-compressed KV cache, anchored on Solana, served on Arweave.
          </p>
          <div className="flex gap-4 justify-center">
            <Button size="lg">
              <Link href="/browse" className="inline-flex items-center">
                Browse memories <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
            <Button size="lg" variant="outline">
              <Link href="/agent">See live agent demo</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="px-6 py-16 border-t border-zinc-800">
        <div className="max-w-5xl mx-auto grid md:grid-cols-3 gap-8">
          <Pillar
            icon={Database}
            title="Audit Trail"
            description="DAO treasury agents commit decision context on-chain. Immutable, queryable, transferable."
          />
          <Pillar
            icon={Lock}
            title="Cold Start Elimination"
            description="Senior agents sell their learned protocol context. New agents skip days of training."
          />
          <Pillar
            icon={Activity}
            title="Memory Marketplace"
            description="Trained agent memory becomes a tradeable asset. Buy expertise; sell what you've taught."
          />
        </div>
      </section>
    </main>
  );
}

function Pillar({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Database;
  title: string;
  description: string;
}) {
  return (
    <div>
      <Icon className="w-6 h-6 mb-4 text-violet-400" />
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-zinc-400 leading-relaxed">{description}</p>
    </div>
  );
}

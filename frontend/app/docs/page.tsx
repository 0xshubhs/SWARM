import Link from "next/link";

export default function DocsPage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-10 prose prose-invert">
      <h1 className="text-3xl font-bold">How AgentVault works</h1>
      <p className="text-zinc-400 mt-2">
        AgentVault is a marketplace and audit layer for AI agent memory. The system has six layers:
      </p>
      <ol className="mt-4 space-y-2 text-zinc-300">
        <li><strong>Solana program</strong> — atomic registry, payments, audit anchoring.</li>
        <li><strong>Backend (FastAPI)</strong> — orchestration, x402 sandbox, indexer.</li>
        <li><strong>TurboQuant worker</strong> — KV cache compression on GPU.</li>
        <li><strong>Frontend</strong> — this site.</li>
        <li><strong>Buyer agent</strong> — autonomous purchaser; the demo star.</li>
        <li><strong>CLI</strong> — power-user seller tool.</li>
      </ol>
      <p className="mt-4 text-zinc-400">
        See <Link href="/agent" className="underline">/agent</Link> for the live demo.
      </p>
    </main>
  );
}

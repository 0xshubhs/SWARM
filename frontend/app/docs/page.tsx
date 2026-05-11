import Link from "next/link";

const CLI_VERSION = "0.1.0";
const CLI_BINARY = "/cli/avlt-darwin-arm64";
const CLI_SHA256 = "0416692022b3168a4708edfcc9fe9108c6c432d374807072826d52f9d223484c";
const CLI_SIZE_MB = "2.2";

export default function DocsPage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-10 space-y-12">
      <header>
        <h1 className="text-3xl font-bold text-zinc-50">How AgentVault works</h1>
        <p className="text-zinc-400 mt-2">
          A marketplace and audit layer for AI agent memory. The system has six layers:
        </p>
      </header>

      <section className="space-y-4">
        <ol className="space-y-2 text-zinc-300 list-decimal list-inside">
          <li><strong>Solana program</strong> — atomic registry, payments, audit anchoring.</li>
          <li><strong>Backend (FastAPI)</strong> — orchestration, x402 sandbox, indexer.</li>
          <li><strong>TurboQuant worker</strong> — KV cache compression on GPU.</li>
          <li><strong>Frontend</strong> — this site.</li>
          <li><strong>Buyer agent</strong> — autonomous purchaser; the demo star.</li>
          <li><strong>CLI</strong> — power-user seller tool.</li>
        </ol>
        <p className="text-zinc-400">
          See <Link href="/agent" className="underline text-violet-400 hover:text-violet-300">/agent</Link> for the live demo.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-zinc-50">Get the CLI (<code className="text-violet-400">avlt</code>)</h2>
        <p className="text-zinc-400">
          Power-user seller tool. Captures KV cache from a local LMCache instance, compresses
          via the backend, uploads to Arweave, and creates an on-chain listing.
        </p>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-5 space-y-4">
          <div className="flex items-baseline justify-between flex-wrap gap-3">
            <div>
              <div className="text-sm uppercase tracking-wide text-zinc-500">macOS · Apple Silicon</div>
              <div className="text-zinc-100 font-mono text-sm mt-1">avlt v{CLI_VERSION} · {CLI_SIZE_MB} MB</div>
            </div>
            <a
              href={CLI_BINARY}
              download="avlt"
              className="inline-flex items-center justify-center h-10 px-5 rounded-md bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
            >
              Download avlt
            </a>
          </div>
          <div className="text-xs text-zinc-500 font-mono break-all">
            <span className="text-zinc-400">sha256</span> {CLI_SHA256}
          </div>
        </div>

        <details className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
          <summary className="cursor-pointer text-zinc-300 text-sm font-medium">After download — make it runnable</summary>
          <pre className="mt-3 text-xs text-zinc-300 bg-zinc-950 rounded p-3 overflow-x-auto"><code>{`mv ~/Downloads/avlt /usr/local/bin/avlt
chmod +x /usr/local/bin/avlt
xattr -d com.apple.quarantine /usr/local/bin/avlt   # macOS Gatekeeper
avlt --help`}</code></pre>
        </details>

        <details className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
          <summary className="cursor-pointer text-zinc-300 text-sm font-medium">Other platforms — build from source</summary>
          <pre className="mt-3 text-xs text-zinc-300 bg-zinc-950 rounded p-3 overflow-x-auto"><code>{`# Requires Rust toolchain (https://rustup.rs)
git clone https://github.com/<your-org>/agentvault
cd agentvault
cargo install --path cli --locked
avlt --help`}</code></pre>
        </details>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-zinc-50">Run everything locally</h2>
        <p className="text-zinc-400">
          Mac-native dev stack: program already on Solana devnet, four local services.
          See <code className="text-zinc-300">RUN_LOCAL.md</code> at the repo root for the full reference.
        </p>
        <ol className="space-y-3 text-sm text-zinc-300 list-decimal list-inside">
          <li>
            <strong>Ollama</strong> serves Qwen 2.5 — usually already running as a daemon.
            <pre className="mt-1 text-xs text-zinc-400 bg-zinc-950 rounded p-2 overflow-x-auto"><code>ollama pull qwen2.5:7b && ollama serve &</code></pre>
          </li>
          <li>
            <strong>Worker</strong> — TurboQuant compression on :8001.
            <pre className="mt-1 text-xs text-zinc-400 bg-zinc-950 rounded p-2 overflow-x-auto"><code>cd worker && uv run uvicorn worker.main:app --reload --port 8001</code></pre>
          </li>
          <li>
            <strong>Backend</strong> — FastAPI on :8000.
            <pre className="mt-1 text-xs text-zinc-400 bg-zinc-950 rounded p-2 overflow-x-auto"><code>cd backend && uv run uvicorn api.main:app --reload --port 8000</code></pre>
          </li>
          <li>
            <strong>Frontend</strong> — this site on :3000.
            <pre className="mt-1 text-xs text-zinc-400 bg-zinc-950 rounded p-2 overflow-x-auto"><code>cd frontend && pnpm dev</code></pre>
          </li>
        </ol>
        <p className="text-zinc-400 text-sm">
          Or, from the repo root: <code className="text-zinc-200">pnpm dev</code> (Turborepo orchestrates all four).
        </p>
      </section>
    </main>
  );
}

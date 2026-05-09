# AgentVault

Solana-native marketplace and audit layer for AI agent memory. Sellers compress LLM KV cache via TurboQuant, store on Arweave, and list on Solana. Buyers (humans or autonomous agents) discover, preview, and purchase memories — atomically on-chain.

> Read [`docs/00_ARCHITECTURE.md`](docs/00_ARCHITECTURE.md) first. The other six docs are self-contained build briefs for each component.

## Repo layout

```
agentvault/
├── docs/                 # Build documents (00–06)
├── programs/agentvault/  # Solana Anchor program (Rust)
├── backend/              # FastAPI server      (Python, Railway)
├── worker/               # TurboQuant compress (Python, RunPod GPU)
├── frontend/             # Next.js marketplace (TypeScript, Vercel)
├── buyer-agent/          # Autonomous buyer    (TypeScript)
├── cli/                  # Seller CLI          (Rust, optional v2)
├── shared/types/         # Generated IDL + shared TS types
├── scripts/              # Deploy / seed / runpod setup
├── tests/                # Anchor integration tests
└── .github/workflows/    # CI
```

## Polyglot turborepo

This is a **polyglot monorepo** managed by **pnpm + Turborepo** for JS/TS, **Cargo workspace** for Rust, and **uv** for Python. Each non-JS package exposes a thin `package.json` shim so `pnpm dev` / `pnpm build` orchestrate everything from one root.

| Package         | Language   | Native build         | Shim'd via            |
| --------------- | ---------- | -------------------- | --------------------- |
| frontend        | TypeScript | `next`               | (native)              |
| buyer-agent     | TypeScript | `tsc` / `tsx`        | (native)              |
| shared/types    | TypeScript | `tsc`                | (native)              |
| backend         | Python     | `uv run uvicorn ...` | `package.json` script |
| worker          | Python     | `uv run uvicorn ...` | `package.json` script |
| programs/agentvault | Rust   | `anchor build`       | root `pnpm anchor:*`  |
| cli             | Rust       | `cargo build`        | root `pnpm cargo:*`   |

## Prerequisites

```bash
# Node / pnpm
nvm install              # respects .nvmrc
npm i -g pnpm@9.12.0

# Python (uv)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Solana + Anchor
sh -c "$(curl -sSfL https://release.solana.com/v1.18.0/install)"
cargo install --git https://github.com/coral-xyz/anchor anchor-cli --force

# Configure Solana
solana config set --url devnet
solana-keygen new --outfile ~/.config/solana/id.json
solana airdrop 5
```

## First-time setup

```bash
pnpm install              # installs JS/TS deps across the workspace
pnpm py:install           # installs Python deps for backend + worker
cargo build --workspace   # builds Rust crates (program + CLI)
cp .env.example .env      # fill in values
```

## Daily workflow

```bash
pnpm dev          # turbo runs all `dev` tasks (frontend + backend + worker + buyer-agent)
pnpm build        # turbo build graph: shared/types → consumers
pnpm typecheck
pnpm lint
pnpm test

pnpm anchor:build # builds the Solana program
pnpm anchor:test  # runs Anchor tests against local-test-validator
pnpm anchor:deploy
```

## Deployment targets

| Component | Target                        |
| --------- | ----------------------------- |
| program   | Solana devnet → mainnet       |
| backend   | Railway                       |
| worker    | RunPod (GPU) / Railway (CPU)  |
| frontend  | Vercel                        |

See [`docs/00_ARCHITECTURE.md`](docs/00_ARCHITECTURE.md) §5 for the rationale behind each choice.
# SWARM

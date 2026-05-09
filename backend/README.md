# backend

FastAPI server, Solana indexer, and Redis job runner. See [`../docs/02_BACKEND.md`](../docs/02_BACKEND.md).

```bash
uv sync --all-extras
cp .env.example .env
uv run uvicorn api.main:app --reload
```

Or from repo root:

```bash
pnpm --filter @agentvault/backend dev
```

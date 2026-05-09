"""TurboQuant worker entry point. Build per docs/03_TURBOQUANT_WORKER.md."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="AgentVault Worker", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# TODO: implement /compress, /decompress, /benchmark, /load, /inference
# See docs/03_TURBOQUANT_WORKER.md §3 (architecture) and §5 (API surface).

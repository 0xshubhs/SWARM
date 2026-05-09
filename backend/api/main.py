"""FastAPI entry point. Build out per docs/02_BACKEND.md."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AgentVault API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# TODO: wire routers from api.routers (listings, sandbox, upload, ws, audit)
# See docs/02_BACKEND.md §3 for the full file structure.

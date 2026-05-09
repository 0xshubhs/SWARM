"""FastAPI entry point. Wires routers, CORS, lifespan, and shared resources."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.deps import make_redis
from api.routers import (
    decisions,
    internal,
    listings,
    pricing,
    sandbox,
    upload,
    verify,
    ws,
    ws_auth,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=settings.LOG_LEVEL.upper())
    app.state.redis = make_redis()
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(
    title="AgentVault API",
    version="0.1.0",
    description="Marketplace + audit anchoring for AI agent memory.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-PAYMENT-REQUIREMENTS"],
)


@app.get("/health")
@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.ENVIRONMENT}


app.include_router(pricing.router)
app.include_router(listings.router)
app.include_router(upload.router)
app.include_router(sandbox.router)
app.include_router(verify.router)
app.include_router(decisions.router)
app.include_router(ws_auth.router)
app.include_router(ws.router)
app.include_router(internal.router)

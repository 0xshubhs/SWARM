"""FastAPI server entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI

from .config import settings
from .routes import benchmark, compress, decompress, health, inference, load


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("AgentVault Worker starting...")
    print(f"  CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"  vLLM endpoint: {settings.VLLM_ENDPOINT}")
    print(f"  Model: {settings.HF_MODEL_ID}")
    yield
    print("AgentVault Worker shutting down...")


app = FastAPI(
    title="AgentVault Worker",
    description="TurboQuant KV-cache compression and inference service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["health"])
app.include_router(compress.router, tags=["compress"])
app.include_router(decompress.router, tags=["decompress"])
app.include_router(load.router, tags=["load"])
app.include_router(inference.router, tags=["inference"])
app.include_router(benchmark.router, tags=["benchmark"])
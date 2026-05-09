"""Shared FastAPI dependencies (DB, Redis, x402 handler, etc)."""
from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.x402.handler import X402Handler
from runtime.vllm_client import VLLMClient
from storage.arweave import ArweaveClient
from storage.db import SessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_redis(request: Request) -> aioredis.Redis:
    pool: aioredis.Redis = request.app.state.redis
    return pool


def make_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=False)


def get_x402() -> X402Handler:
    return X402Handler(
        facilitator_url=settings.X402_FACILITATOR_URL,
        treasury_address=settings.PLATFORM_TREASURY,
        network=f"solana-{settings.SOLANA_NETWORK}",
        usdc_mint=settings.USDC_MINT,
    )


def get_runtime() -> VLLMClient:
    return VLLMClient(endpoint=settings.VLLM_ENDPOINT, api_key=settings.VLLM_API_KEY)


def get_arweave() -> ArweaveClient:
    return ArweaveClient(sidecar_url=settings.IRYS_SIDECAR_URL)

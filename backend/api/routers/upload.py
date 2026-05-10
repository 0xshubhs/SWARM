"""Seller upload flow: init → blob (with WS progress) → finalize.

The actual compression + arweave upload happens in a Redis-backed worker
(see jobs/tasks.py). The frontend listens on the upload WS channel for
progress; the final on-chain instruction is built here in /finalize and
returned for the user's wallet to sign.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from jose import jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.deps import get_db, get_redis
from api.routers.pricing import FeeBreakdown, calculate_fee
from jobs.queue import enqueue_compress
from storage.models import CompressJob

router = APIRouter(prefix="/v1/upload", tags=["upload"])


class UploadInitRequest(BaseModel):
    seller_pubkey: str
    expected_size_bytes: int


class UploadInitResponse(BaseModel):
    upload_id: str
    fee_breakdown: FeeBreakdown
    fee_payment_address: str
    ws_token: str
    ws_channel: str


class UploadFinalizeRequest(BaseModel):
    upload_id: str
    seller_pubkey: str
    title: str
    tags: list[str]
    price_usdc: int
    sandbox_price_usdc: int


class ListMemoryArgs(BaseModel):
    arweave_tx: str
    content_hash: list[int]
    model_id: str
    quant_seed: int
    bits_per_channel: int
    seq_len: int
    price_usdc: int
    sandbox_price_usdc: int
    title: str
    tags: list[str]


class UploadFinalizeResponse(BaseModel):
    listing_pda: str
    config_pda: str
    program_id: str
    args: ListMemoryArgs


def _mint_ws_token(channel: str) -> str:
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    return jwt.encode(
        {"sub": channel, "iat": now_ms, "exp": now_ms + 5 * 60_000},
        settings.WS_TOKEN_SECRET,
        algorithm="HS256",
    )


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    body: UploadInitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadInitResponse:
    upload_id = str(uuid4())
    fee = calculate_fee(body.expected_size_bytes)
    job = CompressJob(
        id=upload_id,
        seller=body.seller_pubkey,
        status="queued",
        input_size_bytes=body.expected_size_bytes,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(job)
    await db.commit()

    return UploadInitResponse(
        upload_id=upload_id,
        fee_breakdown=fee,
        fee_payment_address=settings.PLATFORM_TREASURY,
        ws_token=_mint_ws_token(f"upload:{upload_id}"),
        ws_channel=f"/v1/ws/upload/{upload_id}",
    )


@router.post("/blob/{upload_id}", status_code=202)
async def upload_blob(
    upload_id: str,
    blob: UploadFile,
    bg: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict:
    job = await db.get(CompressJob, upload_id)
    if job is None:
        raise HTTPException(404, "upload_id unknown — call /v1/upload/init first")
    if job.status != "queued":
        raise HTTPException(409, f"upload already {job.status}")

    raw = await blob.read()
    job.status = "running"
    job.input_size_bytes = len(raw)
    await db.commit()

    # Hand off to the worker via Redis. We don't await — the worker publishes
    # progress to events:upload:{id}, the WS gateway forwards.
    await enqueue_compress(redis_client, upload_id, raw)
    return {"upload_id": upload_id, "status": "running"}


@router.post("/finalize", response_model=UploadFinalizeResponse)
async def finalize_upload(
    body: UploadFinalizeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadFinalizeResponse:
    job = await db.get(CompressJob, body.upload_id)
    if job is None:
        raise HTTPException(404, "upload_id unknown")
    if job.status != "done":
        raise HTTPException(409, f"upload not done yet (status={job.status})")
    if job.content_hash is None or job.arweave_tx is None:
        raise HTTPException(500, "compress job is missing hash or arweave_tx")

    from solders.pubkey import Pubkey

    from chain.client import program_id

    pid = program_id()
    seller_pk = Pubkey.from_string(body.seller_pubkey)
    config_pda, _ = Pubkey.find_program_address([b"config"], pid)
    listing_pda, _ = Pubkey.find_program_address(
        [b"listing", bytes(seller_pk), bytes(job.content_hash)],
        pid,
    )

    args = ListMemoryArgs(
        arweave_tx=job.arweave_tx,
        content_hash=list(job.content_hash),
        model_id=settings.HF_MODEL_ID if hasattr(settings, "HF_MODEL_ID") else "qwen2.5-7b-instruct",
        quant_seed=int.from_bytes(job.content_hash[:8], "little") if job.content_hash else 0,
        bits_per_channel=35,
        seq_len=max(0, (job.input_size_bytes or 0) // (28 * 2 * 4 * 128 * 2)),
        price_usdc=body.price_usdc,
        sandbox_price_usdc=body.sandbox_price_usdc,
        title=body.title,
        tags=body.tags,
    )

    return UploadFinalizeResponse(
        listing_pda=str(listing_pda),
        config_pda=str(config_pda),
        program_id=settings.AGENTVAULT_PROGRAM_ID,
        args=args,
    )

"""Audit endpoint: 'does AgentVault know about this hash?'"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from storage.models import Decision, Listing

router = APIRouter(prefix="/v1/verify", tags=["verify"])


class VerifyResponse(BaseModel):
    found: bool
    kind: str | None = None
    on_chain_pda: str | None = None
    arweave_tx: str | None = None
    anchored_at_slot: int | None = None
    anchored_at: datetime | None = None


@router.get("/{content_hash}", response_model=VerifyResponse)
async def verify_hash(
    content_hash: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyResponse:
    try:
        hash_bytes = bytes.fromhex(content_hash)
    except ValueError:
        raise HTTPException(400, "content_hash must be hex")
    if len(hash_bytes) != 32:
        raise HTTPException(400, "content_hash must be 32 bytes (64 hex chars)")

    listing = (
        await db.execute(select(Listing).where(Listing.content_hash == hash_bytes))
    ).scalar_one_or_none()
    if listing is not None:
        return VerifyResponse(
            found=True,
            kind="memory_listing",
            on_chain_pda=listing.id,
            arweave_tx=listing.arweave_tx,
            anchored_at_slot=listing.on_chain_slot,
            anchored_at=listing.created_at,
        )

    decision = (
        await db.execute(select(Decision).where(Decision.context_hash == hash_bytes))
    ).scalar_one_or_none()
    if decision is not None:
        return VerifyResponse(
            found=True,
            kind="decision_record",
            on_chain_pda=decision.id,
            arweave_tx=decision.arweave_tx,
            anchored_at_slot=decision.on_chain_slot,
            anchored_at=decision.timestamp,
        )

    return VerifyResponse(found=False)

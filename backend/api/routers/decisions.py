"""DAO governance audit trail — list DecisionRecord PDAs for an agent."""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from storage.models import Decision

router = APIRouter(prefix="/v1/decisions", tags=["decisions"])


class DecisionDTO(BaseModel):
    id: str
    agent_id: str
    decision_type: str
    context_hash_hex: str
    arweave_tx: str
    decision_data_b64: str
    timestamp: datetime
    on_chain_slot: int


class DecisionsPage(BaseModel):
    items: list[DecisionDTO]
    next_cursor: str | None


@router.get("/{agent_id}", response_model=DecisionsPage)
async def list_decisions(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    decision_type: str | None = None,
    from_slot: int | None = Query(default=None, ge=0),
    to_slot: int | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> DecisionsPage:
    stmt = select(Decision).where(Decision.agent_id == agent_id)
    if decision_type:
        stmt = stmt.where(Decision.decision_type == decision_type)
    if from_slot is not None:
        stmt = stmt.where(Decision.on_chain_slot >= from_slot)
    if to_slot is not None:
        stmt = stmt.where(Decision.on_chain_slot <= to_slot)
    if cursor:
        stmt = stmt.where(Decision.id > cursor)

    stmt = stmt.order_by(Decision.timestamp.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()

    next_cursor = rows[limit - 1].id if len(rows) > limit else None
    rows = rows[:limit]

    return DecisionsPage(
        items=[
            DecisionDTO(
                id=r.id,
                agent_id=r.agent_id,
                decision_type=r.decision_type,
                context_hash_hex=r.context_hash.hex(),
                arweave_tx=r.arweave_tx,
                decision_data_b64=base64.b64encode(r.decision_data).decode(),
                timestamp=r.timestamp,
                on_chain_slot=r.on_chain_slot,
            )
            for r in rows
        ],
        next_cursor=next_cursor,
    )

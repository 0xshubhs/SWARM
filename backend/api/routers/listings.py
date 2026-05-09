"""Marketplace listing browse + detail.

Reads from Supabase (the indexed mirror of on-chain MemoryListing PDAs).
Writes never go through this router — those are done by the seller's
wallet client-side; the indexer mirrors back into Postgres.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from storage.models import Listing

router = APIRouter(prefix="/v1/listings", tags=["listings"])


class ListingDTO(BaseModel):
    id: str
    seller: str
    title: str
    model_id: str
    tags: list[str]
    price_usdc: int
    sandbox_price_usdc: int
    arweave_tx: str
    content_hash_hex: str
    quant_seed: int
    bits_per_channel: int
    seq_len: int
    active: bool
    purchases: int
    created_at: datetime


class ListingsPage(BaseModel):
    items: list[ListingDTO]
    next_cursor: str | None


def _to_dto(row: Listing) -> ListingDTO:
    return ListingDTO(
        id=row.id,
        seller=row.seller,
        title=row.title,
        model_id=row.model_id,
        tags=list(row.tags),
        price_usdc=row.price_usdc,
        sandbox_price_usdc=row.sandbox_price_usdc,
        arweave_tx=row.arweave_tx,
        content_hash_hex=row.content_hash.hex(),
        quant_seed=row.quant_seed,
        bits_per_channel=row.bits_per_channel,
        seq_len=row.seq_len,
        active=row.active,
        purchases=row.purchases,
        created_at=row.created_at,
    )


@router.get("", response_model=ListingsPage)
async def list_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    tags: str | None = Query(default=None, description="Comma-separated tag filter"),
    model: str | None = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    seller: str | None = None,
    active: bool = True,
    sort: str = Query(default="created_at", pattern="^(created_at|purchases|price)$"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> ListingsPage:
    stmt = select(Listing).where(Listing.active == active)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            stmt = stmt.where(Listing.tags.overlap(tag_list))  # type: ignore[attr-defined]
    if model:
        stmt = stmt.where(Listing.model_id == model)
    if seller:
        stmt = stmt.where(Listing.seller == seller)
    if min_price is not None:
        stmt = stmt.where(Listing.price_usdc >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.price_usdc <= max_price)

    if sort == "purchases":
        stmt = stmt.order_by(Listing.purchases.desc(), Listing.id.asc())
    elif sort == "price":
        stmt = stmt.order_by(Listing.price_usdc.asc(), Listing.id.asc())
    else:
        stmt = stmt.order_by(Listing.created_at.desc(), Listing.id.asc())

    if cursor:
        stmt = stmt.where(Listing.id > cursor)

    stmt = stmt.limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()
    next_cursor: str | None = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].id
        rows = rows[:limit]

    return ListingsPage(items=[_to_dto(r) for r in rows], next_cursor=next_cursor)


@router.get("/{listing_id}", response_model=ListingDTO)
async def get_listing(
    listing_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ListingDTO:
    row = await db.get(Listing, listing_id)
    if row is None:
        raise HTTPException(404, "Listing not found")
    return _to_dto(row)

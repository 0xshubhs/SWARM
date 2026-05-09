"""Deterministic pricing — no ML, transparent fee breakdown."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from api.config import settings

router = APIRouter(prefix="/v1/pricing", tags=["pricing"])


class FeeBreakdown(BaseModel):
    base_usdc: int
    compute_usdc: int
    storage_usdc: int
    total_usdc: int
    currency: str = "USDC"
    decimals: int = 6


def calculate_fee(size_bytes: int) -> FeeBreakdown:
    mb = size_bytes / (1024 * 1024)
    compute = int(mb * settings.PER_MB_COMPUTE_USDC)
    storage = int(mb * settings.PER_MB_STORAGE_USDC)
    base = settings.BASE_FEE_USDC
    return FeeBreakdown(
        base_usdc=base,
        compute_usdc=compute,
        storage_usdc=storage,
        total_usdc=base + compute + storage,
    )


@router.get("", response_model=FeeBreakdown)
async def pricing(size_bytes: int = Query(..., ge=0)) -> FeeBreakdown:
    return calculate_fee(size_bytes)

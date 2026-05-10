"""Health check route."""
from __future__ import annotations

import torch
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    return {
        "status": "ok",
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }
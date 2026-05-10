"""API key authentication middleware."""
from __future__ import annotations

from fastapi import Header, HTTPException

from .config import settings


def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Validate the X-API-Key header matches the configured worker API key."""
    if x_api_key != settings.WORKER_API_KEY:
        raise HTTPException(401, "Invalid API key")
    return x_api_key
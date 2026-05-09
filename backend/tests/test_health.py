"""Sanity-check that the FastAPI app boots and /health responds."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

# Set env so dependencies don't try to connect on import.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

from api.main import app  # noqa: E402


def test_health_responds() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

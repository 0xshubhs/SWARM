"""Bundlr/Irys client. Talks to a Node sidecar that wraps @irys/sdk.

Backend never holds the Bundlr keypair directly — it lives in the sidecar's
process. This split keeps the Python service stateless and the signing key
out of long-lived web workers.
"""
from __future__ import annotations

import base64
from typing import Any

import httpx


class ArweaveClient:
    def __init__(self, sidecar_url: str, gateway: str = "https://arweave.net") -> None:
        self.sidecar_url = sidecar_url.rstrip("/")
        self.gateway = gateway.rstrip("/")

    async def upload(self, blob: bytes, tags: list[dict[str, str]] | None = None) -> str:
        """Returns the Arweave TX id."""
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.sidecar_url}/upload",
                json={
                    "blob": base64.b64encode(blob).decode(),
                    "tags": tags or [],
                },
            )
            resp.raise_for_status()
            return resp.json()["arweave_tx"]

    async def fetch(self, arweave_tx: str) -> bytes:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.get(f"{self.gateway}/{arweave_tx}")
            resp.raise_for_status()
            return resp.content

    async def status(self, arweave_tx: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.gateway}/tx/{arweave_tx}/status")
            resp.raise_for_status()
            return resp.json()

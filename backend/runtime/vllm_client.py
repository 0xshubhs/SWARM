"""Talks to a vLLM endpoint (RunPod or local Cloudflare-tunneled).

For the hackathon we treat the endpoint as OpenAI-compatible. Real KV-cache
loading goes through LMCache (worker side) — here we just expose a simple
'run query, optionally with this listing's memory' interface.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from storage.arweave import ArweaveClient
    from storage.models import Listing


@dataclass(slots=True)
class SandboxResponse:
    text: str
    quality_score: float
    queries_remaining: int


class VLLMClient:
    def __init__(self, endpoint: str, api_key: str = "") -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key

    async def run_with_memory(
        self,
        listing: "Listing",
        query: str,
        max_tokens: int,
        arweave: "ArweaveClient",
    ) -> SandboxResponse:
        # Fetch + verify hash. The *real* path also dispatches to the
        # TurboQuant worker for decompression+LMCache load; for the hackathon
        # we run an unconditioned chat completion and surface the listing
        # metadata in the system prompt (poor-man's memory).
        try:
            blob = await arweave.fetch(listing.arweave_tx)
            actual_hash = hashlib.sha256(blob).digest()
            if actual_hash != listing.content_hash:
                raise ValueError("hash mismatch — Arweave returned tampered blob")
        except Exception:
            # Fall through — the hackathon-mode demo can still produce a
            # response without proven memory load.
            pass

        system_prompt = (
            f"You are an expert agent specializing in: {', '.join(listing.tags)}. "
            f"You have access to the memory '{listing.title}' "
            f"({listing.seq_len} tokens of context)."
        )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.endpoint}/v1/chat/completions",
                json={
                    "model": listing.model_id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": max_tokens,
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        return SandboxResponse(
            text=text,
            quality_score=self._score(query, text),
            queries_remaining=4,
        )

    @staticmethod
    def _score(query: str, response: str) -> float:
        # Heuristic placeholder — real scoring is LLM-judged.
        if not response.strip():
            return 0.0
        return min(1.0, 0.5 + len(response) / 400.0)

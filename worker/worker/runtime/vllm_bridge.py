"""vLLM bridge — talk to local vLLM server for inference."""
from __future__ import annotations

import httpx

from ..server.config import settings


async def vllm_complete(
    prompt: str,
    kv_cache_id: str,
    max_tokens: int = 200,
    model: str | None = None,
) -> str:
    """
    Send a completion request to the local vLLM server.

    Args:
        prompt: User prompt
        kv_cache_id: LMCache cache identifier to use
        max_tokens: Max tokens to generate

    Returns:
        Generated text completion
    """
    model = model or settings.HF_MODEL_ID

    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "cache_id": kv_cache_id,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(settings.vllm_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0]["text"]

    if "text" in data:
        return data["text"][0]

    raise RuntimeError(f"Unexpected vLLM response format: {data}")
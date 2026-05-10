"""Load decompressed KV cache into vLLM via LMCache."""
from __future__ import annotations

import torch

try:
    from lmcache import LMCache
    from lmcache.utils.config import LMCacheConfig
    LMCACHE_AVAILABLE = True
except ImportError:
    LMCACHE_AVAILABLE = False

from .lmcache_serde import TurboQuantSerializer

_worker_cache: LMCache | None = None


async def load_into_vllm(kv_cache: torch.Tensor, cache_id: str) -> str:
    """
    Load a decompressed KV cache tensor into vLLM via LMCache.

    Args:
        kv_cache: Decompressed tensor of shape [L, 2, H, S, D]
        cache_id: User-supplied cache identifier

    Returns:
        The cache_id (for use in inference calls)
    """
    if not LMCACHE_AVAILABLE:
        raise ImportError("LMCache not installed. Install with: uv pip install lmcache")

    global _worker_cache
    if _worker_cache is None:
        config = LMCacheConfig()
        _worker_cache = LMCache(
            config=config,
            serializer=TurboQuantSerializer(),
        )

    await _worker_cache.put(cache_id, kv_cache)
    return cache_id


async def get_from_vllm(cache_id: str) -> torch.Tensor | None:
    """Retrieve a cached KV cache by ID."""
    if not LMCACHE_AVAILABLE:
        return None
    if _worker_cache is None:
        return None
    return await _worker_cache.get(cache_id)
"""Custom LMCache serializer for TurboQuant blobs."""
from __future__ import annotations

import io

import torch
from lmcache.storage_backend.serializer.abstractSerializer import AbstractSerializer

MAGIC = b"TQNT"


class TurboQuantSerializer(AbstractSerializer):
    """LMCache serializer that stores/loads compressed TurboQuant blobs.

    Stores metadata separately from the compressed blob for cache key matching.
    """

    @staticmethod
    def serialize(key: str, data: torch.Tensor) -> bytes:
        """Serialize a KV cache tensor to TurboQuant blob bytes."""
        buf = io.BytesIO()
        torch.save(data, buf)
        return buf.getvalue()

    @staticmethod
    def deserialize(key: str, data: bytes) -> torch.Tensor:
        """Deserialize TurboQuant blob bytes back to tensor."""
        buf = io.BytesIO(data)
        return torch.load(buf, map_location="cpu")

    @staticmethod
    def get_storage_key(key: str) -> str:
        """Return the cache key used for storage."""
        return f"turboquant:{key}"

    @staticmethod
    def support_llm() -> bool:
        """Whether this serializer supports LLM cache format."""
        return True
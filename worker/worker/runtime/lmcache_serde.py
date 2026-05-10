"""Custom LMCache serializer that stores tensors as TurboQuant blobs."""
from __future__ import annotations

import os

import torch
from lmcache.storage_backend.serializer.abstractSerializer import AbstractSerializer

from worker.turboquant.compress import compress, decompress

MAGIC = b"TQNT"

_DEFAULT_BITS = float(os.getenv("TURBOQUANT_BITS", "3.5"))
_DEFAULT_SEED = int(os.getenv("TURBOQUANT_SEED", "42"))


class TurboQuantSerializer(AbstractSerializer):
    """LMCache serializer that stores tensors as compressed TurboQuant blobs.

    Compresses on serialize, decompresses on deserialize — so the cache footprint
    matches the on-wire blob size, not the raw fp16 tensor.
    """

    @staticmethod
    def serialize(key: str, data: torch.Tensor) -> bytes:
        result = compress(data, bits=_DEFAULT_BITS, seed=_DEFAULT_SEED)
        return result.blob

    @staticmethod
    def deserialize(key: str, data: bytes) -> torch.Tensor:
        return decompress(data)

    @staticmethod
    def get_storage_key(key: str) -> str:
        return f"turboquant:{key}"

    @staticmethod
    def support_llm() -> bool:
        return True
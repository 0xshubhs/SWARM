"""
End-to-end TurboQuant compress and decompress.

Pipeline:
  compress: Hadamard rotate → Beta-optimal quantize → QJL residual → serialize
  decompress: deserialize → decode quantizer → QJL decode → inverse Hadamard
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import torch

from .hadamard import hadamard_inverse, hadamard_rotate, next_power_of_2
from .qjl import make_qjl_matrix, qjl_decode_to_residual, qjl_encode
from .quantizer import BetaQuantizer
from .serde import deserialize_blob, serialize_blob


class CompressResult(NamedTuple):
    blob: bytes
    metadata: dict


def compress(
    kv_cache: torch.Tensor,
    bits: float = 3.5,
    seed: int = 42,
    qjl_ratio: float = 0.125,
    norm_scale: float | None = None,
) -> CompressResult:
    """
    Compress a KV cache using TurboQuant.

    Args:
        kv_cache: tensor of shape [L, 2, H, S, D]
                  L = num_layers, H = num_heads, S = seq_len, D = head_dim
        bits: target bits per channel for quantizer
        seed: random seed for deterministic rotation/projection
        qjl_ratio: ratio of QJL projection dim to original dim (proj_dim = d * ratio)
        norm_scale: if provided, use this to normalize rotated values to [-1,1].
                    If None, normalizes by max abs value across all vectors.

    Returns:
        CompressResult with blob bytes and metadata dict
    """
    L, two, H, S, D = kv_cache.shape
    assert two == 2, "KV cache must have keys and values (dim 1 = 2)"

    target_d = next_power_of_2(D)
    proj_dim = max(8, int(target_d * qjl_ratio))

    N = L * two * H * S
    vectors = kv_cache.reshape(N, D).float()
    device = vectors.device

    rotated = hadamard_rotate(vectors, seed=seed)

    if norm_scale is None:
        norm_scale = rotated.abs().max().item()
    if norm_scale == 0:
        norm_scale = 1.0

    rotated_normalized = rotated / norm_scale

    quantizer = BetaQuantizer(head_dim=target_d, bits=bits)
    codes = quantizer.encode(rotated_normalized)

    decoded_normalized = quantizer.decode(codes)
    residual = rotated_normalized - decoded_normalized
    W = make_qjl_matrix(target_d, proj_dim, seed=seed).to(device)
    qjl_bits = qjl_encode(residual, W)

    metadata = {
        "shape": [L, two, H, S, D],
        "target_d": target_d,
        "bits": bits,
        "seed": seed,
        "proj_dim": proj_dim,
        "num_levels": quantizer.num_levels,
        "norm_scale": norm_scale,
    }

    blob = serialize_blob(
        codes=codes.cpu().numpy().astype(np.int8),
        qjl_bits=qjl_bits.cpu().numpy(),
        metadata=metadata,
    )

    return CompressResult(blob=blob, metadata=metadata)


def decompress(blob: bytes) -> torch.Tensor:
    """
    Decompress a TurboQuant blob back to KV cache tensor.

    Args:
        blob: bytes from compress()

    Returns:
        torch.Tensor of shape [L, 2, H, S, D]
    """
    codes_np, qjl_bits_np, metadata = deserialize_blob(blob)

    L, two, H, S, D = metadata["shape"]
    target_d = metadata["target_d"]
    proj_dim = metadata["proj_dim"]
    seed = metadata["seed"]
    bits = metadata["bits"]
    norm_scale = metadata.get("norm_scale", 1.0)

    codes = torch.tensor(codes_np, dtype=torch.int32)
    qjl_bits = torch.tensor(qjl_bits_np, dtype=torch.bool)

    quantizer = BetaQuantizer(head_dim=target_d, bits=bits)
    decoded_normalized = quantizer.decode(codes)

    W = make_qjl_matrix(target_d, proj_dim, seed=seed)
    residual_approx = qjl_decode_to_residual(qjl_bits, W)

    rotated_approx = decoded_normalized + residual_approx
    rotated_approx = rotated_approx * norm_scale
    vectors = hadamard_inverse(rotated_approx, seed=seed, original_d=D)

    return vectors.reshape(L, two, H, S, D)
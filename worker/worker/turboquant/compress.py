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
) -> CompressResult:
    """
    Compress a KV cache using TurboQuant.

    Args:
        kv_cache: tensor of shape [L, 2, H, S, D]
                  L = num_layers, H = num_heads, S = seq_len, D = head_dim
        bits: target bits per channel for quantizer
        seed: random seed for deterministic rotation/projection
        qjl_ratio: ratio of QJL projection dim to original dim (proj_dim = d * ratio)

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

    # Per-row L2 normalisation. After Hadamard rotation each row's coordinates
    # are approximately Beta(d/2, d/2) on the unit sphere — the precomputed
    # quantizer levels assume exactly that shape. A single global scale would
    # squash most rows into the inner few levels and destroy fidelity.
    row_norms = rotated.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    rotated_normalized = rotated / row_norms

    quantizer = BetaQuantizer(head_dim=target_d, bits=bits)
    codes = quantizer.encode(rotated_normalized)

    decoded_normalized = quantizer.decode(codes)
    residual = rotated_normalized - decoded_normalized
    W = make_qjl_matrix(target_d, proj_dim, seed=seed).to(device)
    qjl_bits = qjl_encode(residual, W)

    # Reconstruct what decode() would build from the bits, so we can record
    # a per-row scale that brings its magnitude back into the residual's
    # actual range. Without this, the sign-only residual lands at unit scale
    # and overwhelms the much smaller quantizer error during decompression.
    signs = qjl_bits.float() * 2 - 1
    qjl_basis = signs @ torch.linalg.pinv(W)
    basis_norms = qjl_basis.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    residual_norms = residual.norm(dim=-1, keepdim=True)
    qjl_scale = (residual_norms / basis_norms).squeeze(-1)

    metadata = {
        "shape": [L, two, H, S, D],
        "target_d": target_d,
        "bits": bits,
        "seed": seed,
        "proj_dim": proj_dim,
        "num_levels": quantizer.num_levels,
        "row_norms": row_norms.squeeze(-1).cpu().tolist(),
        "qjl_scale": qjl_scale.cpu().tolist(),
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

    codes = torch.tensor(codes_np, dtype=torch.int32)
    qjl_bits = torch.tensor(qjl_bits_np, dtype=torch.bool)

    quantizer = BetaQuantizer(head_dim=target_d, bits=bits)
    decoded_normalized = quantizer.decode(codes)

    W = make_qjl_matrix(target_d, proj_dim, seed=seed)
    residual_approx = qjl_decode_to_residual(qjl_bits, W)
    if "qjl_scale" in metadata:
        scale = torch.tensor(metadata["qjl_scale"], dtype=torch.float32).unsqueeze(-1)
        approx_norms = residual_approx.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        residual_approx = residual_approx / approx_norms * scale

    rotated_approx = decoded_normalized + residual_approx
    if "row_norms" in metadata:
        # New per-row scaling.
        row_norms = torch.tensor(metadata["row_norms"], dtype=torch.float32).unsqueeze(-1)
        rotated_approx = rotated_approx * row_norms
    elif "norm_scale" in metadata:
        # Legacy single-scalar blobs — keep readable.
        rotated_approx = rotated_approx * metadata["norm_scale"]
    vectors = hadamard_inverse(rotated_approx, seed=seed, original_d=D)

    return vectors.reshape(L, two, H, S, D)
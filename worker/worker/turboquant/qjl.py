"""
1-bit Quantized Johnson-Lindenstrauss projection.

The scalar quantizer captures coordinate-level information.
But for KV cache, attention computes inner products — and small
errors in coordinates can compound. The 1-bit QJL residual is
a low-overhead "second pass" that captures inner-product structure.

We project the residual through a Gaussian random matrix of
dimension d × proj_dim (where proj_dim = d/8), then store only
the sign bit of each projection coordinate.
"""
from __future__ import annotations

import numpy as np
import torch


def make_qjl_matrix(d: int, proj_dim: int, seed: int) -> torch.Tensor:
    """
    Gaussian random projection matrix W: R^d → R^proj_dim.

    Columns are i.i.d. Gaussian scaled to unit norm in expectation.
    Uses a different seed than Hadamard to ensure independence.
    """
    rng = np.random.default_rng(seed + 1)
    W = rng.standard_normal((d, proj_dim))
    W = W / np.sqrt(d)
    return torch.tensor(W, dtype=torch.float32)


def qjl_encode(residual: torch.Tensor, W: torch.Tensor) -> torch.Tensor:
    """
    Project residual and store sign bits.

    Args:
        residual: tensor of shape [..., d]
        W: projection matrix of shape [d, proj_dim]

    Returns:
        bool tensor of shape [..., proj_dim] — True = positive, False = negative
    """
    projected = residual @ W
    return projected > 0


def qjl_decode_to_residual(qjl_bits: torch.Tensor, W: torch.Tensor) -> torch.Tensor:
    """
    Approximate the residual from sign bits via least-squares.

    We reconstruct a {-1, +1} vector from the sign bits, then apply
    the pseudo-inverse of W to get an approximate residual in R^d.

    Args:
        qjl_bits: bool tensor of shape [..., proj_dim]
        W: projection matrix of shape [d, proj_dim]

    Returns:
        approximated residual of shape [..., d]
    """
    signs = qjl_bits.float() * 2 - 1
    W_pinv = torch.linalg.pinv(W)
    residual_approx = signs @ W_pinv
    return residual_approx
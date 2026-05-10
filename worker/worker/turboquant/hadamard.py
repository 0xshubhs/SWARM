"""
Fast Walsh-Hadamard Transform with random sign flips.

For a vector x of length d (must be power of 2):
  HxS x  where H is Hadamard matrix, S is diagonal random sign matrix

The transform makes the components of any input vector
approximately iid (Beta-distributed), bringing them
closer to a shape that's easy to quantize.
"""
from __future__ import annotations

import numpy as np
import torch


def next_power_of_2(n: int) -> int:
    """Return the smallest power of 2 >= n."""
    return 1 << (n - 1).bit_length()


def random_signs(d: int, seed: int) -> torch.Tensor:
    """
    Generate a deterministic ±1 vector for given dimension and seed.

    Using a fixed seed ensures the same rotation is applied on encode/decode.
    """
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=d)
    return torch.tensor(signs, dtype=torch.float32)


def fwht(x: torch.Tensor) -> torch.Tensor:
    """
    Fast Walsh-Hadamard Transform.

    Input x must have last dim a power of 2.
    Operates on the last dimension.
    Normalizes by sqrt(d) so that H is self-inverse (orthonormal).
    """
    *_batch, d = x.shape
    assert (d & (d - 1)) == 0, f"Dimension d={d} must be a power of 2"

    result = x.clone()
    stride = 1
    while stride < d:
        half = stride
        for i in range(0, d, stride * 2):
            for j in range(half):
                u = result[..., i + j].clone()
                v = result[..., i + j + half]
                result[..., i + j] = u + v
                result[..., i + j + half] = u - v
        stride *= 2

    return result / (d ** 0.5)


def hadamard_rotate(x: torch.Tensor, seed: int) -> torch.Tensor:
    """
    Apply randomized Hadamard rotation: H @ S @ x where S is random ±1 diagonal.

    Pads to next power of 2 if needed (truncated on inverse).

    Args:
        x: Input tensor of shape [..., d] where d <= 128 typically
        seed: Fixed seed for deterministic rotation (same seed on encode/decode)

    Returns:
        Rotated tensor of shape [..., target_d] where target_d is next power of 2
    """
    *batch, d = x.shape
    target_d = next_power_of_2(d)

    if target_d != d:
        padding = torch.zeros(*batch, target_d - d, device=x.device, dtype=x.dtype)
        x = torch.cat([x, padding], dim=-1)

    signs = random_signs(target_d, seed).to(x.device)
    x = x * signs
    x = fwht(x)
    return x


def hadamard_inverse(x: torch.Tensor, seed: int, original_d: int) -> torch.Tensor:
    """
    Inverse Hadamard rotation. Truncates back to original_d.

    Since H is self-inverse (orthonormal): H = H^-1 = H^T
    We apply: x_rec = S @ H @ x_rot

    Args:
        x: Rotated tensor of shape [..., target_d]
        seed: Same seed used in hadamard_rotate
        original_d: Original dimension before padding

    Returns:
        Reconstructed tensor of shape [..., original_d]
    """
    target_d = x.shape[-1]
    x = fwht(x)
    signs = random_signs(target_d, seed).to(x.device)
    x = x * signs
    return x[..., :original_d]
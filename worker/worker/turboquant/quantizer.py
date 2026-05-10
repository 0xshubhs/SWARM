"""
Per-coordinate scalar quantizer optimized for Beta-distributed inputs.

After Hadamard rotation of a unit-norm vector, each coordinate is
approximately Beta(d/2, d/2) distributed. The Lloyd-Max algorithm
gives optimal quantization levels for this distribution.

Levels are precomputed and cached in precomputed/beta_levels.json.
Run `python -m turboquant.quantizer` once to generate the cache.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from scipy.stats import beta as beta_dist

PRECOMPUTED_PATH = Path(__file__).parent / "precomputed" / "beta_levels.json"

BIT_RATES = [2.5, 3.0, 3.5, 4.0, 5.0, 6.0]
HEAD_DIMS = [64, 128]


def lloyd_max(
    num_levels: int,
    alpha: float = 64,
    beta_param: float = 64,
    num_iterations: int = 100,
    num_samples: int = 100_000,
) -> np.ndarray:
    """
    Lloyd-Max algorithm: iteratively find optimal quantizer levels
    for a Beta(alpha, beta) distribution.

    Samples from Beta, shifts to [-1, 1], then finds optimal
    scalar quantizer levels via Lloyd's algorithm.
    """
    samples = beta_dist.rvs(alpha, beta_param, size=num_samples) * 2 - 1
    samples = np.sort(samples)

    levels = np.linspace(samples.min(), samples.max(), num_levels)

    for _ in range(num_iterations):
        boundaries = (levels[:-1] + levels[1:]) / 2
        assignments = np.searchsorted(boundaries, samples)

        new_levels = np.array(
            [
                samples[assignments == i].mean() if (assignments == i).any() else levels[i]
                for i in range(num_levels)
            ]
        )

        if np.allclose(levels, new_levels, atol=1e-6):
            break
        levels = new_levels

    return levels


def precompute_all_levels() -> dict:
    """Precompute and save levels for all bit-rates × head_dims."""
    output = {}
    for d in HEAD_DIMS:
        output[str(d)] = {}
        for bits in BIT_RATES:
            num_levels = round(2 ** bits)
            levels = lloyd_max(num_levels, alpha=d / 2, beta_param=d / 2)
            output[str(d)][str(bits)] = levels.tolist()

    PRECOMPUTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PRECOMPUTED_PATH.open("w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"Saved precomputed levels to {PRECOMPUTED_PATH}")
    print(f"Head dims: {HEAD_DIMS}, Bit rates: {BIT_RATES}")
    return output


class BetaQuantizer:
    """Encode/decode using precomputed Beta-optimal Lloyd-Max levels."""

    def __init__(self, head_dim: int, bits: float):
        if not PRECOMPUTED_PATH.exists():
            raise FileNotFoundError(
                f"Precomputed levels not found at {PRECOMPUTED_PATH}. "
                "Run `python -m turboquant.quantizer` to generate them."
            )
        with PRECOMPUTED_PATH.open() as f:
            data = json.load(f)

        str_hd = str(head_dim)
        str_bits = str(bits)
        if str_hd not in data:
            raise ValueError(f"No precomputed levels for head_dim={head_dim}")
        if str_bits not in data[str_hd]:
            raise ValueError(f"No precomputed levels for bits={bits} at head_dim={head_dim}")

        self.levels = torch.tensor(data[str_hd][str_bits], dtype=torch.float32)
        self.num_levels = len(self.levels)
        self.bits = bits
        self.head_dim = head_dim

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """
        Map x to nearest level index using binary search.

        Uses torch.searchsorted on inter-level boundaries instead of
        materializing a full [..., d, num_levels] distance matrix.
        Returns int32 codes.

        Args:
            x: tensor of shape [..., d]

        Returns:
            int32 codes of shape [..., d] with values in [0, num_levels-1]
        """
        boundaries = (self.levels[:-1] + self.levels[1:]) / 2
        codes = torch.searchsorted(boundaries.to(x.device), x)
        codes = codes.clamp(0, self.num_levels - 1)
        return codes.to(torch.int32)

    def decode(self, codes: torch.Tensor) -> torch.Tensor:
        """
        Map indices back to level values.

        Args:
            codes: int32 tensor of shape [..., d] with values in [0, num_levels-1]

        Returns:
            float32 tensor of shape [..., d] with quantized values
        """
        return self.levels.to(codes.device)[codes]


if __name__ == "__main__":
    precompute_all_levels()
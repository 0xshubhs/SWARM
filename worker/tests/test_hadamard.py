"""Tests for turboquant/hadamard.py — Phase 1."""
from __future__ import annotations

import pytest
import torch

from worker.turboquant.hadamard import (
    fwht,
    hadamard_inverse,
    hadamard_rotate,
    next_power_of_2,
    random_signs,
)


class TestNextPowerOf2:
    def test_power_of_2_returns_same(self):
        for n in [1, 2, 4, 8, 16, 64, 128, 256, 1024]:
            assert next_power_of_2(n) == n

    def test_rounds_up_to_next_power(self):
        assert next_power_of_2(3) == 4
        assert next_power_of_2(5) == 8
        assert next_power_of_2(7) == 8
        assert next_power_of_2(9) == 16
        assert next_power_of_2(129) == 256

    def test_edge_cases(self):
        assert next_power_of_2(1) == 1
        assert next_power_of_2(2) == 2


class TestRandomSigns:
    def test_deterministic_same_seed(self):
        s1 = random_signs(128, seed=42)
        s2 = random_signs(128, seed=42)
        assert torch.equal(s1, s2)

    def test_deterministic_different_seeds(self):
        s1 = random_signs(128, seed=42)
        s2 = random_signs(128, seed=99)
        assert not torch.equal(s1, s2)

    def test_values_are_pm1(self):
        signs = random_signs(128, seed=42)
        assert torch.all((signs == 1.0) | (signs == -1.0))

    def test_length_correct(self):
        for d in [64, 128, 256]:
            signs = random_signs(d, seed=42)
            assert len(signs) == d


class TestFWHT:
    def test_self_inverse_orthonormal(self):
        """H @ H = I for orthonormal FWHT (normalized by 1/sqrt(d))."""
        d = 128
        torch.eye(d)
        x = torch.randn(d)
        # FWHT is its own inverse
        result = fwht(fwht(x))
        assert torch.allclose(x, result, atol=1e-5), "FWHT must be self-inverse"

    def test_round_trip_identity(self):
        """fwht(fwht(x)) == x for any power-of-2 length vector."""
        for d in [2, 4, 8, 16, 64, 128, 256]:
            x = torch.randn(d)
            assert torch.allclose(fwht(fwht(x)), x, atol=1e-5)

    def test_preserves_dtype(self):
        x = torch.randn(128, dtype=torch.float32)
        result = fwht(fwht(x))
        assert result.dtype == torch.float32

    def test_batch_processing(self):
        """FWHT should handle batch dimensions correctly."""
        x = torch.randn(3, 5, 128)
        result = fwht(fwht(x))
        assert torch.allclose(x, result, atol=1e-5)

    def test_non_power_of_2_raises(self):
        x = torch.randn(3, 100)  # 100 is not power of 2
        with pytest.raises(AssertionError, match="must be a power of 2"):
            fwht(x)


class TestHadamardRotate:
    def test_round_trip_lossless_float32(self):
        """hadamard_inverse(hadamard_rotate(x, seed), seed, len(x)) ≈ x"""
        x = torch.randn(128, dtype=torch.float32)
        seed = 42
        x_rot = hadamard_rotate(x, seed)
        x_rec = hadamard_inverse(x_rot, seed, len(x))
        assert torch.allclose(x, x_rec, atol=1e-4), \
            f"Max error: {(x - x_rec).abs().max().item()}"

    def test_round_trip_different_seeds(self):
        """Different seeds produce different rotations but still round-trip."""
        x = torch.randn(128, dtype=torch.float32)
        for seed in [1, 42, 99, 12345]:
            x_rot = hadamard_rotate(x, seed)
            x_rec = hadamard_inverse(x_rot, seed, len(x))
            assert torch.allclose(x, x_rec, atol=1e-4)

    def test_round_trip_different_dims(self):
        """Round-trip works for various original dimensions."""
        for d in [64, 100, 128, 200]:
            x = torch.randn(d, dtype=torch.float32)
            seed = 42
            x_rot = hadamard_rotate(x, seed)
            assert x_rot.shape[-1] == next_power_of_2(d)  # padded
            x_rec = hadamard_inverse(x_rot, seed, d)
            assert x_rec.shape[-1] == d  # truncated
            assert torch.allclose(x, x_rec, atol=1e-4)

    def test_padding_to_power_of_2(self):
        """Non-power-of-2 dims get padded to next power of 2."""
        d = 100
        x = torch.randn(d)
        target_d = next_power_of_2(d)
        x_rot = hadamard_rotate(x, seed=42)
        assert x_rot.shape[-1] == target_d

    def test_truncation_restores_original(self):
        """Only the first original_d elements are meaningful after inverse."""
        d = 80
        x = torch.randn(d)
        seed = 42
        x_rot = hadamard_rotate(x, seed)
        x_rec = hadamard_inverse(x_rot, seed, d)
        # Elements beyond d should be zero/meaningless in original
        assert x_rec.shape[-1] == d
        assert torch.allclose(x, x_rec, atol=1e-4)

    def test_batch_round_trip(self):
        """Batch tensors round-trip correctly."""
        x = torch.randn(10, 128)
        seed = 42
        x_rot = hadamard_rotate(x, seed)
        x_rec = hadamard_inverse(x_rot, seed, 128)
        assert torch.allclose(x, x_rec, atol=1e-4)

    def test_cuda_if_available(self):
        """Hadamard operations work on CUDA if available."""
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")
        x = torch.randn(128, device="cuda")
        seed = 42
        x_rot = hadamard_rotate(x, seed)
        x_rec = hadamard_inverse(x_rot, seed, 128)
        assert torch.allclose(x, x_rec, atol=1e-4)
        assert x_rot.device.type == "cuda"
        assert x_rec.device.type == "cuda"

    def test_deterministic(self):
        """Same input + same seed = same output every time."""
        x = torch.randn(128)
        seed = 42
        out1 = hadamard_rotate(x, seed)
        out2 = hadamard_rotate(x, seed)
        assert torch.equal(out1, out2)

    def test_different_signs_different_result(self):
        """Different seeds produce different rotations."""
        x = torch.randn(128)
        out1 = hadamard_rotate(x, seed=1)
        out2 = hadamard_rotate(x, seed=2)
        assert not torch.equal(out1, out2)

    def test_orthogonality_preserved(self):
        """Hadamard rotation preserves vector norms (orthonormal transform)."""
        x = torch.randn(128)
        x_rot = hadamard_rotate(x, seed=42)
        orig_norm = torch.norm(x).item()
        rot_norm = torch.norm(x_rot).item()
        assert abs(orig_norm - rot_norm) < 1e-4, \
            "Orthonormal transform should preserve L2 norm"

    def test_kv_cache_shape(self):
        """Works with KV cache shape [L, 2, H, S, D]."""
        # Simulate Qwen 2.5 7B GQA KV cache: [28, 2, 4, 512, 128]
        L, two, H, S, D = 28, 2, 4, 512, 128
        kv = torch.randn(L, two, H, S, D)
        seed = 42

        # Rotate each vector (flattened per-head-per-token)
        # After flatten: [L*two*H*S, D] = [28672, 128]
        L_flat, two, H, S, D = kv.shape
        kv_flat = kv.reshape(-1, D)  # [N, D]
        kv_rot = hadamard_rotate(kv_flat, seed)
        kv_rec = hadamard_inverse(kv_rot, seed, D)

        assert kv_rot.shape == (L_flat * two * H * S, next_power_of_2(D))
        assert kv_rec.shape == kv_flat.shape
        assert torch.allclose(kv_flat, kv_rec, atol=1e-4)
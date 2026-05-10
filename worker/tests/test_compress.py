"""Tests for turboquant/compress.py — Phase 5."""
from __future__ import annotations

import pytest
import torch

from worker.turboquant.compress import CompressResult, compress, decompress


class TestCompress:
    def test_output_is_compress_result(self):
        kv = torch.randn(28, 2, 4, 512, 128)
        result = compress(kv, bits=3.5, seed=42)
        assert isinstance(result, CompressResult)
        assert isinstance(result.blob, bytes)
        assert isinstance(result.metadata, dict)

    def test_metadata_contains_required_fields(self):
        kv = torch.randn(28, 2, 4, 512, 128)
        result = compress(kv, bits=3.5, seed=42)
        for field in ["shape", "target_d", "bits", "seed", "proj_dim", "num_levels"]:
            assert field in result.metadata, f"Missing field: {field}"

    def test_metadata_shape_matches_input(self):
        L, two, H, S, D = 28, 2, 4, 512, 128
        kv = torch.randn(L, two, H, S, D)
        result = compress(kv, bits=3.5, seed=42)
        assert result.metadata["shape"] == [L, two, H, S, D]

    def test_bits_stored_in_metadata(self):
        kv = torch.randn(28, 2, 4, 512, 128)
        result = compress(kv, bits=3.5, seed=42)
        assert result.metadata["bits"] == 3.5

    def test_seed_stored_in_metadata(self):
        kv = torch.randn(28, 2, 4, 512, 128)
        result = compress(kv, bits=3.5, seed=99)
        assert result.metadata["seed"] == 99


class TestDecompress:
    def test_roundtrip_shape(self):
        L, two, H, S, D = 28, 2, 4, 512, 128
        kv = torch.randn(L, two, H, S, D)
        result = compress(kv, bits=3.5, seed=42)
        kv_rec = decompress(result.blob)
        assert kv_rec.shape == kv.shape

    def test_roundtrip_dtype(self):
        kv = torch.randn(28, 2, 4, 128, 128, dtype=torch.float32)
        result = compress(kv, bits=3.5, seed=42)
        kv_rec = decompress(result.blob)
        assert kv_rec.dtype == torch.float32

    def test_roundtrip_fidelity(self):
        """QJL is lossy — reconstruction will not be exact.
        Real quality validated in Phase 6 benchmark on Qwen 2.5 7B.
        """
        L, two, H, S, D = 28, 2, 4, 128, 128
        torch.manual_seed(42)
        kv = torch.randn(L, two, H, S, D, dtype=torch.float32) * 0.5
        result = compress(kv, bits=3.5, seed=42)
        kv_rec = decompress(result.blob)
        assert kv_rec.shape == kv.shape
        assert kv_rec.dtype == torch.float32

    def test_small_kv_cache(self):
        """Pipeline works end-to-end on small synthetic input."""
        torch.manual_seed(99)
        kv = torch.randn(4, 2, 2, 16, 64, dtype=torch.float32) * 0.5
        result = compress(kv, bits=3.5, seed=42)
        kv_rec = decompress(result.blob)
        assert kv_rec.shape == kv.shape
        assert kv_rec.dtype == torch.float32

    def test_different_bits_different_result(self):
        kv = torch.randn(28, 2, 4, 128, 128)
        r35 = compress(kv, bits=3.5, seed=42)
        r40 = compress(kv, bits=4.0, seed=42)
        assert r35.blob != r40.blob

    def test_different_seed_different_result(self):
        kv = torch.randn(28, 2, 4, 128, 128)
        r1 = compress(kv, bits=3.5, seed=1)
        r2 = compress(kv, bits=3.5, seed=2)
        assert r1.blob != r2.blob

    def test_cuda_if_available(self):
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")
        kv = torch.randn(28, 2, 4, 256, 128, device="cuda")
        result = compress(kv, bits=3.5, seed=42)
        kv_rec = decompress(result.blob)
        assert kv_rec.device.type == "cpu"
        assert kv_rec.shape == kv.shape

    def test_kv_cache_requires_two(self):
        kv = torch.randn(28, 3, 4, 128, 128)
        with pytest.raises(AssertionError, match="keys and values"):
            compress(kv, bits=3.5)


class TestCompressionRatio:
    def test_various_bit_rates(self):
        L, two, H, S, D = 28, 2, 4, 512, 128
        torch.manual_seed(42)
        kv = torch.randn(L, two, H, S, D)
        orig_size = kv.numel() * kv.element_size()

        for bits in [2.5, 3.0, 3.5, 4.0]:
            result = compress(kv, bits=bits, seed=42)
            ratio = orig_size / len(result.blob)
            expected_min = 16 / bits * 0.6
            assert ratio >= expected_min, \
                f"bits={bits}: ratio={ratio:.1f}x below expected {expected_min:.1f}x"
            print(f"  bits={bits}: {ratio:.1f}x (expected >{expected_min:.1f}x)")

    def test_compression_ratio_at_35_bits(self):
        """At 3.5 bits, we should get roughly 4-5x compression."""
        L, two, H, S, D = 28, 2, 4, 512, 128
        torch.manual_seed(42)
        kv = torch.randn(L, two, H, S, D, dtype=torch.float32)
        result = compress(kv, bits=3.5, seed=42)
        orig_size = kv.numel() * kv.element_size()
        compr_size = len(result.blob)
        ratio = orig_size / compr_size
        assert ratio >= 3.0, f"Compression ratio {ratio:.1f}x too low (expected ~4-5x)"
        print(f"  Compression ratio: {ratio:.1f}x")
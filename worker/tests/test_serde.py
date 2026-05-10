"""Tests for turboquant/serde.py — Phase 4."""
from __future__ import annotations

import numpy as np
import pytest

from worker.turboquant.serde import (
    MAGIC,
    deserialize_blob,
    serialize_blob,
)


class TestSerializeBlob:
    def test_magic_present(self):
        codes = np.zeros((100, 128), dtype=np.int8)
        qjl = np.zeros((100, 16), dtype=np.bool_)
        blob = serialize_blob(codes, qjl, {"shape": [1, 2, 4, 100, 128]})
        assert blob[:4] == MAGIC

    def test_version_present(self):
        codes = np.zeros((10, 128), dtype=np.int8)
        qjl = np.zeros((10, 16), dtype=np.bool_)
        blob = serialize_blob(codes, qjl, {})
        assert blob[4:8] == b"\x01\x00\x00\x00"

    def test_output_is_bytes(self):
        codes = np.zeros((10, 128), dtype=np.int8)
        qjl = np.zeros((10, 16), dtype=np.bool_)
        blob = serialize_blob(codes, qjl, {})
        assert isinstance(blob, bytes)

    def test_deterministic(self):
        codes = np.random.randint(-100, 100, (10, 128), dtype=np.int8)
        qjl = np.random.choice([True, False], (10, 16))
        metadata = {"shape": [1, 2, 4, 10, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob1 = serialize_blob(codes, qjl, metadata)
        blob2 = serialize_blob(codes, qjl, metadata)
        assert blob1 == blob2


class TestDeserializeBlob:
    def test_roundtrip_codes(self):
        codes = np.random.randint(-128, 127, (800, 128), dtype=np.int8)
        qjl = np.random.choice([True, False], (800, 16))
        metadata = {"shape": [1, 2, 4, 100, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        codes2, _qjl2, _meta2 = deserialize_blob(blob)
        assert np.array_equal(codes, codes2)

    def test_roundtrip_qjl(self):
        codes = np.random.randint(-128, 127, (800, 128), dtype=np.int8)
        qjl = np.random.choice([True, False], (800, 16))
        metadata = {"shape": [1, 2, 4, 100, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        _codes2, qjl2, _meta2 = deserialize_blob(blob)
        assert np.array_equal(qjl, qjl2)

    def test_roundtrip_metadata(self):
        codes = np.zeros((800, 128), dtype=np.int8)
        qjl = np.zeros((800, 16), dtype=np.bool_)
        metadata = {"shape": [1, 2, 4, 100, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        _codes2, _qjl2, meta2 = deserialize_blob(blob)
        assert meta2["bits"] == 3.5
        assert meta2["seed"] == 42
        assert meta2["proj_dim"] == 16

    def test_checksum_tamper_detection(self):
        codes = np.random.randint(-128, 127, (100, 128), dtype=np.int8)
        qjl = np.random.choice([True, False], (100, 16))
        metadata = {"shape": [1, 2, 4, 100, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        tampered = bytearray(blob)
        tampered[-1] ^= 0xFF
        with pytest.raises(ValueError, match="checksum"):
            deserialize_blob(bytes(tampered))

    def test_checksum_truncated_detection(self):
        codes = np.zeros((100, 128), dtype=np.int8)
        qjl = np.zeros((100, 16), dtype=np.bool_)
        metadata = {"shape": [1, 2, 4, 100, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        with pytest.raises(ValueError):
            deserialize_blob(blob[:-10])

    def test_invalid_magic(self):
        blob = b"XXXX" + b"\x00" * 100
        with pytest.raises((ValueError, Exception)):
            deserialize_blob(blob)

    def test_wrong_version(self):
        codes = np.zeros((10, 128), dtype=np.int8)
        qjl = np.zeros((10, 16), dtype=np.bool_)
        metadata = {"shape": [1, 2, 4, 10, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        tampered = bytearray(blob)
        tampered[4] = 0xFF
        with pytest.raises((ValueError, Exception)):
            deserialize_blob(bytes(tampered))

    def test_codes_dtype_int8(self):
        codes = np.random.randint(-128, 127, (800, 128), dtype=np.int8)
        qjl = np.random.choice([True, False], (800, 16))
        metadata = {"shape": [1, 2, 4, 100, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        codes2, _, _ = deserialize_blob(blob)
        assert codes2.dtype == np.int8

    def test_all_zeros_codes(self):
        codes = np.zeros((16000, 128), dtype=np.int8)
        qjl = np.zeros((16000, 16), dtype=np.bool_)
        metadata = {"shape": [2, 2, 4, 1000, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        codes2, qjl2, _meta2 = deserialize_blob(blob)
        assert np.array_equal(codes, codes2)
        assert np.array_equal(qjl, qjl2)

    def test_full_byte_range_codes(self):
        codes = np.arange(-128, 127, dtype=np.int8)[:128].reshape(1, 128)
        qjl = np.zeros((1, 16), dtype=np.bool_)
        metadata = {"shape": [1, 1, 1, 1, 128], "bits": 3.5, "seed": 42, "proj_dim": 16}
        blob = serialize_blob(codes, qjl, metadata)
        codes2, _, _ = deserialize_blob(blob)
        assert np.array_equal(codes, codes2)
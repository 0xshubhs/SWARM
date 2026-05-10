"""
Binary blob format for TurboQuant compressed data.

Format:
  [magic 4B "TQNT"]
  [version 4B u32 little-endian]
  [metadata_len 4B u32 little-endian]
  [metadata JSON bytes]
  [codes_len 8B u64 little-endian]
  [codes bytes (np.int8)]
  [qjl_len 8B u64 little-endian]
  [qjl packed bits (np.uint8)]
  [sha256 32B]

Total header overhead: 4 + 4 + 4 + metadata_len + 8 + codes_len + 8 + qjl_len + 32
"""
from __future__ import annotations

import hashlib
import json
import struct

import numpy as np

MAGIC = b"TQNT"
VERSION = 1


def serialize_blob(codes: np.ndarray, qjl_bits: np.ndarray, metadata: dict) -> bytes:
    """
    Serialize compressed TurboQuant data to binary blob.

    Args:
        codes: int8 numpy array of shape [N, target_d] (quantizer codes)
        qjl_bits: bool numpy array of shape [N, proj_dim] (QJL sign bits)
        metadata: dict with shape, bits, seed, proj_dim, target_d, num_levels

    Returns:
        bytes blob suitable for storage/transmission
    """
    assert codes.dtype == np.int8, f"codes must be int8, got {codes.dtype}"
    assert qjl_bits.dtype == np.bool_, f"qjl_bits must be bool, got {qjl_bits.dtype}"

    metadata_json = json.dumps(metadata, separators=(",", ":")).encode()

    qjl_packed = np.packbits(qjl_bits.flatten(), axis=0)
    codes_bytes = codes.tobytes()
    qjl_bytes = qjl_packed.tobytes()

    body = b"".join(
        [
            MAGIC,
            struct.pack("<I", VERSION),
            struct.pack("<I", len(metadata_json)),
            metadata_json,
            struct.pack("<Q", len(codes_bytes)),
            codes_bytes,
            struct.pack("<Q", len(qjl_bytes)),
            qjl_bytes,
        ]
    )

    checksum = hashlib.sha256(body).digest()
    return body + checksum


def deserialize_blob(blob: bytes) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Deserialize TurboQuant binary blob.

    Args:
        blob: bytes blob from serialize_blob

    Returns:
        (codes, qjl_bits, metadata) tuple

    Raises:
        ValueError: if checksum fails or format is invalid
    """
    if len(blob) < 32:
        raise ValueError("Blob too short to contain header")

    body = blob[:-32]
    expected_checksum = blob[-32:]
    actual_checksum = hashlib.sha256(body).digest()
    if expected_checksum != actual_checksum:
        raise ValueError("Blob checksum mismatch — corrupted data")

    pos = 0

    magic = body[pos : pos + 4]
    if magic != MAGIC:
        raise ValueError(f"Invalid magic: {magic!r}")
    pos += 4

    version = struct.unpack("<I", body[pos : pos + 4])[0]
    if version != VERSION:
        raise ValueError(f"Unsupported version {version}")
    pos += 4

    metadata_len = struct.unpack("<I", body[pos : pos + 4])[0]
    pos += 4
    metadata = json.loads(body[pos : pos + metadata_len])
    pos += metadata_len

    codes_len = struct.unpack("<Q", body[pos : pos + 8])[0]
    pos += 8
    codes_bytes = body[pos : pos + codes_len]
    pos += codes_len

    qjl_len = struct.unpack("<Q", body[pos : pos + 8])[0]
    pos += 8
    qjl_bytes = body[pos : pos + qjl_len]

    L, two, H, S, D = metadata["shape"]
    target_d = metadata.get("target_d", D)
    N = L * two * H * S
    N = L * two * H * S
    codes = np.frombuffer(codes_bytes, dtype=np.int8).reshape(N, target_d)

    proj_dim = metadata["proj_dim"]
    qjl_packed = np.frombuffer(qjl_bytes, dtype=np.uint8)
    qjl_bits = np.unpackbits(qjl_packed)[: N * proj_dim].reshape(N, proj_dim).astype(bool)

    return codes, qjl_bits, metadata
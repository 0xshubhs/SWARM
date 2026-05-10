"""Minimal Borsh field-by-field decoder for Anchor events / accounts.

We avoid pulling in `anchorpy` so the indexer stays light. The encoders below
mirror Anchor 0.30.x behaviour: little-endian fixed-width ints, length-prefixed
strings (u32 LE) and Vec<T> (u32 LE count).
"""
from __future__ import annotations

from dataclasses import dataclass


class BorshError(ValueError):
    pass


@dataclass(slots=True)
class Reader:
    buf: bytes
    pos: int = 0

    def _take(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise BorshError(f"unexpected EOF at {self.pos} need {n}")
        out = self.buf[self.pos : self.pos + n]
        self.pos += n
        return out

    def u8(self) -> int:
        return self._take(1)[0]

    def u16(self) -> int:
        return int.from_bytes(self._take(2), "little")

    def u32(self) -> int:
        return int.from_bytes(self._take(4), "little")

    def u64(self) -> int:
        return int.from_bytes(self._take(8), "little")

    def i64(self) -> int:
        return int.from_bytes(self._take(8), "little", signed=True)

    def bool(self) -> bool:
        return self._take(1)[0] != 0

    def fixed(self, n: int) -> bytes:
        return self._take(n)

    def pubkey(self) -> bytes:
        return self._take(32)

    def string(self) -> str:
        n = self.u32()
        return self._take(n).decode("utf-8")

    def vec_u8(self) -> bytes:
        n = self.u32()
        return self._take(n)

    def vec_string(self) -> list[str]:
        n = self.u32()
        return [self.string() for _ in range(n)]

    def remaining(self) -> int:
        return len(self.buf) - self.pos

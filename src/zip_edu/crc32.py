"""CRC32 implementation (IEEE 802.3 polynomial)."""

from __future__ import annotations

_POLY = 0xEDB88320


def _make_table() -> list[int]:
    table: list[int] = []
    for i in range(256):
        c = i
        for _ in range(8):
            if c & 1:
                c = (c >> 1) ^ _POLY
            else:
                c >>= 1
        table.append(c & 0xFFFFFFFF)
    return table


_CRC32_TABLE = _make_table()


def crc32(data: bytes, seed: int = 0) -> int:
    c = seed ^ 0xFFFFFFFF
    for b in data:
        c = _CRC32_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


"""Bit-level IO utilities for DEFLATE streams.

DEFLATE uses least-significant-bit-first bit ordering.
"""

from __future__ import annotations


class BitReader:
    """Read bits in little-endian bit order from bytes."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos = 0
        self._bit_buf = 0
        self._bit_count = 0

    def read_bits(self, count: int) -> int:
        if count < 0:
            raise ValueError("count must be >= 0")
        while self._bit_count < count:
            if self._byte_pos >= len(self._data):
                raise EOFError("unexpected end of bit stream")
            self._bit_buf |= self._data[self._byte_pos] << self._bit_count
            self._bit_count += 8
            self._byte_pos += 1
        mask = (1 << count) - 1
        value = self._bit_buf & mask
        self._bit_buf >>= count
        self._bit_count -= count
        return value

    def read_bit(self) -> int:
        return self.read_bits(1)

    def align_byte(self) -> None:
        self._bit_buf = 0
        self._bit_count = 0

    def read_bytes(self, count: int) -> bytes:
        if count < 0:
            raise ValueError("count must be >= 0")
        self.align_byte()
        end = self._byte_pos + count
        if end > len(self._data):
            raise EOFError("unexpected end of byte stream")
        chunk = self._data[self._byte_pos:end]
        self._byte_pos = end
        return chunk


class BitWriter:
    """Write bits in little-endian bit order to bytes."""

    def __init__(self) -> None:
        self._out = bytearray()
        self._bit_buf = 0
        self._bit_count = 0

    def write_bits(self, value: int, count: int) -> None:
        if count < 0:
            raise ValueError("count must be >= 0")
        self._bit_buf |= (value & ((1 << count) - 1)) << self._bit_count
        self._bit_count += count
        while self._bit_count >= 8:
            self._out.append(self._bit_buf & 0xFF)
            self._bit_buf >>= 8
            self._bit_count -= 8

    def align_byte(self) -> None:
        if self._bit_count > 0:
            self._out.append(self._bit_buf & 0xFF)
            self._bit_buf = 0
            self._bit_count = 0

    def write_bytes(self, data: bytes) -> None:
        self.align_byte()
        self._out.extend(data)

    def to_bytes(self) -> bytes:
        if self._bit_count > 0:
            self._out.append(self._bit_buf & 0xFF)
            self._bit_buf = 0
            self._bit_count = 0
        return bytes(self._out)

"""Canonical Huffman coding for DEFLATE."""

from __future__ import annotations

from dataclasses import dataclass

from .bitstream import BitReader, BitWriter


def build_canonical_codes(lengths: list[int]) -> dict[int, tuple[int, int]]:
    """Return symbol -> (code, bit_length) for canonical Huffman lengths."""
    max_bits = max(lengths, default=0)
    if max_bits == 0:
        return {}

    bl_count = [0] * (max_bits + 1)
    for length in lengths:
        if length < 0:
            raise ValueError("negative code length")
        if length > 0:
            bl_count[length] += 1

    next_code = [0] * (max_bits + 1)
    code = 0
    for bits in range(1, max_bits + 1):
        code = (code + bl_count[bits - 1]) << 1
        next_code[bits] = code

    out: dict[int, tuple[int, int]] = {}
    for symbol, length in enumerate(lengths):
        if length == 0:
            continue
        out[symbol] = (next_code[length], length)
        next_code[length] += 1
    return out


@dataclass(slots=True)
class HuffmanDecoder:
    """Bit-by-bit canonical Huffman decoder."""

    tables: dict[int, dict[int, int]]
    max_bits: int

    @classmethod
    def from_code_lengths(cls, lengths: list[int]) -> "HuffmanDecoder":
        codes = build_canonical_codes(lengths)
        tables: dict[int, dict[int, int]] = {}
        max_bits = 0
        for symbol, (code, bit_length) in codes.items():
            tables.setdefault(bit_length, {})[code] = symbol
            if bit_length > max_bits:
                max_bits = bit_length
        if max_bits == 0:
            raise ValueError("empty Huffman code set")
        return cls(tables=tables, max_bits=max_bits)

    def decode_symbol(self, reader: BitReader) -> int:
        code = 0
        for bit_length in range(1, self.max_bits + 1):
            code |= reader.read_bit() << (bit_length - 1)
            table = self.tables.get(bit_length)
            if table is not None and code in table:
                return table[code]
        raise ValueError("invalid Huffman code")


def write_symbol(writer: BitWriter, codebook: dict[int, tuple[int, int]], symbol: int) -> None:
    code, bit_length = codebook[symbol]
    writer.write_bits(code, bit_length)


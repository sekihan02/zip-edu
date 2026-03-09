"""Canonical Huffman coding for DEFLATE."""

from __future__ import annotations

from dataclasses import dataclass
import heapq

from .bitstream import BitReader, BitWriter


def reverse_bits(value: int, bit_length: int) -> int:
    out = 0
    for _ in range(bit_length):
        out = (out << 1) | (value & 1)
        value >>= 1
    return out


def build_canonical_codes(lengths: list[int], *, reverse_for_deflate: bool = True) -> dict[int, tuple[int, int]]:
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
        code = next_code[length]
        if reverse_for_deflate:
            code = reverse_bits(code, length)
        out[symbol] = (code, length)
        next_code[length] += 1
    return out


def build_code_lengths_from_frequencies(freqs: list[int], max_bits: int) -> list[int] | None:
    """Build Huffman code lengths from frequencies.

    Returns None when a naive optimal tree exceeds max_bits.
    """
    if max_bits <= 0:
        raise ValueError("max_bits must be >= 1")
    n = len(freqs)
    if n == 0:
        return []

    active = [(f, s) for s, f in enumerate(freqs) if f > 0]
    if not active:
        return [0] * n
    if len(active) == 1:
        lengths = [0] * n
        lengths[active[0][1]] = 1
        return lengths

    # Node tuple: (symbol, left_idx, right_idx), symbol==-1 for internal nodes.
    nodes: list[tuple[int, int, int]] = []
    heap: list[tuple[int, int, int]] = []
    serial = 0
    for freq, symbol in active:
        idx = len(nodes)
        nodes.append((symbol, -1, -1))
        heapq.heappush(heap, (freq, serial, idx))
        serial += 1

    while len(heap) > 1:
        f1, _s1, i1 = heapq.heappop(heap)
        f2, _s2, i2 = heapq.heappop(heap)
        idx = len(nodes)
        nodes.append((-1, i1, i2))
        heapq.heappush(heap, (f1 + f2, serial, idx))
        serial += 1

    root_idx = heap[0][2]
    lengths = [0] * n
    stack: list[tuple[int, int]] = [(root_idx, 0)]
    while stack:
        node_idx, depth = stack.pop()
        symbol, left, right = nodes[node_idx]
        if symbol >= 0:
            lengths[symbol] = max(1, depth)
            continue
        stack.append((left, depth + 1))
        stack.append((right, depth + 1))

    if max(lengths, default=0) > max_bits:
        return None
    return lengths


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

"""Minimal DEFLATE encoder/decoder for educational ZIP implementation."""

from __future__ import annotations

from .bitstream import BitReader, BitWriter
from .huffman import HuffmanDecoder, build_canonical_codes, write_symbol
from .lz77 import (
    DIST_BASE,
    DIST_EXTRA,
    LENGTH_BASE,
    LENGTH_EXTRA,
    LiteralToken,
    MatchToken,
    distance_to_symbol,
    length_to_symbol,
    lz77_encode,
)

_CODE_LENGTH_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]

_FIXED_LITERAL_LENGTHS = [0] * 288
for _i in range(0, 144):
    _FIXED_LITERAL_LENGTHS[_i] = 8
for _i in range(144, 256):
    _FIXED_LITERAL_LENGTHS[_i] = 9
for _i in range(256, 280):
    _FIXED_LITERAL_LENGTHS[_i] = 7
for _i in range(280, 288):
    _FIXED_LITERAL_LENGTHS[_i] = 8
_FIXED_DISTANCE_LENGTHS = [5] * 32

_FIXED_LITERAL_CODES = build_canonical_codes(_FIXED_LITERAL_LENGTHS)
_FIXED_DISTANCE_CODES = build_canonical_codes(_FIXED_DISTANCE_LENGTHS)
_FIXED_LITERAL_TREE = HuffmanDecoder.from_code_lengths(_FIXED_LITERAL_LENGTHS)
_FIXED_DISTANCE_TREE = HuffmanDecoder.from_code_lengths(_FIXED_DISTANCE_LENGTHS)


def compress_deflate_fixed(data: bytes) -> bytes:
    """Compress as a single final DEFLATE block with fixed Huffman coding."""
    writer = BitWriter()
    writer.write_bits(1, 1)  # BFINAL
    writer.write_bits(0b01, 2)  # BTYPE=fixed Huffman

    for token in lz77_encode(data):
        if isinstance(token, LiteralToken):
            write_symbol(writer, _FIXED_LITERAL_CODES, token.value)
            continue

        if not isinstance(token, MatchToken):
            raise ValueError("unknown LZ77 token")
        length_symbol, length_extra, length_extra_bits = length_to_symbol(token.length)
        write_symbol(writer, _FIXED_LITERAL_CODES, length_symbol)
        if length_extra_bits:
            writer.write_bits(length_extra, length_extra_bits)

        dist_symbol, dist_extra, dist_extra_bits = distance_to_symbol(token.distance)
        write_symbol(writer, _FIXED_DISTANCE_CODES, dist_symbol)
        if dist_extra_bits:
            writer.write_bits(dist_extra, dist_extra_bits)

    write_symbol(writer, _FIXED_LITERAL_CODES, 256)  # end of block
    return writer.to_bytes()


def decompress_deflate(data: bytes) -> bytes:
    """Decode raw DEFLATE bytes."""
    reader = BitReader(data)
    out = bytearray()
    while True:
        is_final = reader.read_bits(1)
        block_type = reader.read_bits(2)
        if block_type == 0:
            _decode_stored_block(reader, out)
        elif block_type == 1:
            _decode_compressed_block(reader, out, _FIXED_LITERAL_TREE, _FIXED_DISTANCE_TREE)
        elif block_type == 2:
            lit_tree, dist_tree = _decode_dynamic_trees(reader)
            _decode_compressed_block(reader, out, lit_tree, dist_tree)
        else:
            raise ValueError("invalid DEFLATE block type")

        if is_final:
            break
    return bytes(out)


def _decode_stored_block(reader: BitReader, out: bytearray) -> None:
    reader.align_byte()
    block_len = reader.read_bits(16)
    block_nlen = reader.read_bits(16)
    if block_nlen != (block_len ^ 0xFFFF):
        raise ValueError("invalid stored block length")
    out.extend(reader.read_bytes(block_len))


def _decode_dynamic_trees(reader: BitReader) -> tuple[HuffmanDecoder, HuffmanDecoder]:
    hlit = reader.read_bits(5) + 257
    hdist = reader.read_bits(5) + 1
    hclen = reader.read_bits(4) + 4

    code_length_lengths = [0] * 19
    for i in range(hclen):
        code_length_lengths[_CODE_LENGTH_ORDER[i]] = reader.read_bits(3)
    code_length_tree = HuffmanDecoder.from_code_lengths(code_length_lengths)

    lengths: list[int] = []
    total = hlit + hdist
    while len(lengths) < total:
        symbol = code_length_tree.decode_symbol(reader)
        if 0 <= symbol <= 15:
            lengths.append(symbol)
        elif symbol == 16:
            if not lengths:
                raise ValueError("repeat-length symbol without previous length")
            repeat = reader.read_bits(2) + 3
            lengths.extend([lengths[-1]] * repeat)
        elif symbol == 17:
            repeat = reader.read_bits(3) + 3
            lengths.extend([0] * repeat)
        elif symbol == 18:
            repeat = reader.read_bits(7) + 11
            lengths.extend([0] * repeat)
        else:
            raise ValueError("invalid code-length symbol")
        if len(lengths) > total:
            raise ValueError("dynamic tree overrun")

    literal_lengths = lengths[:hlit]
    distance_lengths = lengths[hlit:]

    if all(v == 0 for v in literal_lengths):
        raise ValueError("literal/length tree is empty")
    if all(v == 0 for v in distance_lengths):
        distance_lengths[0] = 1

    return (
        HuffmanDecoder.from_code_lengths(literal_lengths),
        HuffmanDecoder.from_code_lengths(distance_lengths),
    )


def _decode_compressed_block(
    reader: BitReader,
    out: bytearray,
    literal_tree: HuffmanDecoder,
    distance_tree: HuffmanDecoder,
) -> None:
    while True:
        symbol = literal_tree.decode_symbol(reader)
        if symbol < 256:
            out.append(symbol)
            continue
        if symbol == 256:
            return
        if symbol > 285:
            raise ValueError("invalid length symbol")

        length = _decode_length(symbol, reader)
        dist_symbol = distance_tree.decode_symbol(reader)
        if dist_symbol > 29:
            raise ValueError("invalid distance symbol")
        distance = _decode_distance(dist_symbol, reader)
        if distance > len(out):
            raise ValueError("distance exceeds output size")

        for _ in range(length):
            out.append(out[-distance])


def _decode_length(symbol: int, reader: BitReader) -> int:
    if symbol == 285:
        return 258
    if not (257 <= symbol <= 284):
        raise ValueError("invalid length symbol")
    idx = symbol - 257
    extra_bits = LENGTH_EXTRA[idx]
    extra = reader.read_bits(extra_bits) if extra_bits else 0
    return LENGTH_BASE[idx] + extra


def _decode_distance(symbol: int, reader: BitReader) -> int:
    if not (0 <= symbol <= 29):
        raise ValueError("invalid distance symbol")
    extra_bits = DIST_EXTRA[symbol]
    extra = reader.read_bits(extra_bits) if extra_bits else 0
    return DIST_BASE[symbol] + extra


"""Minimal DEFLATE encoder/decoder for educational ZIP implementation."""

from __future__ import annotations

from dataclasses import dataclass

from .bitstream import BitReader, BitWriter
from .huffman import (
    HuffmanDecoder,
    build_canonical_codes,
    build_code_lengths_from_frequencies,
    write_symbol,
)
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


@dataclass(slots=True)
class _CodeLengthToken:
    symbol: int
    extra: int = 0
    extra_bits: int = 0


def compress_deflate(data: bytes, mode: str = "auto") -> bytes:
    """Compress raw bytes as a single DEFLATE stream.

    mode:
      - auto: choose shortest among dynamic/fixed/stored
      - dynamic: BTYPE=10
      - fixed: BTYPE=01
      - stored: BTYPE=00
    """
    if mode == "auto":
        options = [
            compress_deflate_dynamic(data),
            compress_deflate_fixed(data),
            compress_deflate_stored(data),
        ]
        return min(options, key=len)
    if mode == "dynamic":
        return compress_deflate_dynamic(data)
    if mode == "fixed":
        return compress_deflate_fixed(data)
    if mode == "stored":
        return compress_deflate_stored(data)
    raise ValueError("mode must be one of: auto, dynamic, fixed, stored")


def compress_deflate_fixed(data: bytes) -> bytes:
    """Compress as a single final DEFLATE block with fixed Huffman coding."""
    tokens = lz77_encode(data)
    writer = BitWriter()
    writer.write_bits(1, 1)  # BFINAL
    writer.write_bits(0b01, 2)  # BTYPE=fixed Huffman

    _encode_lz77_tokens(writer, tokens, _FIXED_LITERAL_CODES, _FIXED_DISTANCE_CODES)
    write_symbol(writer, _FIXED_LITERAL_CODES, 256)  # end of block
    return writer.to_bytes()


def compress_deflate_dynamic(data: bytes) -> bytes:
    """Compress using a dynamic Huffman block (BTYPE=10).

    For rare cases where naive tree generation exceeds DEFLATE max bits,
    this falls back to fixed Huffman.
    """
    tokens = lz77_encode(data)
    literal_freq, distance_freq = _build_token_frequencies(tokens)
    literal_lengths = build_code_lengths_from_frequencies(literal_freq, max_bits=15)
    distance_lengths = build_code_lengths_from_frequencies(distance_freq, max_bits=15)
    if literal_lengths is None or distance_lengths is None:
        return compress_deflate_fixed(data)

    if all(v == 0 for v in literal_lengths):
        return compress_deflate_fixed(data)
    if all(v == 0 for v in distance_lengths):
        distance_lengths[0] = 1

    literal_lengths = _trim_lengths(literal_lengths, minimum=257)
    distance_lengths = _trim_lengths(distance_lengths, minimum=1)

    code_len_tokens = _encode_code_length_stream(literal_lengths + distance_lengths)
    code_len_freq = [0] * 19
    for token in code_len_tokens:
        code_len_freq[token.symbol] += 1
    code_len_lengths = build_code_lengths_from_frequencies(code_len_freq, max_bits=7)
    if code_len_lengths is None or all(v == 0 for v in code_len_lengths):
        return compress_deflate_fixed(data)

    ordered_code_len_lengths = [code_len_lengths[i] for i in _CODE_LENGTH_ORDER]
    hclen = max(4, _last_nonzero(ordered_code_len_lengths) + 1)

    literal_codes = build_canonical_codes(literal_lengths)
    distance_codes = build_canonical_codes(distance_lengths)
    code_len_codes = build_canonical_codes(code_len_lengths)

    writer = BitWriter()
    writer.write_bits(1, 1)  # BFINAL
    writer.write_bits(0b10, 2)  # BTYPE=dynamic Huffman
    writer.write_bits(len(literal_lengths) - 257, 5)  # HLIT
    writer.write_bits(len(distance_lengths) - 1, 5)  # HDIST
    writer.write_bits(hclen - 4, 4)  # HCLEN

    for i in range(hclen):
        writer.write_bits(ordered_code_len_lengths[i], 3)

    for token in code_len_tokens:
        write_symbol(writer, code_len_codes, token.symbol)
        if token.extra_bits:
            writer.write_bits(token.extra, token.extra_bits)

    _encode_lz77_tokens(writer, tokens, literal_codes, distance_codes)
    write_symbol(writer, literal_codes, 256)  # end of block
    return writer.to_bytes()


def compress_deflate_stored(data: bytes) -> bytes:
    """Compress into one or more uncompressed stored blocks (BTYPE=00)."""
    writer = BitWriter()
    if not data:
        writer.write_bits(1, 1)
        writer.write_bits(0b00, 2)
        writer.align_byte()
        writer.write_bits(0, 16)
        writer.write_bits(0xFFFF, 16)
        return writer.to_bytes()

    pos = 0
    while pos < len(data):
        chunk = data[pos : pos + 65535]
        pos += len(chunk)
        final = 1 if pos >= len(data) else 0
        writer.write_bits(final, 1)
        writer.write_bits(0b00, 2)
        writer.align_byte()
        writer.write_bits(len(chunk), 16)
        writer.write_bits(len(chunk) ^ 0xFFFF, 16)
        writer.write_bytes(chunk)
    return writer.to_bytes()


def _build_token_frequencies(tokens: list[LiteralToken | MatchToken]) -> tuple[list[int], list[int]]:
    literal_freq = [0] * 286
    distance_freq = [0] * 30

    for token in tokens:
        if isinstance(token, LiteralToken):
            literal_freq[token.value] += 1
            continue

        if not isinstance(token, MatchToken):
            raise ValueError("unknown LZ77 token")
        length_symbol, _, _ = length_to_symbol(token.length)
        dist_symbol, _, _ = distance_to_symbol(token.distance)
        literal_freq[length_symbol] += 1
        distance_freq[dist_symbol] += 1

    literal_freq[256] += 1  # end-of-block symbol
    if all(v == 0 for v in distance_freq):
        distance_freq[0] = 1
    return literal_freq, distance_freq


def _encode_lz77_tokens(
    writer: BitWriter,
    tokens: list[LiteralToken | MatchToken],
    literal_codes: dict[int, tuple[int, int]],
    distance_codes: dict[int, tuple[int, int]],
) -> None:
    for token in tokens:
        if isinstance(token, LiteralToken):
            write_symbol(writer, literal_codes, token.value)
            continue
        if not isinstance(token, MatchToken):
            raise ValueError("unknown LZ77 token")

        length_symbol, length_extra, length_extra_bits = length_to_symbol(token.length)
        write_symbol(writer, literal_codes, length_symbol)
        if length_extra_bits:
            writer.write_bits(length_extra, length_extra_bits)

        dist_symbol, dist_extra, dist_extra_bits = distance_to_symbol(token.distance)
        write_symbol(writer, distance_codes, dist_symbol)
        if dist_extra_bits:
            writer.write_bits(dist_extra, dist_extra_bits)


def _trim_lengths(lengths: list[int], minimum: int) -> list[int]:
    last = _last_nonzero(lengths)
    if last < 0:
        return lengths[:minimum]
    return lengths[: max(minimum, last + 1)]


def _last_nonzero(values: list[int]) -> int:
    for i in range(len(values) - 1, -1, -1):
        if values[i] != 0:
            return i
    return -1


def _encode_code_length_stream(lengths: list[int]) -> list[_CodeLengthToken]:
    out: list[_CodeLengthToken] = []
    i = 0
    while i < len(lengths):
        current = lengths[i]
        run = 1
        while i + run < len(lengths) and lengths[i + run] == current:
            run += 1
        run_left = run

        if current == 0:
            while run_left >= 11:
                use = min(run_left, 138)
                out.append(_CodeLengthToken(symbol=18, extra=use - 11, extra_bits=7))
                run_left -= use
            while run_left >= 3:
                use = min(run_left, 10)
                out.append(_CodeLengthToken(symbol=17, extra=use - 3, extra_bits=3))
                run_left -= use
            while run_left > 0:
                out.append(_CodeLengthToken(symbol=0))
                run_left -= 1
        else:
            out.append(_CodeLengthToken(symbol=current))
            run_left -= 1
            while run_left >= 3:
                use = min(run_left, 6)
                out.append(_CodeLengthToken(symbol=16, extra=use - 3, extra_bits=2))
                run_left -= use
            while run_left > 0:
                out.append(_CodeLengthToken(symbol=current))
                run_left -= 1
        i += run
    return out


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

"""Naive LZ77 encoder helpers for DEFLATE."""

from __future__ import annotations

from dataclasses import dataclass

MIN_MATCH = 3
MAX_MATCH = 258
WINDOW_SIZE = 32768

LENGTH_BASE = [
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    13,
    15,
    17,
    19,
    23,
    27,
    31,
    35,
    43,
    51,
    59,
    67,
    83,
    99,
    115,
    131,
    163,
    195,
    227,
    258,
]
LENGTH_EXTRA = [
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    1,
    1,
    1,
    1,
    2,
    2,
    2,
    2,
    3,
    3,
    3,
    3,
    4,
    4,
    4,
    4,
    5,
    5,
    5,
    5,
    0,
]

DIST_BASE = [
    1,
    2,
    3,
    4,
    5,
    7,
    9,
    13,
    17,
    25,
    33,
    49,
    65,
    97,
    129,
    193,
    257,
    385,
    513,
    769,
    1025,
    1537,
    2049,
    3073,
    4097,
    6145,
    8193,
    12289,
    16385,
    24577,
]
DIST_EXTRA = [
    0,
    0,
    0,
    0,
    1,
    1,
    2,
    2,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    7,
    7,
    8,
    8,
    9,
    9,
    10,
    10,
    11,
    11,
    12,
    12,
    13,
    13,
]


@dataclass(slots=True)
class LiteralToken:
    value: int


@dataclass(slots=True)
class MatchToken:
    length: int
    distance: int


Token = LiteralToken | MatchToken


def _find_longest_match(data: bytes, pos: int) -> tuple[int, int]:
    start = max(0, pos - WINDOW_SIZE)
    best_length = 0
    best_distance = 0
    end_limit = min(len(data), pos + MAX_MATCH)
    for candidate in range(pos - 1, start - 1, -1):
        length = 0
        while pos + length < end_limit and data[candidate + length] == data[pos + length]:
            length += 1
            if length == MAX_MATCH:
                break
        if length > best_length and length >= MIN_MATCH:
            best_length = length
            best_distance = pos - candidate
            if best_length == MAX_MATCH:
                break
    return best_length, best_distance


def lz77_encode(data: bytes) -> list[Token]:
    out: list[Token] = []
    pos = 0
    while pos < len(data):
        length, distance = _find_longest_match(data, pos)
        if length >= MIN_MATCH:
            out.append(MatchToken(length=length, distance=distance))
            pos += length
        else:
            out.append(LiteralToken(value=data[pos]))
            pos += 1
    return out


def length_to_symbol(length: int) -> tuple[int, int, int]:
    if not (3 <= length <= 258):
        raise ValueError("invalid match length")
    if length == 258:
        return 285, 0, 0
    for i in range(28):
        base = LENGTH_BASE[i]
        extra_bits = LENGTH_EXTRA[i]
        max_value = base + (1 << extra_bits) - 1
        if base <= length <= max_value:
            return 257 + i, length - base, extra_bits
    raise ValueError("length symbol conversion failed")


def symbol_to_length(symbol: int, extra_value: int) -> int:
    if symbol == 285:
        return 258
    if not (257 <= symbol <= 284):
        raise ValueError("invalid length symbol")
    idx = symbol - 257
    return LENGTH_BASE[idx] + extra_value


def distance_to_symbol(distance: int) -> tuple[int, int, int]:
    if not (1 <= distance <= WINDOW_SIZE):
        raise ValueError("invalid distance")
    for symbol, base in enumerate(DIST_BASE):
        extra_bits = DIST_EXTRA[symbol]
        max_value = base + (1 << extra_bits) - 1
        if base <= distance <= max_value:
            return symbol, distance - base, extra_bits
    raise ValueError("distance symbol conversion failed")


def symbol_to_distance(symbol: int, extra_value: int) -> int:
    if not (0 <= symbol < len(DIST_BASE)):
        raise ValueError("invalid distance symbol")
    return DIST_BASE[symbol] + extra_value


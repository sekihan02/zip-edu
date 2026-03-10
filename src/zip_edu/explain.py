"""Helpers to inspect intermediate ZIP/DEFLATE steps."""

from __future__ import annotations

from collections import Counter
import struct

from .deflate import compress_deflate_dynamic, compress_deflate_fixed, compress_deflate_stored
from .lz77 import LiteralToken, MatchToken, distance_to_symbol, length_to_symbol, lz77_encode
from .zip_format import LFH_SIG, find_eocd_offset, parse_central_directory


def explain_lz77(data: bytes, limit: int = 120) -> list[str]:
    lines: list[str] = []
    tokens = lz77_encode(data)
    for i, token in enumerate(tokens[:limit]):
        if isinstance(token, LiteralToken):
            b = token.value
            if 32 <= b <= 126:
                lines.append(f"{i:04d}: LIT 0x{b:02X} ('{chr(b)}')")
            else:
                lines.append(f"{i:04d}: LIT 0x{b:02X}")
        elif isinstance(token, MatchToken):
            lines.append(f"{i:04d}: MAT len={token.length} dist={token.distance}")
    if len(tokens) > limit:
        lines.append(f"... ({len(tokens) - limit} tokens omitted)")
    lines.append(f"total_tokens={len(tokens)}")
    return lines


def explain_deflate(data: bytes, limit: int = 40) -> list[str]:
    tokens = lz77_encode(data)
    literal_count = sum(1 for token in tokens if isinstance(token, LiteralToken))
    match_tokens = [token for token in tokens if isinstance(token, MatchToken)]
    matched_bytes = sum(token.length for token in match_tokens)
    sizes = {
        "dynamic": len(compress_deflate_dynamic(data)),
        "fixed": len(compress_deflate_fixed(data)),
        "stored": len(compress_deflate_stored(data)),
    }
    auto_mode = min(sizes, key=sizes.get)
    literal_symbols, distance_symbols = _collect_deflate_symbol_counts(tokens)

    lines = [
        f"input_bytes={len(data)}",
        f"tokens_literal={literal_count}",
        f"tokens_match={len(match_tokens)}",
        f"matched_bytes={matched_bytes}",
        f"mode_bytes[dynamic]={sizes['dynamic']}",
        f"mode_bytes[fixed]={sizes['fixed']}",
        f"mode_bytes[stored]={sizes['stored']}",
        f"auto_choice={auto_mode}",
        f"top_literal_length_symbols={_format_counter(literal_symbols)}",
        f"top_distance_symbols={_format_counter(distance_symbols)}",
        "lz77_preview:",
    ]
    lines.extend(explain_lz77(data, limit=limit))
    return lines


def explain_zip_archive(data: bytes) -> list[str]:
    eocd_offset = find_eocd_offset(data)
    (
        _sig,
        _disk_no,
        _cd_disk_no,
        _entries_on_disk,
        entry_count,
        cd_size,
        cd_offset,
        comment_len,
    ) = struct.unpack_from("<IHHHHIIH", data, eocd_offset)
    entries = parse_central_directory(data)

    lines = [
        f"zip_bytes={len(data)}",
        f"eocd_offset={eocd_offset}",
        f"central_directory_offset={cd_offset}",
        f"central_directory_size={cd_size}",
        f"entry_count={entry_count}",
        f"comment_length={comment_len}",
    ]

    for entry in entries:
        (
            sig,
            _version_needed,
            _general_flag,
            _method,
            _mod_time,
            _mod_date,
            _crc_local,
            _comp_size_local,
            _uncomp_size_local,
            file_name_len,
            extra_len,
        ) = struct.unpack_from("<IHHHHHIIIHH", data, entry.local_header_offset)
        if sig != LFH_SIG:
            raise ValueError(f"invalid local header signature for {entry.name}")
        data_offset = entry.local_header_offset + 30 + file_name_len + extra_len
        flags = _format_flags(entry.general_flag)
        lines.append(
            f"{entry.name}: local_header={entry.local_header_offset} "
            f"data={data_offset} method={_method_name(entry.compress_method)} "
            f"compressed={entry.compressed_size} uncompressed={entry.uncompressed_size} "
            f"flags={flags}"
        )
    return lines


def _collect_deflate_symbol_counts(tokens: list[LiteralToken | MatchToken]) -> tuple[Counter[int], Counter[int]]:
    literal_symbols: Counter[int] = Counter()
    distance_symbols: Counter[int] = Counter()

    for token in tokens:
        if isinstance(token, LiteralToken):
            literal_symbols[token.value] += 1
            continue
        if isinstance(token, MatchToken):
            length_symbol, _length_extra, _length_bits = length_to_symbol(token.length)
            distance_symbol, _dist_extra, _dist_bits = distance_to_symbol(token.distance)
            literal_symbols[length_symbol] += 1
            distance_symbols[distance_symbol] += 1

    literal_symbols[256] += 1
    if not distance_symbols:
        distance_symbols[0] += 1
    return literal_symbols, distance_symbols


def _format_counter(counter: Counter[int], limit: int = 5) -> str:
    if not counter:
        return "-"
    parts = [f"{symbol}:{count}" for symbol, count in counter.most_common(limit)]
    return ", ".join(parts)


def _format_flags(flag: int) -> str:
    parts: list[str] = []
    if flag & 0x0008:
        parts.append("bit3-data-descriptor")
    if flag & 0x0800:
        parts.append("utf8-name")
    return ",".join(parts) if parts else "-"


def _method_name(method: int) -> str:
    if method == 0:
        return "store"
    if method == 8:
        return "deflate"
    return f"method-{method}"

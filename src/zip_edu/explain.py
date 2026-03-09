"""Helpers to inspect intermediate compression steps."""

from __future__ import annotations

from .lz77 import LiteralToken, MatchToken, lz77_encode


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


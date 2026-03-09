from __future__ import annotations

from zip_edu.lz77 import MAX_MATCH, MIN_MATCH, WINDOW_SIZE, LiteralToken, MatchToken, lz77_encode


def test_lz77_respects_match_limits() -> None:
    data = (b"abc" * 20000) + b"tail"
    tokens = lz77_encode(data)
    for t in tokens:
        if isinstance(t, LiteralToken):
            continue
        assert isinstance(t, MatchToken)
        assert MIN_MATCH <= t.length <= MAX_MATCH
        assert 1 <= t.distance <= WINDOW_SIZE


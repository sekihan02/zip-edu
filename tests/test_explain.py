from __future__ import annotations

from zip_edu.explain import explain_deflate, explain_zip_archive
from zip_edu.zip_format import build_zip


def test_explain_deflate_reports_mode_sizes() -> None:
    lines = explain_deflate((b"abcabcabcabc" * 20) + b"tail", limit=6)
    assert any(line.startswith("mode_bytes[dynamic]=") for line in lines)
    assert any(line.startswith("mode_bytes[fixed]=") for line in lines)
    assert any(line.startswith("mode_bytes[stored]=") for line in lines)
    assert any(line.startswith("auto_choice=") for line in lines)
    assert "lz77_preview:" in lines


def test_explain_zip_archive_reports_offsets() -> None:
    data = build_zip(
        [("a.txt", b"alpha alpha alpha"), ("deep/b.txt", b"beta beta beta")],
        compression="deflate-dynamic",
        use_data_descriptor=True,
    )
    lines = explain_zip_archive(data)
    assert any(line.startswith("eocd_offset=") for line in lines)
    assert any("a.txt: local_header=" in line for line in lines)
    assert any("deep/b.txt: local_header=" in line for line in lines)

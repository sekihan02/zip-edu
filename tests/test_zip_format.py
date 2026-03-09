from __future__ import annotations

from pathlib import Path
import zipfile

from zip_edu.zip_format import build_zip, extract_all, parse_central_directory


def test_build_zip_is_readable_by_zipfile(tmp_path: Path) -> None:
    entries = [
        ("a.txt", b"alpha alpha alpha"),
        ("nested/b.bin", bytes(range(64))),
    ]
    data = build_zip(entries, compression="deflate")
    zpath = tmp_path / "sample.zip"
    zpath.write_bytes(data)

    with zipfile.ZipFile(zpath, "r") as zf:
        assert sorted(zf.namelist()) == ["a.txt", "nested/b.bin"]
        assert zf.read("a.txt") == b"alpha alpha alpha"
        assert zf.read("nested/b.bin") == bytes(range(64))


def test_extract_all_from_zipfile_created_archive(tmp_path: Path) -> None:
    zpath = tmp_path / "in.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("x.txt", "hello dynamic zip")
        zf.writestr("deep/y.txt", "line1\nline2\nline3\n")

    out_dir = tmp_path / "out"
    extracted = extract_all(zpath.read_bytes(), out_dir)
    assert len(extracted) == 2
    assert (out_dir / "x.txt").read_text(encoding="utf-8") == "hello dynamic zip"
    assert (out_dir / "deep" / "y.txt").read_text(encoding="utf-8") == "line1\nline2\nline3\n"

    entries = parse_central_directory(zpath.read_bytes())
    assert {e.name for e in entries} == {"x.txt", "deep/y.txt"}


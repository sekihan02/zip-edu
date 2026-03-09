from __future__ import annotations

from pathlib import Path
import zipfile

from zip_edu.zip_format import LFH_SIG, build_zip, extract_all, parse_central_directory


def test_build_zip_is_readable_by_zipfile(tmp_path: Path) -> None:
    entries = [
        ("a.txt", b"alpha alpha alpha"),
        ("nested/b.bin", bytes(range(64))),
    ]
    data = build_zip(entries, compression="deflate-dynamic", use_data_descriptor=True)
    zpath = tmp_path / "sample.zip"
    zpath.write_bytes(data)

    with zipfile.ZipFile(zpath, "r") as zf:
        assert sorted(zf.namelist()) == ["a.txt", "nested/b.bin"]
        assert zf.read("a.txt") == b"alpha alpha alpha"
        assert zf.read("nested/b.bin") == bytes(range(64))


def test_build_zip_deflate_stored_block_is_readable(tmp_path: Path) -> None:
    entries = [("raw.bin", bytes([x % 251 for x in range(90000)]))]
    data = build_zip(entries, compression="deflate-stored")
    zpath = tmp_path / "stored_block.zip"
    zpath.write_bytes(data)
    with zipfile.ZipFile(zpath, "r") as zf:
        assert zf.read("raw.bin") == entries[0][1]


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


def test_central_directory_offsets_point_to_local_headers() -> None:
    data = build_zip(
        [("a.txt", b"aaa"), ("b/c.txt", b"bbb" * 100), ("d/e/f.txt", b"ccc")],
        compression="deflate-auto",
        use_data_descriptor=True,
    )
    entries = parse_central_directory(data)
    for e in entries:
        sig = int.from_bytes(data[e.local_header_offset : e.local_header_offset + 4], "little")
        assert sig == LFH_SIG

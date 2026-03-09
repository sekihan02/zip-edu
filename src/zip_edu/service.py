"""High-level services for packing/unpacking ZIP archives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .zip_format import ZipEntryInfo, ZipExtractedFile, build_zip, extract_all, parse_central_directory

ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class PackResult:
    output_zip: Path
    file_count: int
    total_input_bytes: int
    total_zip_bytes: int


def inspect_zip(zip_path: Path) -> list[ZipEntryInfo]:
    data = zip_path.read_bytes()
    return parse_central_directory(data)


def unpack_zip(zip_path: Path, output_dir: Path, progress: ProgressCallback | None = None) -> list[ZipExtractedFile]:
    data = zip_path.read_bytes()
    entries = parse_central_directory(data)
    if progress:
        progress(f"entries: {len(entries)}")
    extracted = extract_all(data, output_dir)
    if progress:
        progress(f"extracted: {len(extracted)} files")
    return extracted


def pack_zip(
    inputs: list[Path],
    output_zip: Path,
    compression: str = "deflate",
    progress: ProgressCallback | None = None,
) -> PackResult:
    files = _collect_input_files(inputs)
    if not files:
        raise ValueError("no input files found")
    if progress:
        progress(f"collect: {len(files)} files")

    total_input = sum(len(data) for _, data in files)
    archive = build_zip(files, compression=compression)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    output_zip.write_bytes(archive)
    if progress:
        progress(f"written: {output_zip}")

    return PackResult(
        output_zip=output_zip,
        file_count=len(files),
        total_input_bytes=total_input,
        total_zip_bytes=len(archive),
    )


def _collect_input_files(inputs: list[Path]) -> list[tuple[str, bytes]]:
    collected: list[tuple[str, bytes]] = []
    for input_path in inputs:
        p = input_path.resolve()
        if not p.exists():
            raise FileNotFoundError(f"input not found: {p}")
        if p.is_file():
            collected.append((p.name, p.read_bytes()))
            continue

        base = p.parent
        root_name = p.name
        files = sorted(x for x in p.rglob("*") if x.is_file())
        for f in files:
            rel = f.relative_to(base).as_posix()
            if not rel.startswith(root_name + "/"):
                rel = f"{root_name}/{f.relative_to(p).as_posix()}"
            collected.append((rel, f.read_bytes()))
    return collected


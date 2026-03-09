"""ZIP container parsing and writing (without using zipfile module)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import struct

from .crc32 import crc32
from .deflate import compress_deflate_fixed, decompress_deflate

LFH_SIG = 0x04034B50
CDH_SIG = 0x02014B50
EOCD_SIG = 0x06054B50


@dataclass(slots=True)
class ZipEntryInfo:
    name: str
    compress_method: int
    crc32_value: int
    compressed_size: int
    uncompressed_size: int
    local_header_offset: int
    general_flag: int


@dataclass(slots=True)
class ZipExtractedFile:
    name: str
    output_path: Path
    size: int


def parse_central_directory(data: bytes) -> list[ZipEntryInfo]:
    eocd_offset = _find_eocd_offset(data)
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
    if eocd_offset + 22 + comment_len > len(data):
        raise ValueError("invalid EOCD comment length")
    if cd_offset + cd_size > len(data):
        raise ValueError("central directory out of range")

    entries: list[ZipEntryInfo] = []
    pos = cd_offset
    for _ in range(entry_count):
        if pos + 46 > len(data):
            raise ValueError("truncated central directory header")
        (
            sig,
            _version_made,
            _version_needed,
            general_flag,
            method,
            _mod_time,
            _mod_date,
            crc,
            comp_size,
            uncomp_size,
            file_name_len,
            extra_len,
            comment_len,
            _disk_start,
            _int_attr,
            _ext_attr,
            local_offset,
        ) = struct.unpack_from("<IHHHHHHIIIHHHHHII", data, pos)
        if sig != CDH_SIG:
            raise ValueError("invalid central directory signature")
        pos += 46
        file_name = data[pos : pos + file_name_len]
        pos += file_name_len
        pos += extra_len
        pos += comment_len
        name = _decode_name(file_name, general_flag)
        entries.append(
            ZipEntryInfo(
                name=name,
                compress_method=method,
                crc32_value=crc,
                compressed_size=comp_size,
                uncompressed_size=uncomp_size,
                local_header_offset=local_offset,
                general_flag=general_flag,
            )
        )
    return entries


def extract_all(data: bytes, output_dir: Path) -> list[ZipExtractedFile]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result: list[ZipExtractedFile] = []

    for entry in parse_central_directory(data):
        safe_name = entry.name.replace("\\", "/")
        if safe_name.endswith("/"):
            dir_path = _safe_join(output_dir, safe_name)
            dir_path.mkdir(parents=True, exist_ok=True)
            continue

        local_pos = entry.local_header_offset
        if local_pos + 30 > len(data):
            raise ValueError(f"truncated local header for {entry.name}")
        (
            sig,
            _version_needed,
            _general_flag,
            method,
            _mod_time,
            _mod_date,
            _crc_local,
            _comp_size_local,
            _uncomp_size_local,
            file_name_len,
            extra_len,
        ) = struct.unpack_from("<IHHHHHIIIHH", data, local_pos)
        if sig != LFH_SIG:
            raise ValueError(f"invalid local header signature for {entry.name}")

        data_start = local_pos + 30 + file_name_len + extra_len
        data_end = data_start + entry.compressed_size
        if data_end > len(data):
            raise ValueError(f"truncated file data for {entry.name}")
        comp_data = data[data_start:data_end]

        if method == 0:
            file_data = comp_data
        elif method == 8:
            file_data = decompress_deflate(comp_data)
        else:
            raise ValueError(f"unsupported compression method {method} for {entry.name}")

        if len(file_data) != entry.uncompressed_size:
            raise ValueError(f"size mismatch for {entry.name}")
        if crc32(file_data) != entry.crc32_value:
            raise ValueError(f"CRC mismatch for {entry.name}")

        out_path = _safe_join(output_dir, safe_name)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(file_data)
        result.append(ZipExtractedFile(name=safe_name, output_path=out_path, size=len(file_data)))
    return result


def build_zip(entries: list[tuple[str, bytes]], compression: str = "deflate") -> bytes:
    zip_data = bytearray()
    central_records: list[tuple[int, int, int, int, int, int, bytes]] = []
    mod_time, mod_date = _dos_datetime(datetime.now())

    for arc_name, raw_data in entries:
        normalized_name = _normalize_arc_name(arc_name)
        if not normalized_name:
            continue
        name_bytes = normalized_name.encode("utf-8")
        flags = 0x0800  # UTF-8 names

        if compression == "deflate":
            method = 8
            comp_data = compress_deflate_fixed(raw_data)
        elif compression == "store":
            method = 0
            comp_data = raw_data
        else:
            raise ValueError("compression must be 'deflate' or 'store'")

        crc = crc32(raw_data)
        local_offset = len(zip_data)
        zip_data.extend(
            struct.pack(
                "<IHHHHHIIIHH",
                LFH_SIG,
                20,  # version needed
                flags,
                method,
                mod_time,
                mod_date,
                crc,
                len(comp_data),
                len(raw_data),
                len(name_bytes),
                0,  # extra length
            )
        )
        zip_data.extend(name_bytes)
        zip_data.extend(comp_data)

        central_records.append((flags, method, crc, len(comp_data), len(raw_data), local_offset, name_bytes))

    central_offset = len(zip_data)
    entry_count = len(central_records)
    for flags, method, crc, comp_size, uncomp_size, local_offset, name_bytes in central_records:
        zip_data.extend(
            struct.pack(
                "<IHHHHHHIIIHHHHHII",
                CDH_SIG,
                0x0314,  # version made by (UNIX, 2.0)
                20,  # version needed
                flags,
                method,
                mod_time,
                mod_date,
                crc,
                comp_size,
                uncomp_size,
                len(name_bytes),
                0,  # extra length
                0,  # comment length
                0,  # disk start
                0,  # int attr
                0x20,  # ext attr
                local_offset,
            )
        )
        zip_data.extend(name_bytes)

    central_size = len(zip_data) - central_offset
    zip_data.extend(
        struct.pack(
            "<IHHHHIIH",
            EOCD_SIG,
            0,
            0,
            entry_count,
            entry_count,
            central_size,
            central_offset,
            0,
        )
    )
    return bytes(zip_data)


def _normalize_arc_name(name: str) -> str:
    cleaned = name.replace("\\", "/").strip("/")
    return cleaned


def _decode_name(name_bytes: bytes, flag: int) -> str:
    if flag & 0x0800:
        return name_bytes.decode("utf-8")
    return name_bytes.decode("cp437")


def _find_eocd_offset(data: bytes) -> int:
    min_pos = max(0, len(data) - 65557)
    sig = struct.pack("<I", EOCD_SIG)
    for pos in range(len(data) - 22, min_pos - 1, -1):
        if data[pos : pos + 4] == sig:
            return pos
    raise ValueError("EOCD not found")


def _dos_datetime(dt: datetime) -> tuple[int, int]:
    year = min(max(dt.year, 1980), 2107)
    dos_time = (dt.hour << 11) | (dt.minute << 5) | (dt.second // 2)
    dos_date = ((year - 1980) << 9) | (dt.month << 5) | dt.day
    return dos_time, dos_date


def _safe_join(root: Path, arc_name: str) -> Path:
    target = (root / arc_name).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path traversal detected: {arc_name}") from exc
    return target

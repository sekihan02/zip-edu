from __future__ import annotations

import zlib

from zip_edu.deflate import (
    compress_deflate,
    compress_deflate_dynamic,
    compress_deflate_fixed,
    compress_deflate_stored,
    decompress_deflate,
)


def test_fixed_roundtrip() -> None:
    data = (b"ABRACADABRA " * 200) + bytes(range(256)) + (b"\x00" * 128)
    compressed = compress_deflate_fixed(data)
    assert decompress_deflate(compressed) == data


def test_fixed_is_valid_raw_deflate() -> None:
    data = b"hello hello hello hello hello"
    compressed = compress_deflate_fixed(data)
    assert zlib.decompress(compressed, wbits=-15) == data


def test_dynamic_roundtrip() -> None:
    data = (b"dynamic mode test " * 500) + bytes(range(128))
    compressed = compress_deflate_dynamic(data)
    assert decompress_deflate(compressed) == data


def test_dynamic_is_valid_raw_deflate() -> None:
    data = (b"abcde " * 1000) + (b"\x00\xFF" * 120)
    compressed = compress_deflate_dynamic(data)
    assert zlib.decompress(compressed, wbits=-15) == data


def test_stored_block_roundtrip_multi_block() -> None:
    data = bytes([x % 251 for x in range(160000)])
    compressed = compress_deflate_stored(data)
    assert decompress_deflate(compressed) == data
    assert zlib.decompress(compressed, wbits=-15) == data


def test_auto_mode_roundtrip() -> None:
    data = (b"auto mode selection " * 500) + b"tail"
    compressed = compress_deflate(data, mode="auto")
    assert decompress_deflate(compressed) == data


def test_decode_dynamic_deflate_from_zlib() -> None:
    data = b"dynamic tree test " * 400
    compressed = zlib.compress(data, level=9, wbits=-15)
    assert decompress_deflate(compressed) == data

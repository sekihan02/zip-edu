from __future__ import annotations

import zlib

from zip_edu.deflate import compress_deflate_fixed, decompress_deflate


def test_fixed_roundtrip() -> None:
    data = (b"ABRACADABRA " * 200) + bytes(range(256)) + (b"\x00" * 128)
    compressed = compress_deflate_fixed(data)
    assert decompress_deflate(compressed) == data


def test_fixed_is_valid_raw_deflate() -> None:
    data = b"hello hello hello hello hello"
    compressed = compress_deflate_fixed(data)
    assert zlib.decompress(compressed, wbits=-15) == data


def test_decode_dynamic_deflate_from_zlib() -> None:
    data = b"dynamic tree test " * 400
    compressed = zlib.compress(data, level=9, wbits=-15)
    assert decompress_deflate(compressed) == data


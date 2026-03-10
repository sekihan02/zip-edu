"""CLI entry point for zip_edu."""

from __future__ import annotations

import argparse
from pathlib import Path

from .explain import explain_deflate, explain_lz77, explain_zip_archive
from .service import inspect_zip, pack_zip, unpack_zip


def main() -> None:
    parser = argparse.ArgumentParser(description="Educational ZIP compressor/decompressor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pack = sub.add_parser("pack", help="Create a ZIP archive")
    p_pack.add_argument("output_zip", type=Path, help="Output ZIP path")
    p_pack.add_argument("inputs", nargs="+", type=Path, help="Input files or directories")
    p_pack.add_argument("--store", action="store_true", help="Use ZIP Store method (no Deflate)")
    p_pack.add_argument(
        "--deflate-mode",
        choices=["auto", "dynamic", "fixed", "stored"],
        default="auto",
        help="Deflate block mode (ignored with --store)",
    )
    p_pack.add_argument(
        "--data-descriptor",
        action="store_true",
        help="Write local header with bit3 flag and trailing data descriptor",
    )

    p_unpack = sub.add_parser("unpack", help="Extract a ZIP archive")
    p_unpack.add_argument("zip_path", type=Path, help="Input ZIP path")
    p_unpack.add_argument("-o", "--output", type=Path, default=Path("out"), help="Output directory")

    p_inspect = sub.add_parser("inspect", help="Show ZIP entries")
    p_inspect.add_argument("zip_path", type=Path, help="Input ZIP path")

    p_explain = sub.add_parser("explain-lz77", help="Show LZ77 tokenization")
    g = p_explain.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", type=str, help="Input text")
    g.add_argument("--file", type=Path, help="Input file")
    p_explain.add_argument("--limit", type=int, default=120, help="Max token lines")

    p_explain_deflate = sub.add_parser("explain-deflate", help="Show DEFLATE stages")
    g = p_explain_deflate.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", type=str, help="Input text")
    g.add_argument("--file", type=Path, help="Input file")
    p_explain_deflate.add_argument("--limit", type=int, default=40, help="Max LZ77 preview lines")

    p_explain_zip = sub.add_parser("explain-zip", help="Show ZIP container structure")
    p_explain_zip.add_argument("zip_path", type=Path, help="Input ZIP path")

    args = parser.parse_args()

    if args.command == "pack":
        compression = "store" if args.store else f"deflate-{args.deflate_mode}"
        result = pack_zip(
            args.inputs,
            args.output_zip,
            compression=compression,
            use_data_descriptor=args.data_descriptor,
            progress=print,
        )
        ratio = 0.0
        if result.total_input_bytes > 0:
            ratio = result.total_zip_bytes / result.total_input_bytes
        print(f"files={result.file_count}")
        print(f"input={result.total_input_bytes} bytes")
        print(f"zip={result.total_zip_bytes} bytes")
        print(f"ratio={ratio:.3f}")
    elif args.command == "unpack":
        extracted = unpack_zip(args.zip_path, args.output, progress=print)
        total = sum(x.size for x in extracted)
        print(f"extracted_files={len(extracted)}")
        print(f"total={total} bytes")
    elif args.command == "inspect":
        entries = inspect_zip(args.zip_path)
        print(f"entries={len(entries)}")
        for e in entries:
            print(
                f"{e.name} | method={e.compress_method} | "
                f"compressed={e.compressed_size} | uncompressed={e.uncompressed_size}"
            )
    elif args.command == "explain-lz77":
        if args.text is not None:
            src = args.text.encode("utf-8")
        else:
            src = args.file.read_bytes()
        for line in explain_lz77(src, limit=args.limit):
            print(line)
    elif args.command == "explain-deflate":
        if args.text is not None:
            src = args.text.encode("utf-8")
        else:
            src = args.file.read_bytes()
        for line in explain_deflate(src, limit=args.limit):
            print(line)
    elif args.command == "explain-zip":
        for line in explain_zip_archive(args.zip_path.read_bytes()):
            print(line)


if __name__ == "__main__":
    main()

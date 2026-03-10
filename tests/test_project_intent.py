from __future__ import annotations

import ast
import importlib
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]

CORE_FILES = [
    ROOT / "src/zip_edu/bitstream.py",
    ROOT / "src/zip_edu/crc32.py",
    ROOT / "src/zip_edu/deflate.py",
    ROOT / "src/zip_edu/huffman.py",
    ROOT / "src/zip_edu/lz77.py",
    ROOT / "src/zip_edu/zip_format.py",
]

FORBIDDEN_IMPORTS = {"zipfile", "zlib", "bz2", "lzma", "tarfile"}


def test_core_logic_does_not_import_compression_libraries() -> None:
    for path in CORE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module.split(".", 1)[0])
        assert imported_names.isdisjoint(FORBIDDEN_IMPORTS), path.name


def test_pyproject_keeps_core_dependency_free_and_gui_optional() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dependencies"] == []
    extras = pyproject["project"]["optional-dependencies"]
    assert "gui" in extras
    assert "build" in extras


def test_gui_module_imports_even_without_pyside_runtime() -> None:
    gui = importlib.import_module("zip_edu.gui")
    assert hasattr(gui, "run")

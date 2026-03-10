"""PySide6 GUI for educational ZIP pack/unpack."""

from __future__ import annotations

import sys
from pathlib import Path

from .service import inspect_zip, pack_zip, unpack_zip

_PYSIDE_IMPORT_ERROR: Exception | None = None

try:
    from PySide6.QtCore import QThread, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - depends on optional extra
    _PYSIDE_IMPORT_ERROR = exc
else:

    class ZipWorker(QThread):
        log = Signal(str)
        succeeded = Signal(object)
        failed = Signal(str)

        def __init__(self, mode: str, payload: dict) -> None:
            super().__init__()
            self.mode = mode
            self.payload = payload

        def run(self) -> None:
            try:
                if self.mode == "pack":
                    result = pack_zip(
                        self.payload["inputs"],
                        self.payload["output_zip"],
                        compression=self.payload["compression"],
                        use_data_descriptor=self.payload["use_data_descriptor"],
                        progress=self.log.emit,
                    )
                elif self.mode == "unpack":
                    result = unpack_zip(
                        self.payload["zip_path"],
                        self.payload["output_dir"],
                        progress=self.log.emit,
                    )
                elif self.mode == "inspect":
                    result = inspect_zip(self.payload["zip_path"])
                else:
                    raise ValueError("unknown mode")
                self.succeeded.emit(result)
            except Exception as exc:  # noqa: BLE001 - show in GUI
                self.failed.emit(str(exc))


    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("ZIP Education Tool")
            self.resize(980, 620)
            self._worker: ZipWorker | None = None

            root = QWidget(self)
            self.setCentralWidget(root)
            main = QVBoxLayout(root)

            top = QGridLayout()
            top.addWidget(self._build_pack_group(), 0, 0)
            top.addWidget(self._build_unpack_group(), 0, 1)
            main.addLayout(top)

            self.log_view = QTextEdit(self)
            self.log_view.setReadOnly(True)
            main.addWidget(QLabel("ログ"))
            main.addWidget(self.log_view)

        def _build_pack_group(self) -> QGroupBox:
            box = QGroupBox("圧縮 (ZIP 作成)", self)
            layout = QVBoxLayout(box)

            self.pack_inputs = QListWidget(self)
            layout.addWidget(QLabel("入力ファイル/ディレクトリ"))
            layout.addWidget(self.pack_inputs)

            btns = QHBoxLayout()
            self.btn_add_file = QPushButton("ファイル追加", self)
            self.btn_add_dir = QPushButton("ディレクトリ追加", self)
            self.btn_clear_inputs = QPushButton("クリア", self)
            btns.addWidget(self.btn_add_file)
            btns.addWidget(self.btn_add_dir)
            btns.addWidget(self.btn_clear_inputs)
            layout.addLayout(btns)

            self.pack_output = QLineEdit(self)
            self.btn_pack_output = QPushButton("出力先...", self)
            out_row = QHBoxLayout()
            out_row.addWidget(self.pack_output)
            out_row.addWidget(self.btn_pack_output)
            layout.addWidget(QLabel("出力 ZIP"))
            layout.addLayout(out_row)

            self.pack_method = QComboBox(self)
            self.pack_method.addItem("Deflate (自動選択)", "deflate-auto")
            self.pack_method.addItem("Deflate (動的ハフマン)", "deflate-dynamic")
            self.pack_method.addItem("Deflate (固定ハフマン)", "deflate-fixed")
            self.pack_method.addItem("Deflate (非圧縮ブロック BTYPE=00)", "deflate-stored")
            self.pack_method.addItem("Store (無圧縮)", "store")
            layout.addWidget(QLabel("圧縮方式"))
            layout.addWidget(self.pack_method)

            self.pack_data_descriptor = QCheckBox("データデスクリプタ(bit3)を使う", self)
            layout.addWidget(self.pack_data_descriptor)

            self.btn_pack = QPushButton("ZIP 作成", self)
            layout.addWidget(self.btn_pack)

            self.btn_add_file.clicked.connect(self._on_add_file)
            self.btn_add_dir.clicked.connect(self._on_add_dir)
            self.btn_clear_inputs.clicked.connect(self.pack_inputs.clear)
            self.btn_pack_output.clicked.connect(self._on_pick_pack_output)
            self.btn_pack.clicked.connect(self._on_pack)
            return box

        def _build_unpack_group(self) -> QGroupBox:
            box = QGroupBox("解凍 (ZIP 展開)", self)
            layout = QVBoxLayout(box)

            self.unpack_zip = QLineEdit(self)
            self.btn_unpack_zip = QPushButton("ZIP 選択...", self)
            zip_row = QHBoxLayout()
            zip_row.addWidget(self.unpack_zip)
            zip_row.addWidget(self.btn_unpack_zip)
            layout.addWidget(QLabel("入力 ZIP"))
            layout.addLayout(zip_row)

            self.unpack_output = QLineEdit(self)
            self.btn_unpack_output = QPushButton("出力先...", self)
            out_row = QHBoxLayout()
            out_row.addWidget(self.unpack_output)
            out_row.addWidget(self.btn_unpack_output)
            layout.addWidget(QLabel("展開先ディレクトリ"))
            layout.addLayout(out_row)

            act_row = QHBoxLayout()
            self.btn_inspect = QPushButton("内容確認", self)
            self.btn_unpack = QPushButton("解凍実行", self)
            act_row.addWidget(self.btn_inspect)
            act_row.addWidget(self.btn_unpack)
            layout.addLayout(act_row)

            self.btn_unpack_zip.clicked.connect(self._on_pick_unpack_zip)
            self.btn_unpack_output.clicked.connect(self._on_pick_unpack_output)
            self.btn_inspect.clicked.connect(self._on_inspect)
            self.btn_unpack.clicked.connect(self._on_unpack)
            return box

        def _on_add_file(self) -> None:
            files, _ = QFileDialog.getOpenFileNames(self, "追加するファイルを選択")
            for f in files:
                self.pack_inputs.addItem(f)

        def _on_add_dir(self) -> None:
            path = QFileDialog.getExistingDirectory(self, "追加するディレクトリを選択")
            if path:
                self.pack_inputs.addItem(path)

        def _on_pick_pack_output(self) -> None:
            path, _ = QFileDialog.getSaveFileName(self, "出力ZIP", filter="ZIP Files (*.zip)")
            if path:
                if not path.lower().endswith(".zip"):
                    path += ".zip"
                self.pack_output.setText(path)

        def _on_pick_unpack_zip(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "入力ZIP", filter="ZIP Files (*.zip)")
            if path:
                self.unpack_zip.setText(path)

        def _on_pick_unpack_output(self) -> None:
            path = QFileDialog.getExistingDirectory(self, "展開先ディレクトリ")
            if path:
                self.unpack_output.setText(path)

        def _on_pack(self) -> None:
            if self._worker is not None:
                return
            inputs = [Path(self.pack_inputs.item(i).text()) for i in range(self.pack_inputs.count())]
            output = self.pack_output.text().strip()
            if not inputs:
                self._error("入力がありません")
                return
            if not output:
                self._error("出力ZIPを指定してください")
                return
            self._start_worker(
                "pack",
                {
                    "inputs": inputs,
                    "output_zip": Path(output),
                    "compression": self.pack_method.currentData(),
                    "use_data_descriptor": self.pack_data_descriptor.isChecked(),
                },
            )

        def _on_unpack(self) -> None:
            if self._worker is not None:
                return
            zip_path = self.unpack_zip.text().strip()
            output = self.unpack_output.text().strip()
            if not zip_path or not output:
                self._error("入力ZIPと展開先を指定してください")
                return
            self._start_worker("unpack", {"zip_path": Path(zip_path), "output_dir": Path(output)})

        def _on_inspect(self) -> None:
            if self._worker is not None:
                return
            zip_path = self.unpack_zip.text().strip()
            if not zip_path:
                self._error("入力ZIPを指定してください")
                return
            self._start_worker("inspect", {"zip_path": Path(zip_path)})

        def _start_worker(self, mode: str, payload: dict) -> None:
            self._set_busy(True)
            self._append_log(f"[start] {mode}")
            self._worker = ZipWorker(mode, payload)
            self._worker.log.connect(self._append_log)
            self._worker.failed.connect(self._on_worker_failed)
            self._worker.succeeded.connect(lambda result, m=mode: self._on_worker_succeeded(m, result))
            self._worker.finished.connect(lambda: self._set_busy(False))
            self._worker.finished.connect(self._clear_worker_ref)
            self._worker.start()

        def _on_worker_succeeded(self, mode: str, result: object) -> None:
            if mode == "pack":
                self._append_log("[done] zip created")
            elif mode == "unpack":
                self._append_log(f"[done] extracted {len(result)} files")
            elif mode == "inspect":
                entries = result
                self._append_log(f"[inspect] entries={len(entries)}")
                for e in entries:
                    self._append_log(
                        f"  {e.name} | method={e.compress_method} | "
                        f"{e.compressed_size} -> {e.uncompressed_size}"
                    )

        def _on_worker_failed(self, message: str) -> None:
            self._append_log(f"[error] {message}")
            self._error(message)

        def _clear_worker_ref(self) -> None:
            self._worker = None

        def _append_log(self, text: str) -> None:
            self.log_view.append(text)

        def _set_busy(self, busy: bool) -> None:
            for w in [
                self.btn_add_file,
                self.btn_add_dir,
                self.btn_clear_inputs,
                self.btn_pack_output,
                self.pack_data_descriptor,
                self.btn_pack,
                self.btn_unpack_zip,
                self.btn_unpack_output,
                self.btn_unpack,
                self.btn_inspect,
            ]:
                w.setEnabled(not busy)

        def _error(self, message: str) -> None:
            QMessageBox.critical(self, "Error", message)


def run() -> None:
    if _PYSIDE_IMPORT_ERROR is not None:
        raise SystemExit(
            "PySide6 is not installed. Install the GUI extra with: pip install -e .[gui]"
        ) from _PYSIDE_IMPORT_ERROR

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()

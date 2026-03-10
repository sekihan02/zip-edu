# zip-edu

ZIP の仕組みを理解するための学習用プロジェクトです。
圧縮・解凍のコアロジックは `zipfile` / `zlib` に頼らず、自前実装で ZIP コンテナと Deflate を追えるようにしています。
GUI は任意機能で、コア部分はサードパーティ依存なしで読める構成に整理しています。

## このコードで ZIP の仕組みを理解できるか

現状のコードは、理解目的の構成として成立するように整理してあります。見る順番は次の通りです。

- `src/zip_edu/bitstream.py`
  - Deflate のビット単位入出力
- `src/zip_edu/lz77.py`
  - LZ77 のトークン化
- `src/zip_edu/huffman.py`
  - 正準ハフマン符号の生成と復号
- `src/zip_edu/deflate.py`
  - `stored / fixed / dynamic` ブロックの圧縮と解凍
- `src/zip_edu/zip_format.py`
  - ローカルヘッダ、中央ディレクトリ、EOCD の生成と解析
- `src/zip_edu/explain.py`
  - 学習用の説明出力

特に以下のコマンドで「途中段階」を追えます。

- `zip-edu explain-lz77`
  - LZ77 のトークン列を見る
- `zip-edu explain-deflate`
  - トークン数、各 Deflate モードのサイズ、`auto` の選択結果を見る
- `zip-edu explain-zip`
  - EOCD、中央ディレクトリ、各ローカルヘッダの位置を見る

補足:

- テストでは互換性確認のために `zipfile` / `zlib` を使っています
- コアロジック `bitstream / lz77 / huffman / deflate / zip_format` では圧縮ライブラリを使っていません

## 実装範囲

- ZIP 展開
  - ZIP コンテナの手動パース
  - `Store(0)` / `Deflate(8)` をサポート
  - Deflate は `stored / fixed / dynamic` を解凍可能
- ZIP 圧縮
  - LZ77 をナイーブ実装
  - Deflate は `dynamic(BTYPE=10)` / `fixed(BTYPE=01)` / `stored(BTYPE=00)` で圧縮可能
  - `auto` では `dynamic / fixed / stored` のうち最短を選択
  - `bit3` フラグ + データデスクリプタにも対応
  - ZIP コンテナを手動生成
- 学習支援
  - LZ77 プレビュー
  - Deflate モード比較
  - ZIP コンテナ構造の説明出力
- GUI
  - PySide6 ベースの圧縮・解凍・内容確認

## ディレクトリ構成

```text
src/zip_edu/
  bitstream.py   # Deflate 向け bit reader/writer
  huffman.py     # 正準ハフマン符号
  lz77.py        # LZ77 トークン化
  deflate.py     # Deflate 圧縮/解凍
  crc32.py       # CRC32
  zip_format.py  # ZIP コンテナの生成/解析
  explain.py     # 学習用の説明出力
  service.py     # pack/unpack/inspect の高レベル API
  cli.py         # CUI
  gui.py         # PySide6 GUI
  pyinstaller_entry_cli.py  # PyInstaller 用 CLI ラッパー
  pyinstaller_entry_gui.py  # PyInstaller 用 GUI ラッパー
tests/
scripts/
  build_windows_exe.ps1
```

## セットアップ

### コアのみ

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

### GUI も使う

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[gui]"
```

`py -3.13` は例です。Python 3.11 以上があれば `3.11` / `3.12` / `3.13` のいずれでも構いません。

## 使い方

### CLI

```powershell
# 圧縮
zip-edu pack out.zip input_dir file1.txt

# 動的ハフマンを強制
zip-edu pack out_dynamic.zip input_dir --deflate-mode dynamic

# Deflate の非圧縮ブロックを強制
zip-edu pack out_stored_block.zip input_dir --deflate-mode stored

# ZIP Store
zip-edu pack --store out_store.zip input_dir

# bit3 + data descriptor
zip-edu pack out_dd.zip input_dir --deflate-mode auto --data-descriptor

# 解凍
zip-edu unpack in.zip -o out_dir

# 内容確認
zip-edu inspect in.zip

# LZ77 の途中結果を見る
zip-edu explain-lz77 --text "abracadabra abracadabra"

# Deflate のモード比較を見る
zip-edu explain-deflate --text "abracadabra abracadabra"

# ZIP コンテナ構造を見る
zip-edu explain-zip out.zip
```

### GUI

```powershell
zip-edu-gui
```

PySide6 を入れていない状態で `zip-edu-gui` を実行すると、GUI extra のインストール方法を表示して終了します。

## アルゴリズムの流れ

### 1. 圧縮

1. 入力バイト列を LZ77 で `Literal` / `Match(length, distance)` に分解
2. `Literal/Length` と `Distance` を Deflate シンボルへ変換
3. `stored / fixed / dynamic` のいずれかで Deflate ブロックを生成
4. 生成した Deflate データを ZIP の file data に格納
5. 最後に中央ディレクトリと EOCD を付与

### 2. 解凍

1. EOCD を見つけて中央ディレクトリを読む
2. 各エントリのローカルヘッダ位置をたどる
3. `Store` ならそのまま、`Deflate` ならブロックを復号
4. CRC32 とサイズを検証して出力

## 実行ファイル (exe) の作成

`.exe` の生成は Windows PowerShell で行ってください。
WSL から操作している場合も、`.exe` ビルドだけは `powershell.exe` 側で実行するのが安全です。

### 一番簡単な方法

仮想環境の作成、依存導入、テスト、PyInstaller 実行までまとめて行います。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1
```

必要なら Python のバージョンや仮想環境を明示できます。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1 -PythonVersion 3.13 -RecreateVenv
```

生成物:

- `dist\zip-edu-cli.exe`
- `dist\zip-edu-gui.exe`

### 手動で行う場合

```powershell
py -3.13 -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[build]"
python -m pytest -q
python -m PyInstaller --clean --noconfirm --onefile --console --name zip-edu-cli --workpath build/pyi-cli --specpath build/spec --distpath dist --paths src src/pyinstaller_entry_cli.py
python -m PyInstaller --clean --noconfirm --onefile --windowed --name zip-edu-gui --workpath build/pyi-gui --specpath build/spec --distpath dist --paths src src/pyinstaller_entry_gui.py
```

PowerShell の実行ポリシーで `Activate.ps1` が止まる場合:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## テスト

```powershell
python -m pytest -q
```

主な確認内容:

- 自前 `fixed / dynamic / stored` 圧縮の往復
- `zlib` 互換の Deflate 復号
- `zipfile` 互換の ZIP 読み書き
- EOCD / 中央ディレクトリ / ローカルヘッダの整合性
- コアロジックが圧縮ライブラリを import していないこと

## 注意

- 学習目的の実装であり、速度最適化はしていません
- LZ77 はナイーブ探索です
- 動的ハフマン生成は簡易実装のため、符号長制限に収まらない場合は固定ハフマンへフォールバックします
- ZIP64 / 暗号化 / 一部拡張仕様は未対応です

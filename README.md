# zip-edu

PySide6 を使った学習用 ZIP 圧縮・解凍ツールです。  
`zipfile` / `zlib` に頼らず、ZIP コンテナと Deflate をコードで追えるように実装しています。

## 目的

- ZIP の構造（ローカルヘッダ、中央ディレクトリ、EOCD）を理解する
- Deflate の構造（LZ77 + Huffman）を理解する
- GUI から圧縮/解凍を試しながらアルゴリズムを確認する

## 実装範囲

- ZIP 展開:
  - ZIP コンテナの手動パース
  - 圧縮方式 `Store(0)` / `Deflate(8)` をサポート
  - Deflate は `stored/fixed/dynamic` ブロックを解凍可能
- ZIP 圧縮:
  - LZ77 をナイーブ実装
  - Deflate は固定ハフマン (`BTYPE=01`) で圧縮
  - ZIP コンテナ（ローカルヘッダ/中央ディレクトリ/EOCD）を手動生成
- GUI:
  - PySide6 で圧縮、解凍、内容確認（inspect）

## ディレクトリ構成

```text
src/zip_edu/
  bitstream.py   # Deflate 向け bit reader/writer
  huffman.py     # 正準ハフマン符号
  lz77.py        # LZ77 トークン化
  deflate.py     # Deflate 圧縮/解凍
  crc32.py       # CRC32
  zip_format.py  # ZIP コンテナの生成/解析
  service.py     # pack/unpack/inspect の高レベル API
  cli.py         # CUI
  gui.py         # PySide6 GUI
tests/
  test_deflate.py
  test_zip_format.py
```

## セットアップ

```powershell
# Python 3.11+ を想定
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -U pip
pip install -e .
```

## 使い方

### GUI

```powershell
python -m zip_edu.gui
```

またはエントリポイント:

```powershell
zip-edu-gui
```

### CLI

```powershell
# 圧縮 (Deflate固定ハフマン)
zip-edu pack out.zip input_dir file1.txt

# 無圧縮(Store)
zip-edu pack --store out_store.zip input_dir

# 解凍
zip-edu unpack in.zip -o out_dir

# 内容確認
zip-edu inspect in.zip

# LZ77 トークン化の学習表示
zip-edu explain-lz77 --text "abracadabra abracadabra"
```

## アルゴリズムの要点

### 1. 圧縮 (Deflate固定ハフマン)

1. 入力バイト列を LZ77 で `Literal` または `Match(length, distance)` に変換  
2. `Literal/Length` と `Distance` を Deflate のシンボルへ変換  
3. 固定ハフマン符号でビット列へエンコード  
4. ZIP の file data として格納

### 2. 解凍

1. ZIP の中央ディレクトリを読み、各エントリ情報を取得  
2. file data を取り出し、圧縮方式に応じて復号  
   - `Store`: 生データ  
   - `Deflate`: ブロックヘッダ(`BFINAL`,`BTYPE`)ごとに復号  
3. CRC32 とサイズを検証して書き出し

### 3. ZIP コンテナ

- `Local File Header` + `Compressed Data` を各ファイル分連結
- 末尾に `Central Directory` を構築
- 最後に `EOCD` を付けて完成

## 実行ファイル (exe) の作成

PyInstaller を利用します。

```powershell
pip install pyinstaller

# GUI exe
python -m PyInstaller --noconfirm --onefile --windowed --name zip-edu-gui --paths src src/zip_edu/gui.py

# CLI exe
python -m PyInstaller --noconfirm --onefile --console --name zip-edu-cli --paths src src/zip_edu/cli.py
```

生成物:

- `dist/zip-edu-gui.exe`
- `dist/zip-edu-cli.exe`

### exe 化の仕組み

- PyInstaller は Python 実行環境・依存モジュール・エントリスクリプトを解析
- 必要ファイルをブートローダに同梱し、単一実行ファイルへ固める
- 起動時に内部展開し、同梱された Python インタプリタで `gui.py` / `cli.py` を実行

## テスト

```powershell
pip install pytest
pytest -q
```

## リポジトリ作成とリリース

### 1. 初期化とコミット

```powershell
git init
git add .
git commit -m "feat: educational ZIP/Deflate implementation with PySide6 GUI"
```

### 2. GitHub リポジトリ作成

`gh` を使う例:

```powershell
gh repo create zip-edu --public --source . --remote origin --push
```

### 3. リリース作成

```powershell
git tag v0.1.0
git push origin v0.1.0

# exe を添付する例
gh release create v0.1.0 dist/zip-edu-gui.exe dist/zip-edu-cli.exe -t "v0.1.0" -n "Initial release"
```

## 注意

- 教育目的の実装であり、速度最適化はしていません（LZ77 はナイーブ探索）
- ZIP64 / 暗号化 / 一部拡張仕様は未対応です


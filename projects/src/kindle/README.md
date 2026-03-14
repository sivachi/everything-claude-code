# Kindle to PDF Converter

Kindle本をPDFに変換するPythonツール集。スクリーンキャプチャ方式とCalibre変換の両方に対応。

## 🚀 クイックスタート

### 方法1: スクリーンキャプチャ方式（推奨）
DRM保護された本も変換可能。Kindleアプリの画面をキャプチャしてPDFを作成。

```bash
# テスト実行（1ページキャプチャ）
python3 kindle_capture_test.py

# 自動キャプチャ（10ページ）
python3 kindle_capture_auto.py -p 10 -o my_book.pdf

# 無制限キャプチャ（Ctrl+Cで停止）
python3 kindle_capture_auto.py -o my_book.pdf
```

### 方法2: Calibre変換方式
DRMフリーの本のみ対応。高品質な変換が可能。

```bash
# Calibreをインストール
brew install --cask calibre

# Kindle本を検索
python3 kindle_to_pdf_simple.py --list

# 本を変換
python3 kindle_to_pdf_simple.py /path/to/book.azw
```

## 📁 ファイル一覧

### メインツール
| ファイル | 説明 | 使用方法 |
|---------|------|----------|
| `kindle_capture_test.py` | スクリーンキャプチャのテスト | `python3 kindle_capture_test.py` |
| `kindle_capture_auto.py` | 自動スクリーンキャプチャ（推奨） | `python3 kindle_capture_auto.py -p 10` |
| `kindle_to_pdf_simple.py` | Calibre変換（DRMフリー） | `python3 kindle_to_pdf_simple.py book.azw` |
| `find_kindle_paths.py` | Kindle本の場所を検索 | `python3 find_kindle_paths.py` |

### 設定・その他
| ファイル | 説明 |
|---------|------|
| `config.yaml` | 詳細設定ファイル |
| `requirements.txt` | Python依存パッケージ |
| `setup.sh` | セットアップスクリプト |
| `old/` | テストファイルや旧バージョン |

## 🛠 インストール

### 基本インストール（スクリーンキャプチャ用）
```bash
# 最小限の依存パッケージ
pip3 install Pillow --user
```

### フルインストール（全機能）
```bash
# Calibreインストール（DRMフリー本の変換用）
brew install --cask calibre

# Python依存パッケージ
pip3 install -r requirements.txt --user
```

## 💡 使用例

### 例1: Kindleアプリから本をPDFに変換
1. Amazon Kindle.appを開く
2. 変換したい本の最初のページを表示
3. ターミナルで実行:
```bash
# 20ページを2秒間隔でキャプチャ
python3 kindle_capture_auto.py -p 20 -d 2 -o "本のタイトル.pdf"
```

### 例2: Kindle本の場所を探す
```bash
python3 find_kindle_paths.py
```

### 例3: DRMフリーの本を高品質変換
```bash
python3 kindle_to_pdf_simple.py ~/Downloads/sample.azw -o sample.pdf
```

## ⚙️ オプション

### kindle_capture_auto.py
- `-o, --output` : 出力PDFファイル名（デフォルト: kindle_book.pdf）
- `-p, --pages` : キャプチャするページ数（デフォルト: 無制限）
- `-d, --delay` : ページ間の待機時間（秒）（デフォルト: 2）

### kindle_to_pdf_simple.py
- `--list` : 利用可能なKindle本を一覧表示
- `--all` : ディレクトリ内の全ての本を変換
- `-o, --output` : 出力ディレクトリ

## 🔍 Kindle本の保存場所

### macOS
- `/Applications/Amazon Kindle.app` - Kindleアプリ
- `~/Library/Containers/com.amazon.Lassen/` - Kindleデータ
- `~/Library/Containers/com.amazon.Kindle/Data/Library/Application Support/Kindle/My Kindle Content/`

### Windows
- `C:\Users\[username]\Documents\My Kindle Content\`
- `C:\Users\[username]\AppData\Local\Amazon\Kindle\`

## ⚠️ 注意事項

### スクリーンキャプチャ方式

#### 📋 必要な権限設定（重要）
macOSでは以下の権限が必要です：

1. **画面収録権限**
   - `システム環境設定` > `セキュリティとプライバシー` > `プライバシー` > `画面収録`
   - 「ターミナル」にチェックを入れる
   - VSCodeやiTermを使用している場合は、それらにもチェックを入れる

2. **アクセシビリティ権限**（自動ページめくり用）
   - `システム環境設定` > `セキュリティとプライバシー` > `プライバシー` > `アクセシビリティ`
   - 「ターミナル」にチェックを入れる
   - これにより、AppleScriptでのキー入力シミュレーションが可能になります

#### 🔓 権限の付与方法
1. 🔒 をクリックして変更を許可
2. 管理者パスワードを入力
3. 該当アプリにチェックを入れる
4. アプリを再起動（ターミナルを閉じて開き直す）

#### ⚠️ 権限エラーが出た場合
```bash
# 権限をリセット
tccutil reset ScreenCapture
tccutil reset Accessibility

# その後、システム環境設定で再度権限を付与
```

### Calibre変換方式
- DRM保護された本は変換できません
- DRMフリーの本、またはDRMが解除された本のみ対応

## 🐛 トラブルシューティング

### 問題: スクリーンキャプチャが動作しない
```bash
# 権限を確認
tccutil reset ScreenCapture
# システム環境設定で権限を再付与
```

### 問題: Calibreが見つからない
```bash
# Calibreを再インストール
brew reinstall --cask calibre
# パスを確認
which ebook-convert
```

### 問題: Kindle本が見つからない
```bash
# Kindle本の場所を検索
python3 find_kindle_paths.py
# mdfindで検索
mdfind -name "*.azw"
```

## 📝 設定ファイル

`config.yaml`で詳細設定が可能:
```yaml
capture:
  delay_between_pages: 2.0  # ページ間の待機時間
  page_turn_key: 'right'    # ページめくりキー
  
processing:
  enhance_contrast: true    # コントラスト強調
  remove_margins: true      # 余白除去
  
output:
  quality: 95               # JPEG品質
  dpi: 150                  # PDF解像度
```

## 📄 ライセンス

MIT License

## 🤝 貢献

バグ報告や機能リクエストは[Issues](https://github.com/yourusername/kindle_scan/issues)へ。

## ⚖️ 法的注意

このツールは個人使用のみを目的としています。著作権法を遵守し、個人的なバックアップ目的でのみ使用してください。変換したPDFを配布しないでください。
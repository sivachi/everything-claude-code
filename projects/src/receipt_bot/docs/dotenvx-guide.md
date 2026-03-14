# dotenvx 使い方ガイド

dotenvxは、dotenvの作者が開発したセキュアな環境変数管理ツール。
AES-256暗号化により、`.env`ファイルを安全にGitにコミットできる。

## インストール

### npm（プロジェクトローカル）

```bash
npm install @dotenvx/dotenvx --save
# または
pnpm add @dotenvx/dotenvx
```

### Homebrew（グローバル - 推奨）

```bash
brew install dotenvx/brew/dotenvx
```

### シェルスクリプト

```bash
curl -sfS https://dotenvx.sh | sh
```

### Windows

```bash
winget install dotenvx
```

## 基本的な使い方

### 1. 環境変数を読み込んでコマンド実行

```bash
# .envを読み込んでコマンド実行
dotenvx run -- node index.js

# npm scriptと組み合わせ
dotenvx run -- npm run dev
```

### 2. 特定の環境ファイルを指定

```bash
# .env.productionを読み込む
dotenvx run -f .env.production -- node index.js

# 複数ファイルを読み込む（後のファイルが優先）
dotenvx run -f .env -f .env.local -- node index.js
```

### 3. package.jsonでの使用例

```json
{
  "scripts": {
    "dev": "dotenvx run -- node src/index.js",
    "dev:prod": "dotenvx run -f .env.production -- node src/index.js"
  }
}
```

## 暗号化機能

### 暗号化の初期設定

```bash
# .envファイルを暗号化
dotenvx encrypt

# 特定の環境ファイルを暗号化
dotenvx encrypt -f .env.production
```

暗号化すると以下が生成される：
- `.env` - 暗号化された値と`DOTENV_PUBLIC_KEY`を含む
- `.env.keys` - 復号化用の秘密鍵（**絶対にコミットしない**）

### 暗号化された.envの例

```bash
#/-------------------[DOTENV_PUBLIC_KEY]--------------------/
#/            public-key encryption for .env files          /
#/----------------------------------------------------------/
DOTENV_PUBLIC_KEY="034af93e93708b994a0xxxxxxxxxxxxxx"

# .env
DATABASE_URL="encrypted:BDxxxxxxxxxxxxxxxxx..."
API_KEY="encrypted:BDxxxxxxxxxxxxxxxxx..."
```

### 環境変数の追加・更新

```bash
# 暗号化して値を設定
dotenvx set KEY "value"

# 特定の環境ファイルに設定
dotenvx set KEY "value" -f .env.production
```

### 復号化

```bash
# .env.keysがあれば自動で復号化される
dotenvx run -- node index.js

# 本番環境では環境変数で秘密鍵を渡す
DOTENV_PRIVATE_KEY="xxxxxxxx" dotenvx run -- node index.js
```

## コードでの使用

### Node.js

```javascript
// dotenvからの移行は1行変更するだけ
// 変更前: require('dotenv').config()
require('@dotenvx/dotenvx').config()

// ES Modules
import { config } from '@dotenvx/dotenvx'
config()

// process.envで通常通りアクセス
console.log(process.env.DATABASE_URL)
```

## チームでの運用

### .gitignoreの設定

```gitignore
# 秘密鍵は絶対にコミットしない
.env.keys

# 暗号化された.envはコミットしてOK
# .env
# .env.production
```

### 秘密鍵の共有方法

1. **CI/CD**: 環境変数`DOTENV_PRIVATE_KEY`として設定
2. **チームメンバー**: 安全な方法で共有（1Password、Slack DMなど）
3. **ローカル開発**: `.env.keys`ファイルを各自保持

### 環境別の秘密鍵

```bash
# 各環境の秘密鍵を環境変数で設定
DOTENV_PRIVATE_KEY_PRODUCTION="xxx"
DOTENV_PRIVATE_KEY_STAGING="yyy"
```

## よく使うコマンド一覧

| コマンド | 説明 |
|---------|------|
| `dotenvx run -- <cmd>` | .envを読み込んでコマンド実行 |
| `dotenvx run -f <file> -- <cmd>` | 指定ファイルを読み込んで実行 |
| `dotenvx encrypt` | .envを暗号化 |
| `dotenvx encrypt -f <file>` | 指定ファイルを暗号化 |
| `dotenvx set KEY value` | 暗号化して値を設定 |
| `dotenvx get KEY` | 値を取得 |
| `dotenvx decrypt` | .envを復号化（平文に戻す） |

## トラブルシューティング

### 秘密鍵が見つからないエラー

```
[DECRYPTION_FAILED] Unable to decrypt .env
```

→ `.env.keys`ファイルがあるか、`DOTENV_PRIVATE_KEY`環境変数が設定されているか確認

### 暗号化されていない値がある

```bash
# 全ての値を暗号化
dotenvx encrypt
```

## 参考リンク

- 公式サイト: https://dotenvx.com/
- GitHub: https://github.com/dotenvx/dotenvx
- ドキュメント: https://dotenvx.com/docs

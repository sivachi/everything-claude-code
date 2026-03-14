# Discord Bot 起動方法

## 起動コマンド

```bash
cd packages/bot
npm run dev
```

## 起動成功時のメッセージ

```
Logged in as [Bot名]!
Started refreshing application (/) commands.
Successfully reloaded application (/) commands.
```

## 前提条件

1. **環境変数の設定**
   - `.env` ファイルに以下が設定されていること：
     - DISCORD_BOT_TOKEN
     - DISCORD_CLIENT_ID
     - SUPABASE_URL
     - SUPABASE_SERVICE_KEY
     - GEMINI_API_KEY

2. **Supabase データベースのセットアップ**
   - 以下のマイグレーションファイルを順番に実行：
     1. 001_initial_schema.sql
     2. 002_storage_policies.sql
     3. 003_functions.sql
     4. 004_update_expense_categories_safe.sql
     5. 005_add_tags.sql

3. **Discord Bot の招待**
   - Discord Developer Portal でボットをサーバーに招待
   - 必要な権限：Send Messages, Use Slash Commands, Embed Links, Attach Files

## その他のコマンド

### ビルド & 本番実行
```bash
npm run build  # TypeScriptコンパイル
npm start      # 本番実行
```

### プロジェクトルートから実行
```bash
cd /Users/algo-q/Documents/GitHub/04_receipt_bot
npm run dev    # monorepo全体を開発モードで実行
```

## トラブルシューティング

- 依存関係がインストールされていない場合：`npm install`
- ポートが使用中の場合：他のプロセスを終了
- 権限エラーの場合：Discord Bot の権限を確認
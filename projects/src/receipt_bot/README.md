# Discord レシート管理ボット

Discord からレシートをアップロードし、freee の勘定科目に合わせて分類・管理するシステムです。

## 機能

- 📸 レシート画像の OCR 解析（Gemini API）
- 🗂️ freee 標準の勘定科目で自動分類
- 📊 支出統計とレポート
- 💾 データエクスポート（CSV/JSON）
- 🎯 カスタム分類ルール

## セットアップ

### 1. 環境変数の設定

`packages/bot/.env` ファイルを作成し、以下の環境変数を設定：

```env
# Discord Bot
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CLIENT_ID=your_discord_client_id

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_supabase_service_key

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key
```

### 2. Supabase のセットアップ

1. Supabase プロジェクトを作成
2. SQL エディタで `supabase/migrations` 内の SQL ファイルを順番に実行：
   - `001_initial_schema.sql`
   - `002_storage_policies.sql`
   - `003_functions.sql`

### 3. Discord Bot のセットアップ

1. Discord Developer Portal で新しいアプリケーションを作成
2. Bot セクションで Token を取得
3. OAuth2 > URL Generator で以下の権限を選択：
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`, `Attach Files`
4. 生成された URL でボットをサーバーに招待

### 4. Google Gemini API のセットアップ

1. [Google AI Studio](https://makersuite.google.com/app/apikey) で API キーを取得
2. 環境変数に設定

## 起動方法

```bash
# 依存関係のインストール
cd packages/bot
npm install

# 開発モード
npm run dev

# ビルド & 本番実行
npm run build
npm start
```

## Discord コマンド

### `/receipt upload`
レシート画像をアップロードして解析

オプション:
- `image` (必須): レシート画像
- `category`: 経費科目を手動指定
- `note`: メモ

### `/receipt list`
レシート一覧を表示

オプション:
- `month`: 対象月 (YYYY-MM)
- `category`: カテゴリでフィルタ

### `/receipt stats`
統計情報を表示

オプション:
- `period`: 期間（week/month/year）

### `/receipt export`
データをエクスポート

オプション:
- `format`: CSV または JSON
- `month`: 対象月 (YYYY-MM)

### `/receipt category list`
利用可能なカテゴリ一覧

### `/receipt category set-default`
デフォルトカテゴリを設定

### `/receipt category add-rule`
自動分類ルールを追加

## 経費科目

freee 標準の勘定科目：
- `SUPPLIES`: 消耗品費
- `TRAVEL`: 旅費交通費
- `MEETING`: 会議費
- `ENTERTAINMENT`: 交際費
- `BOOKS`: 新聞図書費
- `COMMUNICATION`: 通信費
- `UTILITIES`: 水道光熱費
- `COMMISSION`: 支払手数料
- `MISC`: 雑費

## トラブルシューティング

### Bot が応答しない
- Discord Bot Token が正しいか確認
- Bot がオンラインか確認
- 必要な権限があるか確認

### OCR が機能しない
- Gemini API キーが有効か確認
- 画像が鮮明か確認
- レート制限に達していないか確認

### Supabase エラー
- Service Key が正しいか確認
- マイグレーションが実行されているか確認
- RLS ポリシーが適切か確認
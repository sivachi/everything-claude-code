# API 設計

## 概要
レシートデータの CRUD 操作とダッシュボード用のエンドポイントを提供する REST API。

## エンドポイント一覧

### 認証
```
POST   /auth/discord/callback   # Discord OAuth2 コールバック
GET    /auth/me                 # 現在のユーザー情報
POST   /auth/logout             # ログアウト
```

### レシート管理
```
GET    /receipts                # レシート一覧取得
GET    /receipts/:id            # レシート詳細取得
POST   /receipts                # レシート作成
PUT    /receipts/:id            # レシート更新
DELETE /receipts/:id            # レシート削除
POST   /receipts/:id/confirm    # カテゴリ確定
```

### 統計・分析
```
GET    /stats/summary           # 期間別サマリー
GET    /stats/categories       # カテゴリ別集計
GET    /stats/trends           # トレンド分析
GET    /stats/monthly          # 月次レポート
```

### カテゴリ管理
```
GET    /categories              # カテゴリ一覧
GET    /categories/:id/rules    # 分類ルール取得
POST   /categories/rules        # 分類ルール追加
DELETE /categories/rules/:id    # 分類ルール削除
```

### エクスポート
```
GET    /export/csv              # CSV エクスポート
GET    /export/json             # JSON エクスポート
```

## リクエスト/レスポンス例

### レシート一覧取得
```http
GET /receipts?page=1&limit=20&month=2024-01&category=SUPPLIES
Authorization: Bearer {token}

Response:
{
  "data": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "storeName": "セブンイレブン",
      "amount": 1234,
      "receiptDate": "2024-01-15",
      "category": {
        "id": 1,
        "code": "SUPPLIES",
        "name": "消耗品費"
      },
      "imageUrl": "https://...",
      "thumbnailUrl": "https://..."
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "totalPages": 3
  }
}
```

### レシート作成
```http
POST /receipts
Content-Type: application/json

{
  "imageUrl": "https://...",
  "ocrData": {
    "storeName": "セブンイレブン",
    "amount": 1234,
    "taxAmount": 123,
    "date": "2024-01-15",
    "items": ["ペン", "ノート"]
  },
  "categoryId": 1,
  "note": "会議用資料"
}
```

### 月次サマリー取得
```http
GET /stats/summary?year=2024&month=1

Response:
{
  "period": "2024-01",
  "totalAmount": 45678,
  "receiptCount": 23,
  "averageAmount": 1986,
  "categories": [
    {
      "code": "SUPPLIES",
      "name": "消耗品費",
      "amount": 12345,
      "count": 10,
      "percentage": 27.0
    }
  ],
  "comparison": {
    "previousPeriod": "2023-12",
    "amountChange": 5678,
    "percentageChange": 14.2
  }
}
```

## エラーレスポンス

```json
{
  "error": {
    "code": "RECEIPT_NOT_FOUND",
    "message": "指定されたレシートが見つかりません",
    "details": {
      "receiptId": "123e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

## 認証・認可

1. **JWT トークン**
   - Discord OAuth2 で認証
   - アクセストークンの有効期限: 24時間
   - リフレッシュトークン対応

2. **CORS 設定**
   - ダッシュボードドメインのみ許可
   - 認証付きリクエスト対応

## レート制限

- 一般エンドポイント: 100req/分
- アップロード: 10req/分
- エクスポート: 5req/分
# 日次サマリー機能の使用方法

## 機能概要

毎日の支出をタグ・勘定科目ごとに集計して通知する機能です。

## コマンド一覧

### 1. 手動でサマリーを表示
```
/receipt summary [date:YYYY-MM-DD] [send-to-channel:true/false]
```
- `date`: 対象日（省略時は昨日）
- `send-to-channel`: チャンネルに送信するかどうか

### 2. 自動通知の設定
```
/receipt notify setup channel:#チャンネル [time:HH:MM]
```
- `channel`: 通知先チャンネル
- `time`: 通知時刻（省略時は21:00）

### 3. 通知設定の確認
```
/receipt notify status
```

### 4. 通知の停止
```
/receipt notify stop
```

## サマリーの内容

### 全体統計
- 総額
- レシート件数

### カテゴリ別集計
- 各カテゴリの合計金額と件数

### タグ別集計
- 各タグの合計金額と件数

### 主な支出
- 金額が大きい上位5件のレシート

## 使用例

### 手動でサマリーを確認
```
/receipt summary
```
→ 昨日のサマリーを自分だけに表示

### 特定の日のサマリーをチャンネルに送信
```
/receipt summary date:2024-03-15 send-to-channel:true
```
→ 2024年3月15日のサマリーをチャンネルに送信

### 毎日21時に自動通知を設定
```
/receipt notify setup channel:#general
```
→ #generalチャンネルに毎日21時に通知

### 毎日朝9時に自動通知を設定
```
/receipt notify setup channel:#expenses time:09:00
```
→ #expensesチャンネルに毎日9時に通知

## 注意事項

- 自動通知は前日のサマリーを送信します
- レシートがない日は通知されません
- 通知時刻は24時間形式（HH:MM）で指定
- 通知設定はユーザーごとに1つのみ
# プロジェクト進捗ログ

## 現在の状態
- 状態: 完了
- 最終更新: 2026-03-15
- 概要: works/ 配下の全プロジェクトを everything-claude-code/projects/ に統合完了

## TODO
- [ ] なし（新規タスク発生時に追加）

## 変更履歴
### 2026-03-15（gen精度評価の網羅化）
- 変更: `projects/gen/scripts/07_rag_eval.py`
  - 定量評価を追加（キーワード適合度・意味類似度・Chronicle意味類似度・文脈拡張率）
  - テストケースを8件→16件に拡張して再評価を実施
  - 評価結果を `projects/gen/output/rag_eval_report.json` / `rag_eval_report.md` に自動出力
  - Chronicle評価のバイアスを修正（hit数判定から意味類似度判定へ）
- 変更: `projects/gen/scripts/06_rag_improvements.py`
  - リランカーを `RRF + CrossEncoder` のハイブリッド再スコアに改善
  - Chronicle埋め込みキャッシュにエッジ内容ハッシュ検証を追加
  - `chunk_id` 欠損時の誤文脈展開を防ぐ安全処理を追加
  - プロファイル保存/読込に安全なファイル名正規化を追加（パストラバーサル対策）

### 2026-03-15（全プロジェクト統合）
- 作成: `projects/gen/` — AI竹尾関連を統合（AItakeo + ai_takeo + ai_takeo_local → gen）
  - `gen/scripts/` — データ処理・前処理スクリプト群
  - `gen/rag/` — RAG用ファイル（local_rag_takeo.py等）
  - `gen/sources/` — ソースデータ（人格コピープロジェクト・分析md）
  - `gen/output/` — 生成済みデータ
- 移動: `e2e` + `e2e 2` → `projects/03_e2e/`
- 移動: `csv/` → `projects/src/csv_merger/`
- 移動: `kindle/` → `projects/src/kindle/`
- 移動: `local-rag/` → `projects/src/local_rag/`
- 移動: `receipt_bot/` → `projects/src/receipt_bot/`
- 移動: `remotion-app/` → `projects/src/remotion_app/`
- 移動: `youtube/` → `projects/src/youtube/`
- 移動: スクレイパー群 → `projects/src/scrapers/`
- 移動: `障害者雇用/` → `projects/docs/障害者雇用/`
- 移動: `sennin_kankyo_kouchiku.md` → `projects/docs/`
- 移動: `ハローワーク採用_入社タスク一覧.md` → `projects/docs/`
- 移動: `20260315_神楽坂お散歩プラン.md` → `projects/docs/`
- 移動: `faiss_index.*` → `projects/old/`
- 削除: `fc2-ppv-4800340.mp4`（1.6GB動画）
- 削除: `receipt_bot.zip`（展開済み）
- 削除: `remotion/`（空ディレクトリ）
- 削除: 元の各ディレクトリ（統合済みのため）

### 2026-03-15（初期環境構築）
- 作成: `projects/` — everything-claude-code 内にプロジェクト作業場を構築
- 変更: `CLAUDE.md` — 仙人プロンプトのルールを統合
- 変更: `.gitignore` — Python関連の除外設定を追加

## 設計判断ログ
- (2026-03-15) AI竹尾関連は3箇所（AItakeo, ai_takeo, ai_takeo_local）に分散していたため、gen/に統合。ai_takeo_localが最新のコードベースのためベースとし、AItakeoのRAG系はgen/rag/、ai_takeoのソースデータはgen/sources/に配置。
- (2026-03-15) 初期環境を claude/ に構築後、everything-claude-code/projects/ に統合。既存のプラグイン構成を壊さず、自社開発用の作業場として projects/ サブディレクトリを追加する方針とした。

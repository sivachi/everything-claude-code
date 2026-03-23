# Project GEN パイプライン概要

## 概要
この `gen` プロジェクトは、動画生成パイプラインではなく、`玄` という人格を再現するための `RAG + Chronicle Graph` パイプラインです。

全体としては、以下の流れで動きます。

1. セッションHTMLを前処理してチャンク化する
2. 個人情報や固有名詞をマスクする
3. `玄_在り方.md` から人格グラフを構築する
4. チャンクを埋め込みして ChromaDB に登録する
5. アプリ実行時にハイブリッド検索、Chronicle 検索、リランキング、文脈拡張を行う
6. それらを Claude に渡して、`玄` として応答させる

## オフライン構築パイプライン

### 0. 在り方抽出・整理
`00_extract_principles.py` などの `00_*` 系スクリプトは、元データから `玄` の在り方や原則を抽出し、`玄_在り方.md` を磨くための補助工程です。

これは毎回の検索インデックス作成の前提になる、`Identity Layer` の整備工程です。

### 1. 前処理
`scripts/01_preprocess.py`

役割:

- `sources/Sources/*.html` を走査
- ファイルを `speaker_dialogue / unlabeled_audio / document` に分類
- 話者ラベル付きファイルでは `GEN` の発話ターンを抽出
- ラベルなし音声書き起こしでは段落ベースでチャンク化
- `chunks.jsonl` と `preprocess_stats.json` を出力

出力:

- `output/chunks.jsonl`
- `output/preprocess_stats.json`

現状の実データ:

- 対象ファイル数: `258`
- 総チャンク数: `12,089`
- `GEN` ターン: `687`
- 非 `GEN` ターン: `417`
- ラベルなしチャンク: `10,985`
- 平均チャンク長: `355文字`

### 2. PII マスク
`scripts/05_mask_pii.py`

役割:

- `chunks.jsonl` に対して個人名・施設名・イベント名をマスク
- `text` だけでなく `source_file` と `context_turns` も対象
- 毎回 `chunks_backup.jsonl` から復元して再適用するため、二重マスクを防げる

出力:

- 更新済み `output/chunks.jsonl`
- バックアップ `output/chunks_backup.jsonl`

### 3. Chronicle Graph 構築
`scripts/02_build_chronicle.py`

役割:

- `玄_在り方.md` を解析
- `Chronicle Graph` とセクション対応情報を生成
- システムプロンプト用のフルテキストも生成

出力:

- `output/chronicle_graph.json`
- `output/chronicle_sections.json`
- `output/chronicle_full_text.txt`

このレイヤーは、単なる検索結果に引っ張られず、`玄` の人格の芯を保つための構造化レイヤーです。

### 4. ベクトルインデックス作成
`scripts/03_index.py`

役割:

- `chunks.jsonl` を `ruri-v3-310m` で埋め込み
- `ChromaDB` に登録
- 全チャンク用と `GEN` 発話専用の2コレクションを構築

コレクション:

- `gen_chunks`: 全チャンク
- `gen_chunks_hi`: `GEN` ターンのみ

利用モデル:

- Embedding: `cl-nagoya/ruri-v3-310m`
- 次元数: `768`

## オンライン応答パイプライン
`scripts/04_app.py` が実際のアプリ本体です。

アプリ実行時は以下の順に処理されます。

1. ユーザー入力を受け取る
2. `ruri-v3-310m` でクエリ埋め込みを生成する
3. `Chroma` に対してセマンティック検索を行う
4. `BM25` でキーワード検索を行う
5. `RRF` で両者を統合する
6. クロスエンコーダーで再ランキングする
7. ヒットチャンクの前後を結合して文脈拡張する
8. `Chronicle Graph` に対して別途ベクトル検索する
9. 必要ならユーザープロファイル情報を差し込む
10. 在り方テキスト、検索チャンク、Chronicle エッジ、会話履歴をまとめて Claude に渡す
11. `玄` としてストリーミング応答を返す

## 精度改善レイヤー
`scripts/06_rag_improvements.py`

このモジュールは、アプリ本体から読み込まれる改善機能群です。

### 1. クロスエンコーダーリランキング
- `RRF` 統合後の候補を再スコアリング
- モデル: `hotchpotch/japanese-reranker-cross-encoder-xsmall-v1`

### 2. Chronicle Graph ベクトル検索
- `Chronicle Graph` のエッジ `target` を事前埋め込み
- 従来の bigram ベースより意味的に近いエッジを取得可能

### 3. チャンク文脈拡張
- 検索ヒットしたチャンクの前後チャンクを結合
- 単独チャンクより文脈を補いやすい

### 4. お客様プロファイル
- `profiles/*.json` で過去テーマやメモを保持
- システムプロンプトに注入して継続性を持たせる

## 評価パイプライン
`scripts/07_rag_eval.py`

役割:

- 改善前と改善後の検索品質を比較
- `RRFのみ` と `RRF + リランキング` の比較
- `bigram Chronicle` と `ベクトル Chronicle` の比較
- 文脈拡張の増分確認
- プロファイルセクション差分の確認

出力:

- `output/rag_eval_report.json`
- `output/rag_eval_report.md`

## 現時点の評価結果
`output/rag_eval_report.json` のサマリーは以下です。

- クエリ数: `16`
- キーワード適合度: `0.225 -> 0.240625`
- 意味類似度: `0.8410 -> 0.8424`
- Chronicle意味類似度: `0.8229 -> 0.8524`
- 文脈拡張率平均: `2.63倍`
- Chronicle意味類似度改善: `16/16クエリ`

この結果から、特に `Chronicle Graph` のベクトル検索改善が大きく効いていることが分かります。

## 実行順
最初から構築し直す場合の基本手順は以下です。

```bash
python3 scripts/01_preprocess.py
python3 scripts/05_mask_pii.py
python3 scripts/02_build_chronicle.py
python3 scripts/03_index.py --rebuild --batch-size 32
streamlit run scripts/04_app.py
```

## スクリプト一覧

### データ構築系
- `scripts/00_extract_principles.py`
- `scripts/00_phase2_only.py`
- `scripts/01_preprocess.py`
- `scripts/05_mask_pii.py`
- `scripts/02_build_chronicle.py`
- `scripts/03_index.py`

### 実行系
- `scripts/04_app.py`

### 改善・評価系
- `scripts/06_rag_improvements.py`
- `scripts/07_rag_eval.py`

## このプロジェクトの本質
この `gen` は単純なRAGではなく、以下の3層構造を持つ人格再現型RAGです。

1. `Identity Layer`
`玄_在り方.md` 由来の `Chronicle Graph` によって、人格の芯を保つ

2. `Case Layer`
過去セッションのチャンクを `Hybrid RAG` で検索し、事例ベースの根拠を出す

3. `Response Layer`
リランキング、文脈拡張、プロファイル、会話履歴を統合して Claude が応答を生成する

つまりこのプロジェクトは、単なる「似た文章検索」ではなく、
`玄が何を信じ、どう人を見て、どう言葉を返すか`
までを再現しようとしている構成です。

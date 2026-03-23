# CLAUDE_PROGRESS.md — nazo プロジェクト進捗

## プロジェクト概要
「謎の会」の録音データ・セッションHTMLから、スピリチュアル関連の知見を抽出・分類し、カテゴリ別マークダウンとして出力するパイプライン。

## 方式
Method B（Pythonパイプライン）— GENプロジェクトのアーキテクチャを参考。

## パイプライン構成
1. `process_nazokai.py` — HTML → MD変換（フィラー除去 + PIIマスク）※既存
2. `scripts/04_shrine_messages.py` — 神社メッセージdocx → 神様/神社ごとMD出力
3. `scripts/01_chunk.py --include-gen` — MD + TXT + GEN HTML → チャンク化 → `output/chunks.jsonl`
4. `scripts/02_classify.py` — Claude APIでチャンク要約＋カテゴリ分類 → `output/classified.jsonl`
5. `scripts/03_output.py` — 分類結果 → カテゴリ別MD出力 → `output_md/カテゴリ別/`

## データソース
- nazo HTMLファイル（30件）→ output_md/イベント + 運営・コンサル
- 録音データ文字起こし（5件全完了）
- GENソースHTML（258件）→ projects/gen/sources/Sources/
- 神社メッセージdocx（24件）→ /Users/tadaakikurata/works/神社メッセージ/

## 分類体系
`output_md/スピリチュアル分類.md` — 9大カテゴリ、3階層

## 分類結果サマリー（2026-03-23完了）
- 分類済み: 4,166/4,167チャンク
- スピリチュアル関連: 1,625件
- 非スピリチュアル: 2,541件
- カテゴリ別MD: 9カテゴリ + その他 + 統合ファイル → `output_md/カテゴリ別/`

## 完了タスク
- [x] HTML→MD変換（process_nazokai.py）
- [x] スピリチュアル分類体系の作成・改善
- [x] プロジェクトを projects/nazo に移動
- [x] 01_chunk.py 作成・実行
- [x] 02_classify.py 作成（バッチ処理+キーワードフィルタで最適化済み）
- [x] 03_output.py 作成・実行
- [x] 文字起こし完了: File 1〜5（全5件）
- [x] process_nazokai.py の INPUT_DIR を更新
- [x] GENソースHTML（258件）をパイプラインに統合
- [x] 神社メッセージdocx（24件）→ 神様/神社ごとMD出力（04_shrine_messages.py）
- [x] 神社メッセージMD（28ファイル, 306エントリ）をパイプラインに統合
- [x] チャンク化: 4,167チャンク（イベント215 + 運営115 + 神社450 + 録音32 + GEN3355）
- [x] 02_classify.py 全件分類完了（4,166件）
- [x] 03_output.py カテゴリ別MD生成完了
- [x] 事業計画書v2にセッションデータ・運営MTGの知見を反映
- [x] テスト29件全パス

## TODO
- [ ] File 4, 5 の文字起こしを01_chunk.py → 02_classify.py で取り込み（APIクレジット補充後）
- [ ] note記事の作成（分類済みデータからドラフト生成）
- [ ] nazo.world ドメインのメール設定

## ファイル構成
```
projects/nazo/
├── process_nazokai.py          # HTML→MD変換
├── scripts/
│   ├── 01_chunk.py             # チャンク化
│   ├── 02_classify.py          # 分類（Claude API）
│   ├── 03_output.py            # カテゴリ別MD出力
│   └── 04_shrine_messages.py   # 神社メッセージdocx→MD
├── tests/
│   └── test_pipeline.py        # パイプラインテスト（29件）
├── output/
│   ├── chunks.jsonl            # チャンクデータ（4,167件）
│   ├── chunk_stats.json        # チャンク統計
│   └── classified.jsonl        # 分類結果（4,166件）
├── output_md/
│   ├── スピリチュアル分類.md    # カテゴリ分類定義
│   ├── イベント/               # イベント系MDファイル（17件）
│   ├── 運営・コンサル/         # 運営系MDファイル（14件）
│   ├── 神社メッセージ/         # 神様/神社ごとMD（28件, 306エントリ）
│   └── カテゴリ別/             # 分類出力（9カテゴリ + その他 + 統合）
├── 謎会事業計画書_v2.md        # 事業計画書（セッションデータ反映済み）
├── 録音データ/                 # 音声ファイル + 文字起こしtxt（5件）
├── *.html                      # ソースHTMLファイル
├── *.json                      # メタデータ
└── .env                        # APIキー
```

## 設計メモ
- チャンク最小50文字、最大2000文字
- MDファイルは見出し区切り、TXTファイルは800文字区切り
- 分類にはClaude Sonnet 4を使用（コスト効率重視）
- バッチ処理: 8チャンク/API呼び出し、キーワードフィルタで非スピリチュアルをスキップ
- --resume オプションで中断再開可能
- 出力形式は「運営・コンサルでのスピリチュアルQA.md」を参考

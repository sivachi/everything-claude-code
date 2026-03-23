#!/usr/bin/env python3
"""
02_classify.py — チャンクをClaude APIで要約＋カテゴリ分類（コスト最適化版）

最適化:
  - バッチ処理: 1回のAPI呼び出しで複数チャンクをまとめて分類
  - キーワード事前フィルタ: 明らかに非スピリチュアルな内容はAPIを叩かない
  - Haikuスクリーニング: 安いモデルで先にスピ/非スピを判定（--use-haiku-filter）
  - resume: 既分類チャンクはスキップ

使用方法:
  python3 scripts/02_classify.py [--batch-size 8] [--resume] [--use-haiku-filter] [--limit 100]
"""

import json
import os
import sys
import time
import re
import argparse
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic パッケージが必要です: pip install anthropic")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"
CHUNKS_FILE = OUTPUT_DIR / "chunks.jsonl"
CLASSIFIED_FILE = OUTPUT_DIR / "classified.jsonl"
CLASSIFICATION_FILE = PROJECT_DIR / "output_md" / "スピリチュアル分類.md"


def load_env():
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

load_env()

# ── キーワード事前フィルタ ──
# これらのキーワードが1つも含まれないチャンクはスピリチュアルでない可能性が高い
SPIRITUAL_KEYWORDS = [
    "霊", "魂", "前世", "来世", "生まれ変わり", "転生", "守護", "指導霊",
    "神", "天使", "精霊", "エネルギー", "波動", "オーラ", "チャクラ",
    "カルマ", "因果", "業", "宇宙", "次元", "覚醒", "目覚め",
    "浄化", "ヒーリング", "瞑想", "祈り", "お経", "供養", "49日",
    "パワーストーン", "水晶", "タロット", "占い", "リーディング",
    "シンクロ", "直感", "テレパシー", "チャネリング", "透視",
    "引き寄せ", "願望", "運気", "開運", "ソウルメイト", "ツインレイ",
    "アトランティス", "ムー", "聖地", "パワースポット", "陰謀",
    "結界", "厄除け", "お守り", "盛り塩", "お香",
    "予知", "予言", "生霊", "念", "気", "修行", "滝行",
    "スピリチュアル", "スピ", "霊感", "霊能", "霊視",
    "亡くなっ", "成仏", "あの世", "あちらの世界",
    "使命", "役目", "課題", "学び",  # 魂の文脈で使われやすい
    "見えない", "感じる", "不思議",  # スピ文脈のキーワード
    "神社", "メッセージ", "導き", "加護", "ご縁",
    "先祖", "仏", "菩薩", "明王",
    "コンサル", "タケチング",  # スピリチュアルコンサルの文脈
]

# 明確に非スピリチュアルな内容のパターン
NON_SPIRITUAL_PATTERNS = [
    r"^おはようございます",
    r"^お疲れ様",
    r"^ありがとうございます\s*$",
    r"^はい\s*$",
    r"議事録",
    r"アジェンダ",
    r"次回の日程",
]
NON_SPIRITUAL_RE = [re.compile(p) for p in NON_SPIRITUAL_PATTERNS]


def keyword_prefilter(text):
    """キーワード事前フィルタ: スピリチュアル関連の可能性があるかチェック"""
    text_lower = text.lower()
    for kw in SPIRITUAL_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def is_obviously_non_spiritual(text):
    """明らかに非スピリチュアル（短い挨拶、事務連絡等）"""
    stripped = text.strip()
    if len(stripped) < 30:
        return True
    for regex in NON_SPIRITUAL_RE:
        if regex.search(stripped):
            return True
    return False


def load_classification():
    return CLASSIFICATION_FILE.read_text(encoding="utf-8")


def build_system_prompt(classification_text):
    """分類用のシステムプロンプト（バッチ対応）"""
    return f"""あなたは日本語のスピリチュアルコンテンツの分類・要約の専門家です。

以下のカテゴリ分類体系に基づいて、与えられたテキストチャンクを分析してください。

{classification_text}

---

複数のチャンクが与えられます。各チャンクに対して、以下のJSON形式で回答してください。
回答は必ずJSON配列として返してください。

[
  {{
    "chunk_index": 0,
    "summary": "チャンクの内容を1〜3文で要約。具体的な情報を残す",
    "category_id": "最も適切なカテゴリ番号（例: 1-2-1, 5-4-1）。スピリチュアルに関係ない場合は 'none'",
    "category_name": "カテゴリ名",
    "topic": "短いトピック名",
    "confidence": "high / medium / low",
    "is_spiritual": true
  }}
]

ルール:
- スピリチュアルな内容でない場合は is_spiritual: false, category_id: "none" とする
- 複数カテゴリにまたがる場合は最も主要なものを選ぶ
- 要約には具体的な数字や固有の表現をできるだけ残す
- JSON配列以外は出力しない。マークダウンのコードブロックも使わない"""


def build_haiku_filter_prompt():
    """Haikuスクリーニング用の軽量プロンプト"""
    return """複数のテキストチャンクが与えられます。各チャンクがスピリチュアル関連の内容を含むかどうかを判定してください。
スピリチュアル関連: 霊、魂、前世、神、エネルギー、波動、占い、浄化、ヒーリング、瞑想、パワースポット等に関する内容。
回答はJSON配列で。[{"chunk_index": 0, "is_spiritual": true}, ...]
JSON配列以外は出力しない。"""


def classify_batch(client, system_prompt, chunks_batch):
    """複数チャンクをまとめて分類"""
    user_content = ""
    for i, chunk in enumerate(chunks_batch):
        user_content += f"--- チャンク {i} ---\n{chunk['text']}\n\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300 * len(chunks_batch),
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_content}
            ],
        )
        result_text = response.content[0].text.strip()
        # JSON配列抽出
        if result_text.startswith("```"):
            lines = result_text.split("```")
            result_text = lines[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        # 配列の開始を見つける
        start = result_text.find("[")
        end = result_text.rfind("]") + 1
        if start >= 0 and end > start:
            result_text = result_text[start:end]
        results = json.loads(result_text)
        return results
    except json.JSONDecodeError as e:
        print(f"\n  JSON解析エラー（バッチ）: {e}")
        print(f"  応答先頭: {result_text[:200]}")
        # バッチ失敗時は個別にフォールバック
        return None
    except Exception as e:
        print(f"\n  API エラー（バッチ）: {e}")
        return None


def classify_single(client, system_prompt_single, chunk_text):
    """1チャンクを個別分類（フォールバック用）"""
    single_prompt = system_prompt_single.replace("複数のチャンクが与えられます。各チャンクに対して、以下のJSON形式で回答してください。\n回答は必ずJSON配列として返してください。", "チャンクに対して、以下のJSON形式で回答してください。")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=single_prompt,
            messages=[
                {"role": "user", "content": f"以下のテキストチャンクを分類・要約してください:\n\n{chunk_text}"}
            ],
        )
        result_text = response.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        # 配列か単体か
        parsed = json.loads(result_text)
        if isinstance(parsed, list):
            return parsed[0] if parsed else None
        return parsed
    except Exception:
        return {
            "summary": "",
            "category_id": "error",
            "category_name": "解析エラー",
            "topic": "",
            "confidence": "low",
            "is_spiritual": False,
        }


def haiku_screen(client, chunks_batch):
    """Haikuで安くスピ/非スピをスクリーニング"""
    user_content = ""
    for i, chunk in enumerate(chunks_batch):
        # Haikuには先頭300文字だけ送る（コスト削減）
        text_preview = chunk["text"][:300]
        user_content += f"--- チャンク {i} ---\n{text_preview}\n\n"

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50 * len(chunks_batch),
            system=build_haiku_filter_prompt(),
            messages=[
                {"role": "user", "content": user_content}
            ],
        )
        result_text = response.content[0].text.strip()
        start = result_text.find("[")
        end = result_text.rfind("]") + 1
        if start >= 0 and end > start:
            result_text = result_text[start:end]
        results = json.loads(result_text)
        return {r["chunk_index"]: r["is_spiritual"] for r in results}
    except Exception as e:
        print(f"\n  Haikuスクリーニングエラー: {e}")
        # エラー時は全てスピリチュアルとして扱う（安全側）
        return {i: True for i in range(len(chunks_batch))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=8,
                        help="1回のAPI呼び出しで処理するチャンク数 (default: 8)")
    parser.add_argument("--resume", action="store_true",
                        help="前回の続きから再開")
    parser.add_argument("--limit", type=int, default=0,
                        help="処理するチャンク数の上限（0=全件）")
    parser.add_argument("--use-haiku-filter", action="store_true",
                        help="Haikuで事前スクリーニングしてコスト削減")
    parser.add_argument("--dry-run", action="store_true",
                        help="APIを叩かずにフィルタ結果だけ確認")
    args = parser.parse_args()

    if not CHUNKS_FILE.exists():
        print(f"エラー: {CHUNKS_FILE} が見つかりません。先に 01_chunk.py を実行してください。")
        sys.exit(1)

    if not CLASSIFICATION_FILE.exists():
        print(f"エラー: {CLASSIFICATION_FILE} が見つかりません。")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        print("エラー: ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key) if not args.dry_run else None

    # チャンク読み込み
    chunks = []
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    print(f"全チャンク数: {len(chunks)}")

    # 分類テキスト読み込み
    classification_text = load_classification()
    system_prompt = build_system_prompt(classification_text)

    # 既存の分類結果を読み込み（resume用）
    done_ids = set()
    if args.resume and CLASSIFIED_FILE.exists():
        with open(CLASSIFIED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    done_ids.add(record["chunk_id"])
                except json.JSONDecodeError:
                    continue
        print(f"既存の分類結果: {len(done_ids)} 件（スキップ）")

    # 未処理チャンクを取得
    pending = [c for c in chunks if c["chunk_id"] not in done_ids]
    if args.limit > 0:
        pending = pending[:args.limit]

    # ── ステップ1: キーワード事前フィルタ ──
    spiritual_candidates = []
    non_spiritual_by_keyword = []
    for chunk in pending:
        if is_obviously_non_spiritual(chunk["text"]):
            non_spiritual_by_keyword.append(chunk)
        elif keyword_prefilter(chunk["text"]):
            spiritual_candidates.append(chunk)
        else:
            non_spiritual_by_keyword.append(chunk)

    print(f"\nキーワードフィルタ結果:")
    print(f"  スピリチュアル候補: {len(spiritual_candidates)} チャンク（API分類対象）")
    print(f"  非スピリチュアル（スキップ）: {len(non_spiritual_by_keyword)} チャンク")

    # 非スピリチュアル判定されたものを即座に書き込み
    if not args.dry_run:
        write_mode = "a" if args.resume and CLASSIFIED_FILE.exists() else "w"
        with open(CLASSIFIED_FILE, write_mode, encoding="utf-8") as f:
            for chunk in non_spiritual_by_keyword:
                record = {
                    "chunk_id": chunk["chunk_id"],
                    "source_file": chunk["source_file"],
                    "source_type": chunk["source_type"],
                    "heading": chunk["heading"],
                    "text": chunk["text"],
                    "char_count": chunk["char_count"],
                    "summary": "",
                    "category_id": "none",
                    "category_name": "非スピリチュアル",
                    "topic": "",
                    "confidence": "high",
                    "is_spiritual": False,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if args.dry_run:
        print("\n[dry-run] APIは叩きません。")
        # コスト見積もり
        total_chars = sum(c["char_count"] for c in spiritual_candidates)
        est_batches = (len(spiritual_candidates) + args.batch_size - 1) // args.batch_size
        print(f"  API分類対象: {len(spiritual_candidates)} チャンク")
        print(f"  合計文字数: {total_chars:,} 文字")
        print(f"  推定バッチ数: {est_batches} 回（バッチサイズ {args.batch_size}）")
        print(f"  推定入力トークン/バッチ: ~{(len(classification_text) + total_chars // est_batches) * 2 // 3:,}")
        return

    # ── ステップ2: Haikuスクリーニング（オプション） ──
    if args.use_haiku_filter and spiritual_candidates:
        print(f"\nHaikuスクリーニング実行中...")
        haiku_batch_size = 20  # Haikuは安いので大きめバッチ
        still_spiritual = []
        haiku_non_spiritual = []

        for i in range(0, len(spiritual_candidates), haiku_batch_size):
            batch = spiritual_candidates[i:i + haiku_batch_size]
            screening = haiku_screen(client, batch)
            for j, chunk in enumerate(batch):
                if screening.get(j, True):
                    still_spiritual.append(chunk)
                else:
                    haiku_non_spiritual.append(chunk)
            time.sleep(0.5)

        print(f"  Haiku判定 スピリチュアル: {len(still_spiritual)}")
        print(f"  Haiku判定 非スピリチュアル: {len(haiku_non_spiritual)}")

        # Haikuで非スピ判定されたものを書き込み
        with open(CLASSIFIED_FILE, "a", encoding="utf-8") as f:
            for chunk in haiku_non_spiritual:
                record = {
                    "chunk_id": chunk["chunk_id"],
                    "source_file": chunk["source_file"],
                    "source_type": chunk["source_type"],
                    "heading": chunk["heading"],
                    "text": chunk["text"],
                    "char_count": chunk["char_count"],
                    "summary": "",
                    "category_id": "none",
                    "category_name": "非スピリチュアル（Haiku判定）",
                    "topic": "",
                    "confidence": "medium",
                    "is_spiritual": False,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        spiritual_candidates = still_spiritual

    # ── ステップ3: Sonnetバッチ分類 ──
    print(f"\nSonnetバッチ分類: {len(spiritual_candidates)} チャンク（バッチサイズ {args.batch_size}）")
    total_batches = (len(spiritual_candidates) + args.batch_size - 1) // args.batch_size
    print(f"推定API呼び出し回数: {total_batches}")

    processed = 0
    errors = 0

    for batch_idx in range(0, len(spiritual_candidates), args.batch_size):
        batch = spiritual_candidates[batch_idx:batch_idx + args.batch_size]
        batch_num = batch_idx // args.batch_size + 1
        print(f"  バッチ {batch_num}/{total_batches} ({len(batch)}チャンク)...", end="", flush=True)

        results = classify_batch(client, system_prompt, batch)

        if results is None:
            # バッチ失敗 → 個別にフォールバック
            print(" バッチ失敗、個別処理中...", end="", flush=True)
            with open(CLASSIFIED_FILE, "a", encoding="utf-8") as f:
                for chunk in batch:
                    result = classify_single(client, system_prompt, chunk["text"])
                    if result:
                        record = {
                            "chunk_id": chunk["chunk_id"],
                            "source_file": chunk["source_file"],
                            "source_type": chunk["source_type"],
                            "heading": chunk["heading"],
                            "text": chunk["text"],
                            "char_count": chunk["char_count"],
                            **result,
                        }
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        processed += 1
                    else:
                        errors += 1
                    time.sleep(0.5)
            print(" 完了")
        else:
            # バッチ成功
            with open(CLASSIFIED_FILE, "a", encoding="utf-8") as f:
                for result in results:
                    idx = result.get("chunk_index", 0)
                    if idx < len(batch):
                        chunk = batch[idx]
                        record = {
                            "chunk_id": chunk["chunk_id"],
                            "source_file": chunk["source_file"],
                            "source_type": chunk["source_type"],
                            "heading": chunk["heading"],
                            "text": chunk["text"],
                            "char_count": chunk["char_count"],
                            "summary": result.get("summary", ""),
                            "category_id": result.get("category_id", "error"),
                            "category_name": result.get("category_name", ""),
                            "topic": result.get("topic", ""),
                            "confidence": result.get("confidence", "low"),
                            "is_spiritual": result.get("is_spiritual", False),
                        }
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        processed += 1

            cats = [r.get("category_id", "?") for r in results]
            print(f" → {', '.join(cats)}")

        # レート制限対策
        time.sleep(1)

    # 統計
    print(f"\n完了:")
    print(f"  キーワードフィルタ除外: {len(non_spiritual_by_keyword)} チャンク")
    print(f"  API分類: {processed} チャンク")
    print(f"  エラー: {errors} チャンク")
    print(f"  合計API呼び出し: ~{total_batches} 回（バッチ処理）")

    # classified.jsonl の統計
    if CLASSIFIED_FILE.exists():
        all_records = []
        with open(CLASSIFIED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    all_records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        spiritual_count = sum(1 for r in all_records if r.get("is_spiritual"))
        print(f"\n分類済み合計: {len(all_records)} チャンク")
        print(f"  スピリチュアル: {spiritual_count}")
        print(f"  非スピリチュアル: {len(all_records) - spiritual_count}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Project GEN - 全データ ICAI 在り方抽出スクリプト（コスト最適化版）
- 258ファイル全件処理
- haiku モデルで抽出（opus比 1/10コスト）
- 3ファイルをバッチ化して API 呼び出しを削減
- 既存の22ファイル中間JSONを再利用
- チェックポイント保存（中断・再開可能）
"""

import json, os, re, time, datetime, anthropic
from pathlib import Path
from bs4 import BeautifulSoup
from tqdm import tqdm

# ── パス設定 ──────────────────────────────────────
BASE_DIR    = Path("/Users/tadaakikurata/works/ai_takeo_local")
DATA_DIR    = Path("/Users/tadaakikurata/works/ai_takeo/AI竹尾プロジェクト(人格コピー)/Sources")
OUTPUT_DIR  = BASE_DIR / "output"
ARIKATA_MD  = BASE_DIR / "玄_在り方.md"
CHECKPOINT  = OUTPUT_DIR / "checkpoint_full.json"
INTER_OLD   = OUTPUT_DIR / "在り方_中間抽出.json"       # 既存22ファイル分
INTER_FULL  = OUTPUT_DIR / "在り方_中間抽出_full.json"  # 全件
REPORT_FILE = OUTPUT_DIR / "在り方_比較レポート_full.md"

BATCH_SIZE  = 3    # 1回のAPI呼び出しに含めるファイル数
MAX_CHARS   = 8000 # 1ファイルあたりの最大文字数（トークン節約）

# ── APIキー読み込み ───────────────────────────────
with open(BASE_DIR / ".env") as f:
    for line in f:
        if line.startswith("ANTHROPIC_API_KEY="):
            api_key = line.strip().split("=", 1)[1].strip()
            os.environ["ANTHROPIC_API_KEY"] = api_key
            break

client = anthropic.Anthropic(api_key=api_key)

# ── ユーティリティ ────────────────────────────────
def extract_text(html_path: Path) -> str:
    """HTMLからテキスト抽出・フィラー除去・文字数制限"""
    try:
        for enc in ["utf-8", "shift_jis", "cp932"]:
            try:
                soup = BeautifulSoup(html_path.read_text(encoding=enc), "html.parser")
                break
            except Exception:
                continue
        else:
            return ""

        text = soup.get_text(separator="\n")
        # フィラー除去
        text = re.sub(r"(えーっと|あのー?|そのー?|まあ|なんか){2,}", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:MAX_CHARS]
    except Exception as e:
        return ""

def parse_json_safe(text: str) -> dict:
    """不完全なJSONも可能な限りパース"""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        # 最後の完全オブジェクトまでを切り取り
        for end in ["]}}", "]}", "}"]:
            idx = text.rfind(end)
            if idx > 0:
                try:
                    return json.loads(text[:idx + len(end)])
                except Exception:
                    pass
        return {}

def get_already_processed(checkpoint_data: dict) -> set:
    """チェックポイントから処理済みファイル名を取得"""
    return set(checkpoint_data.get("processed_files", []))


# ── バッチ抽出 ────────────────────────────────────
EXTRACT_PROMPT = """あなたはAI人格分析の専門家です。
以下は「GEN」という人物のコーチング/コンサルセッション書き起こしです（複数ファイル）。

{transcripts}

---
各セッションから「GENの在り方（価値観・信念・行動パターン・診断方法）」を抽出してください。

【出力形式（JSON）】
{{
  "results": [
    {{
      "file": "ファイル名",
      "principles": [
        {{
          "principle": "原則の内容（1文で簡潔に）",
          "category": "believes/values/rejects/diagnoses_via/communicates_using のどれか",
          "evidence": "根拠となる発言の要約（30字以内）"
        }}
      ]
    }}
  ]
}}

・1ファイルあたり3〜6個の原則を抽出
・GENが「言っていること」ではなく「在り方として体現していること」を抽出
・JSONのみ出力"""

def extract_batch(file_batch: list[tuple[str, str]]) -> list[dict]:
    """3ファイルをまとめて1回のhaiku呼び出しで抽出"""
    transcripts = ""
    for fname, text in file_batch:
        transcripts += f"\n\n=== {fname} ===\n{text}\n"

    prompt = EXTRACT_PROMPT.format(transcripts=transcripts)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        parsed = parse_json_safe(response.content[0].text)
        results = parsed.get("results", [])

        principles = []
        for r in results:
            for p in r.get("principles", []):
                p["source_file"] = r.get("file", "")
                principles.append(p)
        return principles
    except Exception as e:
        print(f"  [ERROR] バッチ抽出失敗: {e}")
        return []


# ── 集約（haiku バッチ）────────────────────────────
AGG_PROMPT = """以下の{n}個の原則を整理してください。

---
{principles_text}
---

重複・類似をまとめ、5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）に分類してください。

{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 件数推定, "confidence": "high/medium/low"}}]}}

JSONのみ出力。"""

def aggregate_in_batches(all_principles: list[dict]) -> list[dict]:
    """haiku で50件ずつ集約し、最終集約はsonnetで"""
    print(f"\n[STEP 3] 集約中 ({len(all_principles)}原則)...")

    # --- Phase 1: haiku で 50件ずつ集約 ---
    BATCH = 50
    phase1_results = []
    chunks = [all_principles[i:i+BATCH] for i in range(0, len(all_principles), BATCH)]

    for ci, chunk in enumerate(chunks):
        text = "\n".join(
            f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')}"
            for i, p in enumerate(chunk)
        )
        prompt = AGG_PROMPT.format(n=len(chunk), principles_text=text)
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = parse_json_safe(resp.content[0].text)
            batch_agg = parsed.get("aggregated", [])
            phase1_results.extend(batch_agg)
            print(f"  バッチ {ci+1}/{len(chunks)}: {len(chunk)}→{len(batch_agg)}件")
        except Exception as e:
            print(f"  [ERROR] バッチ{ci+1}集約失敗: {e}")
        time.sleep(0.5)

    # --- Phase 2: sonnet で最終集約 ---
    print(f"  最終集約中 ({len(phase1_results)}→目標30件前後, using sonnet)...")
    final_text = "\n".join(
        f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [freq:{p.get('frequency',1)}]"
        for i, p in enumerate(phase1_results)
    )
    final_prompt = f"""以下の原則を最終整理してください（目標：25〜35件）。

---
{final_text}
---

重複を完全にまとめ、頻度順・カテゴリ別に整理してください。

{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 件数推定, "confidence": "high/medium/low"}}]}}

JSONのみ出力。"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=6000,
            messages=[{"role": "user", "content": final_prompt}]
        )
        parsed = parse_json_safe(resp.content[0].text)
        final = parsed.get("aggregated", [])
        print(f"  → 最終: {len(final)}件")
        return final
    except Exception as e:
        print(f"  [ERROR] 最終集約失敗: {e}")
        return phase1_results


# ── 比較（sonnet）────────────────────────────────
def compare_with_arikata(aggregated: list[dict], arikata_text: str) -> str:
    agg_json = json.dumps(aggregated, ensure_ascii=False, indent=2)
    prompt = f"""以下2つを比較してください。

【A】Claudeが258セッションから独立抽出した原則:
{agg_json}

【B】既存「玄_在り方.md」（v2.0）:
{arikata_text}

3分類で比較レポートを作成してください：

## MATCH（一致・補強）
| 原則 | B（既存）との対応 | 確信度 |
|---|---|---|

## NEW（新規追加候補）
| 原則 | カテゴリ | 頻度 | 追加推奨度 |
|---|---|---|---|

## CONFLICT（要検証）
| Aの抽出 | Bの記述 | 差異のポイント |
|---|---|---|

## 総評
- 全データ分析で見えた新たな発見
- v2.0への追記推奨事項
- 特に注目すべきパターン

Markdownで出力してください。"""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()


# ── メイン処理 ────────────────────────────────────
def main():
    print("=" * 60)
    print("  Project GEN - 全データ ICAI 抽出（コスト最適化版）")
    print("=" * 60)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # --- 既存中間結果の読み込み ---
    existing_principles = []
    already_processed = set()
    if INTER_OLD.exists():
        existing_principles = json.loads(INTER_OLD.read_text(encoding="utf-8"))
        print(f"[INFO] 既存22ファイル分: {len(existing_principles)}原則を再利用")

    # --- チェックポイント読み込み ---
    checkpoint = {}
    if CHECKPOINT.exists():
        checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        already_processed = get_already_processed(checkpoint)
        checkpoint_principles = checkpoint.get("principles", [])
        print(f"[INFO] チェックポイント: {len(already_processed)}ファイル処理済み, {len(checkpoint_principles)}原則")
    else:
        checkpoint_principles = []

    # --- 全HTMLファイル取得 ---
    all_files = sorted(DATA_DIR.glob("*.html"))
    print(f"[INFO] 総ファイル数: {len(all_files)}")

    # --- 未処理ファイルを抽出 ---
    # 既存22ファイルのファイル名も除外
    processed_fnames = already_processed.copy()
    if INTER_OLD.exists():
        # 既存中間JSONのsource_fileから処理済みファイルを取得
        for p in existing_principles:
            if "source_file" in p:
                processed_fnames.add(p["source_file"])

    remaining = [f for f in all_files if f.name not in processed_fnames]
    print(f"[INFO] 未処理: {len(remaining)}ファイル（{len(all_files)-len(remaining)}件スキップ）")
    print(f"[INFO] バッチサイズ: {BATCH_SIZE}ファイル/呼び出し")
    print(f"[INFO] 予定API呼び出し数: {len(remaining)//BATCH_SIZE + 1}回（抽出）\n")

    # --- バッチ処理 ---
    new_principles = list(checkpoint_principles)  # チェックポイントからの継続
    batches = [remaining[i:i+BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]

    with tqdm(total=len(batches), desc="抽出中") as pbar:
        for bi, batch_files in enumerate(batches):
            # テキスト抽出
            file_texts = []
            for fpath in batch_files:
                text = extract_text(fpath)
                if text.strip():
                    file_texts.append((fpath.name, text))

            if not file_texts:
                pbar.update(1)
                continue

            # haiku で原則抽出
            extracted = extract_batch(file_texts)
            new_principles.extend(extracted)

            # チェックポイント保存（10バッチごと）
            processed_fnames.update(f.name for f in batch_files)
            if (bi + 1) % 10 == 0 or bi == len(batches) - 1:
                checkpoint_data = {
                    "processed_files": list(processed_fnames),
                    "principles": new_principles,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                CHECKPOINT.write_text(json.dumps(checkpoint_data, ensure_ascii=False, indent=2), encoding="utf-8")
                tqdm.write(f"  [チェックポイント保存] {len(new_principles)}原則")

            pbar.update(1)
            time.sleep(0.3)  # レート制限対策

    # --- 全原則をマージ ---
    all_principles = existing_principles + new_principles
    print(f"\n[INFO] 全原則数（マージ後）: {len(all_principles)}")
    INTER_FULL.write_text(json.dumps(all_principles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] 全中間結果を保存: {INTER_FULL}")

    # --- 集約 ---
    aggregated = aggregate_in_batches(all_principles)

    # --- 比較 ---
    print("\n[STEP 4] 在り方.md と比較中...")
    arikata_text = ARIKATA_MD.read_text(encoding="utf-8")
    comparison_md = compare_with_arikata(aggregated, arikata_text)

    # --- レポート出力 ---
    report = f"""# 在り方 比較レポート（全データ版）

## 概要
- 実行日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
- 分析ファイル数: {len(all_files)} / {len(all_files)}（全件）
- 抽出原則数（生）: {len(all_principles)}
- 集約後原則数: {len(aggregated)}
- 比較対象: 玄_在り方.md（v2.0）

---

{comparison_md}

---

## 集約原則の全リスト（258セッション独立抽出）

| # | 原則 | カテゴリ | 頻度 | 確信度 |
|---|---|---|---|---|
"""
    for i, p in enumerate(aggregated, 1):
        report += f"| {i} | {p.get('principle','')} | {p.get('category','')} | {p.get('frequency','-')} | {p.get('confidence','-')} |\n"

    REPORT_FILE.write_text(report, encoding="utf-8")

    # チェックポイントを削除（完了）
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()

    print(f"\n{'='*60}")
    print(f"  完了！")
    print(f"  → {REPORT_FILE}")
    print(f"  集約原則数: {len(aggregated)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Project GEN - Phase2のみ実行（Phase1b: 348件 → 最終25〜35件）
- Phase2a: sonnet 3バッチ（116件/バッチ）→ ~60件
- Phase2b: sonnet 最終（~60件 → 25〜35件）
- 比較レポート生成
"""

import json, os, re, time, datetime, anthropic
from pathlib import Path

BASE_DIR    = Path("/Users/tadaakikurata/works/ai_takeo_local")
OUTPUT_DIR  = BASE_DIR / "output"
PHASE1B_FILE= OUTPUT_DIR / "在り方_phase1b_v3.json"
ARIKATA_MD  = BASE_DIR / "玄_在り方.md"
REPORT_FILE = OUTPUT_DIR / "在り方_比較レポート_v3.md"
AGG_FILE    = OUTPUT_DIR / "在り方_集約_v3.json"

with open(BASE_DIR / ".env") as f:
    for line in f:
        if line.startswith("ANTHROPIC_API_KEY="):
            api_key = line.strip().split("=", 1)[1].strip()
            os.environ["ANTHROPIC_API_KEY"] = api_key
            break

client = anthropic.Anthropic(api_key=api_key)


def parse_json_safe(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        for end in ["]}}", "]}", "}"]:
            idx = text.rfind(end)
            if idx > 0:
                try:
                    return json.loads(text[:idx + len(end)])
                except Exception:
                    pass
    return {}


def call_api_with_retry(model, max_tokens, messages, max_retries=5):
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, messages=messages
            )
            return resp.content[0].text
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            status = getattr(e, 'status_code', 529)
            if status == 529:
                wait = 2 ** attempt * 10
                print(f"    [529] {wait}秒待機...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"    [ERROR] {e}")
            time.sleep(5)
    raise RuntimeError("リトライ上限")


AGG_PROMPT = """以下の{n}個の原則を統合・整理してください。

---
{text}
---

ルール：
- 同じ内容・類似した内容を1つにまとめる（積極的に統合）
- 5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）に分類
- frequencyは入力の出現頻度の合計
- 目標：{target}件前後に圧縮

JSONのみ出力:
{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 数値, "confidence": "high/medium/low"}}]}}"""


def aggregate_batch(items, target_count, label):
    """sonnet でバッチ集約"""
    BATCH = 120
    chunks = [items[i:i+BATCH] for i in range(0, len(items), BATCH)]
    total = len(chunks)
    results = []

    print(f"  {label}: {len(items)}件 → {total}バッチ（最大{BATCH}件/バッチ、目標{target_count}件/バッチ）")

    for ci, chunk in enumerate(chunks):
        text = "\n".join(
            f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [freq:{p.get('frequency',1)}]"
            for i, p in enumerate(chunk)
        )
        prompt = AGG_PROMPT.format(n=len(chunk), text=text, target=max(5, len(chunk)//5))

        try:
            raw = call_api_with_retry(
                model="claude-sonnet-4-5",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = parse_json_safe(raw)
            batch_agg = parsed.get("aggregated", [])
            if len(batch_agg) == 0:
                print(f"    ⚠️ 0件返答。RAWの最初100文字: {raw[:100]}")
            results.extend(batch_agg)
            print(f"  [{ci+1:02d}/{total}] {len(chunk)}件 → {len(batch_agg)}件  (累計: {len(results)}件)")
        except Exception as e:
            print(f"  [{ci+1:02d}/{total}] ❌ {e}")

        time.sleep(3)

    return results


def final_aggregate(items):
    """sonnet 最終集約 → 25〜35件"""
    print(f"\n  最終集約（sonnet）: {len(items)}件 → 目標25〜35件")

    text = "\n".join(
        f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [freq:{p.get('frequency',1)}]"
        for i, p in enumerate(items)
    )

    prompt = f"""以下の原則を最終整理してください（目標：25〜35件）。

---
{text}
---

ルール：
- 重複・類似を完全に統合
- 頻度は入力のfrequency合計
- 頻度が高い順に並べる
- 5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）で分類

JSONのみ出力:
{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 数値, "confidence": "high/medium/low"}}]}}"""

    raw = call_api_with_retry(
        model="claude-sonnet-4-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )
    parsed = parse_json_safe(raw)
    final = parsed.get("aggregated", [])
    print(f"  最終集約完了: {len(final)}件")
    if len(final) == 0:
        print(f"  ⚠️ RAWの最初200文字: {raw[:200]}")
    return final


def generate_comparison(aggregated, arikata_text):
    print("\n[STEP 3] v3.0との比較レポート生成中...")
    agg_json = json.dumps(aggregated, ensure_ascii=False, indent=2)

    # v3.0のセクションリストだけ渡す（文字数削減）
    sections = [l for l in arikata_text.split('\n') if l.startswith('### ')]
    arikata_summary = "v3.0セクション一覧:\n" + "\n".join(sections)

    prompt = f"""以下2つを比較してください。

【A】258セッション全件から抽出・再集約した原則:
{agg_json}

【B】玄_在り方.md（v3.0）のセクション構成:
{arikata_summary}

3分類で比較レポートを作成：

## MATCH（v3.0に既に収録済み）
| 原則（A） | v3.0対応セクション | 確信度 |
|---|---|---|

## NEW（v3.0に未収録の新規候補）
| 原則（A） | カテゴリ | 頻度 | 追加推奨度 | 理由 |
|---|---|---|---|---|

## CONFLICT（要検証）
| Aの抽出 | v3.0の記述 | 差異のポイント |
|---|---|---|

## 総評
v3.0への追記推奨事項と優先順位を記述してください。

Markdownで出力。"""

    raw = call_api_with_retry(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    return raw.strip()


def main():
    print("=" * 60)
    print("  Project GEN - Phase2のみ実行")
    print("=" * 60)

    # Phase1b データ読み込み
    phase1b = json.loads(PHASE1B_FILE.read_text(encoding="utf-8"))
    print(f"\n[INFO] Phase1bデータ読み込み: {len(phase1b)}件")

    # Phase2a: 120件/バッチ で圧縮
    print("\n[STEP 2a] Phase2a（sonnet, 120件/バッチ）...")
    phase2a = aggregate_batch(phase1b, target_count=20, label="Phase2a")
    print(f"  → {len(phase2a)}件")

    if len(phase2a) == 0:
        print("❌ Phase2aが0件。終了します。")
        return

    # Phase2b: 最終集約
    print("\n[STEP 2b] Phase2b 最終集約...")
    final = final_aggregate(phase2a)

    if len(final) == 0:
        print("⚠️ Phase2bが0件。Phase2aの結果をそのまま保存します。")
        final = phase2a

    # 保存
    AGG_FILE.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  集約結果を保存: {AGG_FILE}（{len(final)}件）")

    # 比較レポート
    arikata_text = ARIKATA_MD.read_text(encoding="utf-8")
    comparison_md = generate_comparison(final, arikata_text)

    # レポート
    report = f"""# 在り方 比較レポート（再集約Fix版）

## 概要
- 実行日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
- 生データ: 1,346件 → Phase1b: {len(phase1b)}件 → Phase2a: {len(phase2a)}件 → 最終: {len(final)}件
- 比較対象: 玄_在り方.md（v3.0 / 40セクション）

---

{comparison_md}

---

## 集約原則の全リスト（再集約Fix版）

| # | 原則 | カテゴリ | 頻度 | 確信度 |
|---|---|---|---|---|
"""
    for i, p in enumerate(final, 1):
        report += f"| {i} | {p.get('principle','')} | {p.get('category','')} | {p.get('frequency','-')} | {p.get('confidence','-')} |\n"

    REPORT_FILE.write_text(report, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  ✅ 完了！")
    print(f"  → レポート: {REPORT_FILE}")
    print(f"  最終原則数: {len(final)}件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

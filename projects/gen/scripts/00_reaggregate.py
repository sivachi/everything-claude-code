#!/usr/bin/env python3
"""
Project GEN - 再集約スクリプト
- 既存の在り方_中間抽出_full.json（1,346件）を再集約
- 529エラー対策: 指数バックオフ＋リトライ（最大5回）
- Phase1: haiku 40件/バッチ（前回50→40に削減）
- Phase2: sonnet 最終集約
- 玄_在り方.md v3.0 と比較レポート生成
"""

import json, os, re, time, datetime, anthropic
from pathlib import Path

BASE_DIR    = Path("/Users/tadaakikurata/works/ai_takeo_local")
OUTPUT_DIR  = BASE_DIR / "output"
INTER_FULL  = OUTPUT_DIR / "在り方_中間抽出_full.json"
ARIKATA_MD  = BASE_DIR / "玄_在り方.md"
REPORT_FILE = OUTPUT_DIR / "在り方_比較レポート_v3.md"
AGG_FILE    = OUTPUT_DIR / "在り方_集約_v3.json"
PHASE1_FILE = OUTPUT_DIR / "在り方_phase1_v3.json"   # Phase1中間保存
PHASE1B_FILE= OUTPUT_DIR / "在り方_phase1b_v3.json"  # Phase1b中間保存

# APIキー読み込み
with open(BASE_DIR / ".env") as f:
    for line in f:
        if line.startswith("ANTHROPIC_API_KEY="):
            api_key = line.strip().split("=", 1)[1].strip()
            os.environ["ANTHROPIC_API_KEY"] = api_key
            break

client = anthropic.Anthropic(api_key=api_key)


# ── ユーティリティ ────────────────────────────────────
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


def call_api_with_retry(model: str, max_tokens: int, messages: list,
                        max_retries: int = 5) -> str:
    """529エラー対応の指数バックオフ付きAPI呼び出し"""
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages
            )
            return resp.content[0].text
        except anthropic.RateLimitError as e:
            wait = 2 ** attempt * 10  # 10s, 20s, 40s, 80s, 160s
            print(f"    [529 過負荷] attempt {attempt+1}/{max_retries} → {wait}秒待機...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                wait = 2 ** attempt * 10
                print(f"    [529 過負荷] attempt {attempt+1}/{max_retries} → {wait}秒待機...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"    [ERROR] {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise
    raise RuntimeError(f"API呼び出し失敗（{max_retries}回リトライ後）")


# ── Phase 1: haiku で 40件ずつ集約 ─────────────────────
AGG_PROMPT = """以下の{n}個の原則を整理してください。

---
{principles_text}
---

重複・類似をまとめ、5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）に分類してください。

{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 件数推定, "confidence": "high/medium/low"}}]}}

JSONのみ出力。"""


def run_haiku_aggregation(principles: list[dict], batch_size: int, label: str) -> list[dict]:
    """haiku で batch_size 件ずつ集約する汎用関数"""
    chunks = [principles[i:i+batch_size] for i in range(0, len(principles), batch_size)]
    total = len(chunks)
    results = []

    print(f"  {label}: {len(principles)}件 → {total}バッチ（{batch_size}件/バッチ）")

    for ci, chunk in enumerate(chunks):
        text = "\n".join(
            f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [freq:{p.get('frequency',1)}]"
            for i, p in enumerate(chunk)
        )
        prompt = AGG_PROMPT.format(n=len(chunk), principles_text=text)

        try:
            raw = call_api_with_retry(
                model="claude-haiku-4-5",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = parse_json_safe(raw)
            batch_agg = parsed.get("aggregated", [])
            results.extend(batch_agg)
            print(f"  [{ci+1:02d}/{total}] {len(chunk)}件 → {len(batch_agg)}件  (累計: {len(results)}件)")
        except Exception as e:
            print(f"  [{ci+1:02d}/{total}] ❌ 失敗（スキップ）: {e}")

        time.sleep(2)  # バッチ間待機（529対策）

    print(f"  {label} 完了: {len(principles)}件 → {len(results)}件")
    return results


def phase1_aggregate(all_principles: list[dict]) -> list[dict]:
    """Phase1: haiku 40件/バッチで1346→~1000件"""
    # 既存のPhase1結果があればスキップ
    if PHASE1_FILE.exists():
        data = json.loads(PHASE1_FILE.read_text(encoding="utf-8"))
        print(f"  [スキップ] Phase1結果を再利用: {len(data)}件")
        return data

    results = run_haiku_aggregation(all_principles, batch_size=40, label="Phase1")

    # Phase1結果を保存（失敗時の再開用）
    PHASE1_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Phase1結果を保存: {PHASE1_FILE}")
    return results


def phase1b_aggregate(phase1_results: list[dict]) -> list[dict]:
    """Phase1b: haiku 80件/バッチで~1000→~150件に2次圧縮"""
    # 既存のPhase1b結果があればスキップ
    if PHASE1B_FILE.exists():
        data = json.loads(PHASE1B_FILE.read_text(encoding="utf-8"))
        print(f"  [スキップ] Phase1b結果を再利用: {len(data)}件")
        return data

    results = run_haiku_aggregation(phase1_results, batch_size=80, label="Phase1b")

    PHASE1B_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Phase1b結果を保存: {PHASE1B_FILE}")
    return results


# ── Phase 2: sonnet で最終集約 ─────────────────────────
def phase2_aggregate(phase1_results: list[dict]) -> list[dict]:
    print(f"\n  Phase2: {len(phase1_results)}件 → 目標25〜35件（sonnet）")

    final_text = "\n".join(
        f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [freq:{p.get('frequency',1)}]"
        for i, p in enumerate(phase1_results)
    )

    prompt = f"""以下の原則を最終整理してください（目標：25〜35件）。

---
{final_text}
---

重複を完全にまとめ、頻度順・カテゴリ別に整理してください。
頻度は元データの出現回数の合計を推定してください。

{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 件数推定, "confidence": "high/medium/low"}}]}}

JSONのみ出力。"""

    raw = call_api_with_retry(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    parsed = parse_json_safe(raw)
    final = parsed.get("aggregated", [])
    print(f"  Phase2 完了: → {len(final)}件")
    return final


# ── 比較レポート生成（sonnet）────────────────────────────
def generate_comparison(aggregated: list[dict], arikata_text: str) -> str:
    print("\n[STEP 3] v3.0との比較レポート生成中（sonnet）...")

    agg_json = json.dumps(aggregated, ensure_ascii=False, indent=2)
    prompt = f"""以下2つを比較してください。

【A】Claudeが258セッションから独立抽出した原則（再集約版）:
{agg_json}

【B】既存「玄_在り方.md」（v3.0）:
{arikata_text}

3分類で比較レポートを作成してください：

## MATCH（一致・補強）
| 原則（A） | B（v3.0）との対応 | 確信度 | 備考 |
|---|---|---|---|

## NEW（v3.0未収録の新規候補）
| 原則（A） | カテゴリ | 頻度 | 追加推奨度 | 理由 |
|---|---|---|---|---|

## CONFLICT（要検証・矛盾点）
| Aの抽出 | Bの記述 | 差異のポイント | 検証方向 |
|---|---|---|---|

## 総評
v3.0との対比で見えた新発見、追記推奨事項、特に注目すべきパターンを記述してください。

Markdownで出力してください。"""

    raw = call_api_with_retry(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    return raw.strip()


# ── メイン ────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Project GEN - 再集約スクリプト（529エラー対策版）")
    print("=" * 60)

    # 1,346件の生データ読み込み
    all_principles = json.loads(INTER_FULL.read_text(encoding="utf-8"))
    print(f"\n[STEP 1] 生データ読み込み: {len(all_principles)}件")

    cats = {}
    for p in all_principles:
        c = p.get('category', '?')
        cats[c] = cats.get(c, 0) + 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}件")

    # Phase 1: haiku 40件/バッチ → ~1000件
    print("\n[STEP 2] Phase1集約（haiku, 40件/バッチ）...")
    phase1 = phase1_aggregate(all_principles)

    # Phase 1b: haiku 80件/バッチ → ~150件（sonnetへ渡せるサイズまで圧縮）
    print("\n[STEP 2b] Phase1b集約（haiku, 80件/バッチ）...")
    phase1b = phase1b_aggregate(phase1)

    # Phase 2: sonnet最終集約（~150件 → 25〜35件）
    phase2 = phase2_aggregate(phase1b)

    # 集約結果を保存
    AGG_FILE.write_text(json.dumps(phase2, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  集約結果を保存: {AGG_FILE}")

    # Phase1/1b の中間ファイルを削除（完了後クリーンアップ）
    for f in [PHASE1_FILE, PHASE1B_FILE]:
        if f.exists():
            f.unlink()

    # v3.0との比較
    arikata_text = ARIKATA_MD.read_text(encoding="utf-8")
    comparison_md = generate_comparison(phase2, arikata_text)

    # レポート出力
    report = f"""# 在り方 比較レポート（再集約版 v3）

## 概要
- 実行日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
- 入力: 在り方_中間抽出_full.json（{len(all_principles)}件）
- Phase1集約後: {len(phase1)}件
- Phase1b集約後: {len(phase1b)}件
- Phase2最終集約後: {len(phase2)}件
- 比較対象: 玄_在り方.md（v3.0）

---

{comparison_md}

---

## 集約原則の全リスト（再集約版）

| # | 原則 | カテゴリ | 頻度 | 確信度 |
|---|---|---|---|---|
"""
    for i, p in enumerate(phase2, 1):
        report += f"| {i} | {p.get('principle','')} | {p.get('category','')} | {p.get('frequency','-')} | {p.get('confidence','-')} |\n"

    REPORT_FILE.write_text(report, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  ✅ 完了！")
    print(f"  → レポート: {REPORT_FILE}")
    print(f"  → 集約JSON: {AGG_FILE}")
    print(f"  最終原則数: {len(phase2)}件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

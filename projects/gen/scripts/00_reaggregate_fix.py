#!/usr/bin/env python3
"""
Project GEN - 再集約 Fix版
- Phase1保存済みデータ（1,194件）を入力
- sonnet 100件/バッチ で ~150件に圧縮（Phase1b）
- sonnet 最終集約で 25〜35件（Phase2）
- 玄_在り方.md v3.0 と比較レポート生成
"""

import json, os, re, time, datetime, anthropic
from pathlib import Path

BASE_DIR    = Path("/Users/tadaakikurata/works/claude-code/projects/gen")
OUTPUT_DIR  = BASE_DIR / "output"
PHASE1_FILE = OUTPUT_DIR / "在り方_phase1_v3.json"   # Phase1の保存済み（1,194件）
ARIKATA_MD  = BASE_DIR / "玄_在り方.md"
REPORT_FILE = OUTPUT_DIR / "在り方_比較レポート_v3.md"
AGG_FILE    = OUTPUT_DIR / "在り方_集約_v3.json"
PHASE1B_FILE= OUTPUT_DIR / "在り方_phase1b_v3.json"
INTER_FULL  = OUTPUT_DIR / "在り方_中間抽出_full.json"

# APIキー読み込み
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


def call_api_with_retry(model: str, max_tokens: int, messages: list,
                        max_retries: int = 5) -> str:
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages
            )
            return resp.content[0].text
        except anthropic.RateLimitError:
            wait = 2 ** attempt * 10
            print(f"    [529] attempt {attempt+1}/{max_retries} → {wait}秒待機...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                wait = 2 ** attempt * 10
                print(f"    [529] attempt {attempt+1}/{max_retries} → {wait}秒待機...")
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


# ── Phase1: haiku 40件/バッチ → ~1200件 ─────────────────
def phase1_haiku(raw_principles: list[dict]) -> list[dict]:
    """Phase1: haiku 40件/バッチ（キャッシュあればスキップ）"""
    if PHASE1_FILE.exists():
        data = json.loads(PHASE1_FILE.read_text(encoding="utf-8"))
        if len(data) > 0:
            print(f"  [スキップ] Phase1既存結果を再利用: {len(data)}件")
            return data

    BATCH = 40
    chunks = [raw_principles[i:i+BATCH] for i in range(0, len(raw_principles), BATCH)]
    total = len(chunks)
    results = []
    print(f"  Phase1（haiku）: {len(raw_principles)}件 → {total}バッチ（{BATCH}件/バッチ）")

    for ci, chunk in enumerate(chunks):
        text = "\n".join(
            f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')}"
            for i, p in enumerate(chunk)
        )
        prompt = HAIKU_AGG_PROMPT.format(n=len(chunk), principles_text=text)
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
            print(f"  [{ci+1:02d}/{total}] ❌ 失敗: {e}")
        time.sleep(2)

    PHASE1_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Phase1 完了: {len(raw_principles)}件 → {len(results)}件  [保存済み]")
    return results


# ── Phase1b: sonnet 100件/バッチ → ~150件 ─────────────
HAIKU_AGG_PROMPT = """以下の{n}個の原則を整理してください。

---
{principles_text}
---

重複・類似をまとめ、5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）に分類してください。

{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 件数推定, "confidence": "high/medium/low"}}]}}

JSONのみ出力。"""


AGG_PROMPT = """以下の{n}個の原則を統合・整理してください。

---
{principles_text}
---

【ルール】
- 同じ内容・類似した内容を1つにまとめる
- 5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）に分類
- frequencyは入力の合計を推定
- 目標：入力の1/5〜1/3に圧縮（重複をしっかり除去する）

出力形式（JSONのみ）:
{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 数値, "confidence": "high/medium/low"}}]}}"""


def phase1b_sonnet(phase1_data: list[dict]) -> list[dict]:
    """sonnet 100件/バッチ で 1194 → ~150件"""

    # キャッシュ確認
    if PHASE1B_FILE.exists():
        data = json.loads(PHASE1B_FILE.read_text(encoding="utf-8"))
        if len(data) > 0:
            print(f"  [スキップ] Phase1b既存結果を再利用: {len(data)}件")
            return data

    BATCH = 100
    chunks = [phase1_data[i:i+BATCH] for i in range(0, len(phase1_data), BATCH)]
    total = len(chunks)
    results = []

    print(f"  Phase1b（sonnet）: {len(phase1_data)}件 → {total}バッチ（{BATCH}件/バッチ）")

    for ci, chunk in enumerate(chunks):
        text = "\n".join(
            f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [出現頻度:{p.get('frequency',1)}]"
            for i, p in enumerate(chunk)
        )
        prompt = AGG_PROMPT.format(n=len(chunk), principles_text=text)

        try:
            raw = call_api_with_retry(
                model="claude-sonnet-4-5",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = parse_json_safe(raw)
            batch_agg = parsed.get("aggregated", [])
            results.extend(batch_agg)
            print(f"  [{ci+1:02d}/{total}] {len(chunk)}件 → {len(batch_agg)}件  (累計: {len(results)}件)")
        except Exception as e:
            print(f"  [{ci+1:02d}/{total}] ❌ 失敗: {e}")

        time.sleep(3)  # sonnet用に少し長めの待機

    PHASE1B_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Phase1b 完了: {len(phase1_data)}件 → {len(results)}件")
    return results


# ── Phase2: sonnet 最終集約 → 25〜35件 ───────────────
def phase2_final(phase1b_data: list[dict]) -> list[dict]:
    print(f"\n  Phase2（sonnet最終）: {len(phase1b_data)}件 → 目標25〜35件")

    final_text = "\n".join(
        f"[{i+1}] ({p.get('category','?')}) {p.get('principle','')} [頻度:{p.get('frequency',1)}]"
        for i, p in enumerate(phase1b_data)
    )

    prompt = f"""以下の原則を最終整理してください（目標：25〜35件）。

---
{final_text}
---

【ルール】
- 重複・類似を完全にまとめる
- 頻度は入力のfrequency合計を使用
- 頻度が高い順に並べる
- 5カテゴリ（believes/values/rejects/diagnoses_via/communicates_using）で整理

出力形式（JSONのみ）:
{{"aggregated": [{{"principle": "...", "category": "...", "frequency": 数値, "confidence": "high/medium/low"}}]}}"""

    raw = call_api_with_retry(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    parsed = parse_json_safe(raw)
    final = parsed.get("aggregated", [])
    print(f"  Phase2 完了: → {len(final)}件")
    return final


# ── 比較レポート ──────────────────────────────────────
def generate_comparison(aggregated: list[dict], arikata_text: str) -> str:
    print("\n[STEP 3] v3.0との比較レポート生成中（sonnet）...")
    agg_json = json.dumps(aggregated, ensure_ascii=False, indent=2)

    prompt = f"""以下2つを比較してください。

【A】258セッションから独立抽出した原則（1346件→再集約版）:
{agg_json}

【B】既存「玄_在り方.md」（v3.0、40セクション）:
{arikata_text[:8000]}  ← 文字数制限のため冒頭8000字

3分類で比較レポートを作成してください：

## MATCH（一致・補強）
| 原則（A） | v3.0との対応 | 確信度 | 備考 |
|---|---|---|---|

## NEW（v3.0未収録の新規候補）
| 原則（A） | カテゴリ | 頻度 | 追加推奨度 | 理由 |
|---|---|---|---|---|

## CONFLICT（要検証・矛盾点）
| Aの抽出 | v3.0の記述 | 差異のポイント | 検証方向 |
|---|---|---|---|

## 総評
v3.0でまだカバーできていない観点、頻度が高いのに未収録の原則、特に注目すべきパターンを記述してください。

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
    print("  Project GEN - 再集約 Fix版（sonnet 2段階）")
    print("=" * 60)

    # 生データ読み込み
    raw_principles = json.loads(INTER_FULL.read_text(encoding="utf-8"))
    print(f"\n[INFO] 生データ読み込み: {len(raw_principles)}件")

    # Phase1: haiku 40件/バッチ
    print("\n[STEP 2] Phase1（haiku, 40件/バッチ）...")
    phase1_data = phase1_haiku(raw_principles)
    print(f"\n[INFO] Phase1完了: {len(phase1_data)}件")

    cats = {}
    for p in phase1_data:
        c = p.get('category', '?')
        cats[c] = cats.get(c, 0) + 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}件")

    # Phase1b: sonnet 100件/バッチ
    print("\n[STEP 2b] Phase1b（sonnet, 100件/バッチ）...")
    phase1b = phase1b_sonnet(phase1_data)

    if len(phase1b) == 0:
        print("❌ Phase1bが0件でした。スクリプトを確認してください。")
        return

    # Phase2: sonnet 最終集約
    print("\n[STEP 2c] Phase2最終集約（sonnet）...")
    phase2 = phase2_final(phase1b)

    if len(phase2) == 0:
        print("❌ Phase2が0件でした。")
        return

    # 保存
    AGG_FILE.write_text(json.dumps(phase2, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  集約結果を保存: {AGG_FILE}")

    # v3.0との比較
    arikata_text = ARIKATA_MD.read_text(encoding="utf-8")
    comparison_md = generate_comparison(phase2, arikata_text)

    # レポート出力
    report = f"""# 在り方 比較レポート（再集約Fix版）

## 概要
- 実行日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
- 生データ: {len(raw_principles)}件（在り方_中間抽出_full.json）
- Phase1（haiku 40件/バッチ）後: {len(phase1_data)}件
- Phase1b（sonnet 100件/バッチ）後: {len(phase1b)}件
- Phase2（sonnet 最終集約）後: {len(phase2)}件
- 比較対象: 玄_在り方.md（v3.0 / 40セクション）

---

{comparison_md}

---

## 集約原則の全リスト（再集約Fix版）

| # | 原則 | カテゴリ | 頻度 | 確信度 |
|---|---|---|---|---|
"""
    for i, p in enumerate(phase2, 1):
        report += f"| {i} | {p.get('principle','')} | {p.get('category','')} | {p.get('frequency','-')} | {p.get('confidence','-')} |\n"

    REPORT_FILE.write_text(report, encoding="utf-8")

    # クリーンアップ（成功時のみ）
    for f in [PHASE1_FILE, PHASE1B_FILE]:
        if f.exists():
            f.unlink()

    print(f"\n{'='*60}")
    print(f"  ✅ 完了！")
    print(f"  → レポート: {REPORT_FILE}")
    print(f"  最終原則数: {len(phase2)}件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

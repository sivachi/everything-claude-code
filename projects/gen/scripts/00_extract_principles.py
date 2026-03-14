"""
00_extract_principles.py
========================
2位 ICAI (Inverse Constitutional AI) アプローチ

やること:
  1. 生HTMLファイルからGENの発言テキストを抽出
  2. Claudeで「この人物の暗黙の在り方・原則を抽出」
  3. 既存の 玄_在り方.md と突き合わせて3分類
     - MATCH   : 一致・補強
     - NEW     : 在り方.mdにない新規発見
     - CONFLICT: 在り方.mdと矛盾・要検証
  4. 比較レポートを output/在り方_比較レポート.md に出力
"""

import os
import sys
import json
import re
import time
import random
from pathlib import Path
from bs4 import BeautifulSoup
import anthropic

# ── パス設定 ──────────────────────────────────────
BASE_DIR    = Path("/Users/tadaakikurata/works/ai_takeo_local")
SOURCE_DIR  = Path("/Users/tadaakikurata/works/ai_takeo/AI竹尾プロジェクト(人格コピー)/Sources")
ARIKATA_MD  = BASE_DIR / "玄_在り方.md"
OUTPUT_DIR  = BASE_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "在り方_比較レポート.md"

# ── サンプリング設定 ──────────────────────────────
# 全258ファイルは多いので、種別ごとにバランス良くサンプリング
SAMPLE_CONFIG = {
    "囲炉裏": 8,
    "タケチング": 8,
    "神社": 4,
    "Dream": 5,
    "その他": 5,
}
TOTAL_SAMPLE = sum(SAMPLE_CONFIG.values())  # 30ファイル

# ── フィラー除去 ──────────────────────────────────
FILLER_PATTERN = re.compile(
    r'(あー+|うー+ん*|えー+|んー+|えっと|まあ+|あのー*|そのー*|なんか+|ちょっと+)'
    r'(?![^\s])',  # 単独フィラーのみ除去（単語の一部は残す）
    re.UNICODE
)


def extract_text_from_html(filepath: Path) -> str:
    """HTMLからプレーンテキストを抽出"""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        paragraphs = soup.find_all("p")
        if paragraphs:
            text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        else:
            text = soup.get_text(separator="\n", strip=True)
        # フィラー除去
        text = FILLER_PATTERN.sub("", text)
        # 連続空白・改行の正規化
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    except Exception as e:
        print(f"  [WARN] HTML解析エラー {filepath.name}: {e}")
        return ""


def classify_session_type(filename: str) -> str:
    """ファイル名からセッション種別を推定"""
    name = filename.lower()
    if "囲炉裏" in filename or "iroriconsul" in name:
        return "囲炉裏"
    elif "タケチング" in filename or "takechng" in name or "takeo" in name:
        return "タケチング"
    elif "神社" in filename or "shrine" in name:
        return "神社"
    elif "dream" in name or "ドリーム" in filename:
        return "Dream"
    else:
        return "その他"


def sample_files() -> list[dict]:
    """セッション種別ごとにバランス良くファイルをサンプリング"""
    html_files = list(SOURCE_DIR.glob("*.html"))
    print(f"[INFO] HTMLファイル総数: {len(html_files)}")

    # 種別ごとに分類
    buckets = {k: [] for k in SAMPLE_CONFIG}
    for f in html_files:
        stype = classify_session_type(f.name)
        buckets[stype].append(f)

    print("[INFO] セッション種別内訳:")
    for k, v in buckets.items():
        print(f"  {k}: {len(v)}ファイル")

    # サンプリング
    sampled = []
    for stype, count in SAMPLE_CONFIG.items():
        files = buckets[stype]
        n = min(count, len(files))
        chosen = random.sample(files, n)
        for f in chosen:
            sampled.append({"path": f, "session_type": stype})

    random.shuffle(sampled)
    print(f"[INFO] サンプリング数: {len(sampled)}ファイル\n")
    return sampled


def extract_principles_from_session(client: anthropic.Anthropic, session_text: str, session_type: str) -> str:
    """1セッションからGENの在り方・原則を抽出"""
    # テキストが長すぎる場合は先頭3000文字に制限
    truncated = session_text[:3000] if len(session_text) > 3000 else session_text

    prompt = f"""以下は、あるメンター（以下「GEN」）の会話・セッションの文字起こしです。
セッション種別: {session_type}

---
{truncated}
---

このテキストを読んで、GENという人物が**暗黙的に持っている在り方・価値観・信念・行動原則**を抽出してください。

【抽出ルール】
- GENが「こうあるべき」「こう考えている」と示している原則を列挙する
- 表面的な発言ではなく、その背後にある価値観・哲学を読み取る
- 1セッションにつき3〜8個を目安に抽出
- 各原則は1〜2文で簡潔に記述

【出力フォーマット（JSON）】
{{
  "principles": [
    {{
      "principle": "原則の内容（簡潔に）",
      "evidence": "そう読み取った根拠となる発言や行動（短く）",
      "category": "believes / values / rejects / diagnoses_via / communicates_using のいずれか"
    }}
  ]
}}

JSONのみを出力してください。説明文は不要です。"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except anthropic.RateLimitError:
        print("  [WARN] RateLimit - 30秒待機...")
        time.sleep(30)
        return extract_principles_from_session(client, session_text, session_type)
    except Exception as e:
        print(f"  [ERROR] API呼び出しエラー: {e}")
        return '{"principles": []}'


def aggregate_principles(all_principles: list[dict]) -> str:
    """全セッションの原則を集約・重複排除・合成"""
    client = anthropic.Anthropic()

    # 全原則をテキスト化
    principles_text = ""
    for i, p in enumerate(all_principles):
        principles_text += f"[{i+1}] ({p['category']}) {p['principle']}\n"
        principles_text += f"    根拠: {p['evidence']}\n\n"

    prompt = f"""以下は、GENという人物の複数セッション（{len(all_principles)}件）から抽出された在り方・原則の一覧です。

---
{principles_text}
---

これらを以下の手順で整理してください：

1. **重複・類似している原則をまとめる**（出現頻度が高いほど確度が高い）
2. **5つのカテゴリに分類する**
   - believes（信念：世界・人間についての確信）
   - values（大切にしていること）
   - rejects（否定・拒絶していること）
   - diagnoses_via（人・状況をどう読むか）
   - communicates_using（コミュニケーションの技法）
3. **各カテゴリ内で出現頻度順に並べる**

【出力フォーマット（JSON）】
{{
  "aggregated": [
    {{
      "principle": "原則の内容",
      "category": "カテゴリ",
      "frequency": 出現セッション数（推定）,
      "confidence": "high / medium / low"
    }}
  ]
}}

JSONのみを出力してください。"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] 集約APIエラー: {e}")
        return '{"aggregated": []}'


def compare_with_arikata(client: anthropic.Anthropic, aggregated_principles: list[dict], arikata_text: str) -> str:
    """抽出した原則と既存の玄_在り方.mdを比較"""

    aggregated_text = json.dumps(aggregated_principles, ensure_ascii=False, indent=2)

    prompt = f"""以下の2つを比較してください。

【A】Claudeがデータから独立抽出した原則（ICAI手法）:
{aggregated_text}

【B】既存の「玄_在り方.md」（NotebookLMが抽出）:
{arikata_text}

---

以下の3分類で比較結果をまとめてください：

**MATCH（一致・補強）**: AとBの両方に共通して現れる原則
  - Aの抽出により確証が取れた → 残す

**NEW（新規発見）**: Aにあって、Bにない原則
  - Bへの追加候補 → 取捨選択が必要

**CONFLICT（矛盾・要検証）**: AとBで内容が食い違う原則
  - どちらが正しいか確認が必要

【出力フォーマット（Markdown）】

## MATCH（確証が取れた在り方）
| 原則 | B（既存）との対応 | 確信度 |
|---|---|---|
| ... | ... | high/medium/low |

## NEW（新規追加候補）
| 原則 | カテゴリ | 根拠の強さ | 追加推奨度 |
|---|---|---|---|
| ... | ... | ... | ★★★/★★/★ |

## CONFLICT（要検証）
| Aの抽出 | Bの記述 | 差異のポイント |
|---|---|---|
| ... | ... | ... |

## 総評
- データが裏付けた在り方の確信度
- Bへの主な追記候補
- 特に注目すべき発見

Markdownで出力してください。"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] 比較APIエラー: {e}")
        return "比較エラーが発生しました"


def parse_json_safe(text: str) -> dict:
    """JSONパース（コードブロック対応）"""
    # ```json ... ``` を除去
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSONパースエラー: {e}")
        return {}


def main():
    print("=" * 60)
    print("  Project GEN - 2位 ICAI 在り方抽出・比較スクリプト")
    print("=" * 60)

    # APIキー確認
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # .envファイルを確認
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ["ANTHROPIC_API_KEY"] = api_key
                        print("[INFO] .envからAPIキーを読み込みました")
                        break
        if not api_key:
            print("[ERROR] ANTHROPIC_API_KEY が設定されていません")
            print("  .envファイルに ANTHROPIC_API_KEY=sk-ant-... を記載するか")
            print("  export ANTHROPIC_API_KEY=sk-ant-... を実行してください")
            sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # 既存の在り方.mdを読み込む
    print(f"\n[STEP 0] 既存の玄_在り方.md を読み込み...")
    if not ARIKATA_MD.exists():
        print(f"[ERROR] {ARIKATA_MD} が見つかりません")
        sys.exit(1)
    arikata_text = ARIKATA_MD.read_text(encoding="utf-8")
    print(f"  → {len(arikata_text)}文字 読み込み完了")

    # ファイルサンプリング
    print(f"\n[STEP 1] ファイルをサンプリング...")
    sampled_files = sample_files()

    # 各セッションから原則抽出
    print(f"\n[STEP 2] {len(sampled_files)}ファイルから在り方を抽出中...")
    all_principles = []
    for i, item in enumerate(sampled_files):
        filepath = item["path"]
        stype    = item["session_type"]
        print(f"  [{i+1:02d}/{len(sampled_files)}] {filepath.name[:50]}...")

        text = extract_text_from_html(filepath)
        if not text or len(text) < 100:
            print(f"  [SKIP] テキストが短すぎます ({len(text)}文字)")
            continue

        result_json = extract_principles_from_session(client, text, stype)
        parsed = parse_json_safe(result_json)
        principles = parsed.get("principles", [])

        for p in principles:
            p["source_file"]    = filepath.name
            p["session_type"]   = stype
            all_principles.append(p)

        print(f"  → {len(principles)}個の原則を抽出")
        time.sleep(1)  # API負荷軽減

    print(f"\n  合計 {len(all_principles)} 個の原則を抽出しました")

    # 中間結果を保存
    intermediate_path = BASE_DIR / "output" / "在り方_中間抽出.json"
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(intermediate_path, "w", encoding="utf-8") as f:
        json.dump(all_principles, f, ensure_ascii=False, indent=2)
    print(f"  中間結果を保存: {intermediate_path}")

    # 原則を集約
    print(f"\n[STEP 3] 原則を集約・重複排除中...")
    agg_json = aggregate_principles(all_principles)
    agg_parsed = parse_json_safe(agg_json)
    aggregated = agg_parsed.get("aggregated", [])
    print(f"  → {len(aggregated)} 個の集約原則")

    # 既存の在り方.mdと比較
    print(f"\n[STEP 4] 玄_在り方.md と比較中...")
    comparison_md = compare_with_arikata(client, aggregated, arikata_text)

    # レポート出力
    print(f"\n[STEP 5] レポートを出力中...")
    report = f"""# 在り方 比較レポート
## 概要
- 実行日時: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
- 分析ファイル数: {len(sampled_files)} / 258
- 抽出原則数（生）: {len(all_principles)}
- 集約後原則数: {len(aggregated)}
- 比較対象: 玄_在り方.md（NotebookLM抽出・v1.0）

---

{comparison_md}

---

## 集約原則の全リスト（Claudeによる独立抽出）

| # | 原則 | カテゴリ | 頻度 | 確信度 |
|---|---|---|---|---|
"""
    for i, p in enumerate(aggregated, 1):
        report += f"| {i} | {p.get('principle','')} | {p.get('category','')} | {p.get('frequency','-')} | {p.get('confidence','-')} |\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n{'='*60}")
    print(f"  完了！レポートを出力しました")
    print(f"  → {OUTPUT_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

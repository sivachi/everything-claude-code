# -*- coding: utf-8 -*-
"""AI竹尾ナレッジベース構築（HTTP直接版）

google.generativeaiを使わず、直接HTTP APIを呼び出すバージョン
"""

import os
import re
import time
import json
import requests
from datetime import datetime

# ==========================================
# 1. 設定
# ==========================================
GOOGLE_API_KEY = "AIzaSyArusnTtHc7CY_Y11j2-XaAWbum600PbO0"

INPUT_FILE = "全HTMLテキスト抽出.txt"
OUTPUT_FILE = "AI竹尾_ナレッジベース_完成版.md"

# Gemini API endpoint
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}"

# ==========================================
# 2. クリーニング関数
# ==========================================

def clean_text_regex(text):
    """正規表現による強力なノイズ除去（前処理）"""
    lines = text.split('\n')
    cleaned_lines = []

    remove_patterns_line = [
        r"^うん[。、]?$", r"^うんうん[。、]?$", r"^ああ[。、]?$",
        r"^えっと[。、]?$", r"^えー[。、]?$", r"^あのー[。、]?$",
        r"^はい[。、]?$", r"^なるほど[。、]?$", r"^そうですね[。、]?$",
        r"^そう[。、]?$", r"^そっか[。、]?$", r"^へえ[。、]?$",
        r"^ええ[。、]?$", r"^おお[。、]?$", r"^うーん[。、]?$",
        r"^確かに[。、]?$", r"^録音[。、]?$", r"^録画[。、]?$",
        r"^.{1,3}$", r"^=+$",
    ]

    replace_patterns = [
        (r"^えっと、", ""), (r"^あの、", ""), (r"^ま、", ""),
        (r"^あ、", ""), (r"うん。うん。", ""), (r"ああ、", ""),
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if any(re.match(p, line) for p in remove_patterns_line):
            continue

        for p, r in replace_patterns:
            line = re.sub(p, r, line)

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def call_gemini_api(prompt, max_retries=3):
    """Gemini APIを直接HTTPで呼び出す"""
    headers = {
        "Content-Type": "application/json",
    }

    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        }
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=data, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    print(f"  [Warning] Empty response from API")
                    return None
            elif response.status_code == 429:
                print(f"  [Rate limit] Waiting 30 seconds...")
                time.sleep(30)
            else:
                print(f"  [Error] Status {response.status_code}: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"  [Error] Attempt {attempt + 1}: {e}")
            time.sleep(5)

    return None


def process_session_with_ai(file_name, session_text):
    """Gemini APIを使って、1セッション分のテキストを構造化する"""

    prompt = f"""あなたは優秀な編集者です。以下の対話テキストは、メンター「竹尾氏」と相談者の会話です。
ノイズ（フィラーや相槌）を除去し、以下のフォーマットで要約・構造化してください。

【重要ルール】
1. 竹尾氏の口調（関西弁、語り口）は**絶対に修正せず、そのまま維持**してください。
2. 相談者の悩みと、竹尾氏の教えを明確に分けてください。
3. 複数のトピックがある場合は、それぞれ分けて出力してください。

【入力テキスト】
{session_text[:12000]}

【出力フォーマット】
### 出典: {file_name}

**【相談内容 / 文脈】**
(相談者が何を悩み、どのような状況にあるかを簡潔に要約)

**【竹尾氏の教え / 回答】**
(竹尾氏の発言から、ノイズを除去した「核となる教え」を記述。箇条書きではなく、語り口を再現した文章で)

**【関連タグ】**
#タグ1 #タグ2

---
"""

    result = call_gemini_api(prompt)

    if result:
        return result
    else:
        # エラー時は原文を返す
        return f"### 出典: {file_name}\n\n(AI処理エラー)\n\n{session_text[:2000]}\n\n---\n"


# ==========================================
# 3. メイン処理
# ==========================================
def main():
    print(f"{'='*60}")
    print(f"AI竹尾 ナレッジベース構築（HTTP直接版）")
    print(f"{'='*60}")
    print(f"\n開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not os.path.exists(INPUT_FILE):
        print(f"エラー: {INPUT_FILE} が見つかりません。")
        return

    # 全ファイルを読み込み
    print(f"\n読み込み: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        full_text = f.read()

    print(f"元のサイズ: {len(full_text):,} 文字")

    # 【ファイル名】でセッションごとに分割
    sessions = re.split(r'【ファイル名】', full_text)

    if not sessions[0].strip():
        sessions = sessions[1:]

    total_sessions = len(sessions)
    print(f"検出されたセッション数: {total_sessions}")

    final_output = "# AI竹尾 ナレッジベース (完成版)\n\n"
    final_output += "竹尾氏の対話から抽出した教えをまとめたナレッジベースです。\n"
    final_output += "フィラー・ノイズを除去し、AI竹尾チャットボットの学習データとして使用します。\n\n"
    final_output += "---\n\n"

    processed = 0
    errors = 0

    for i, session in enumerate(sessions):
        parts = session.split('\n', 1)
        file_name = parts[0].strip()
        body = parts[1] if len(parts) > 1 else ""

        if not body.strip():
            continue

        # ファイル名整形
        if file_name.endswith('.html'):
            file_name = file_name[:-5]

        print(f"[{i+1}/{total_sessions}] 処理中: {file_name[:40]}...")

        # 1. 正規表現クリーニング
        cleaned_body = clean_text_regex(body)

        if len(cleaned_body) < 100:
            print(f"  -> スキップ（内容が短すぎます）")
            continue

        # 2. AIによる構造化
        structured_content = process_session_with_ai(file_name, cleaned_body)

        if structured_content:
            final_output += structured_content + "\n"
            processed += 1
        else:
            errors += 1

        # Rate Limit対策
        time.sleep(2)

    # 結果を保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_output)

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"完了！")
    print(f"出力ファイル: {OUTPUT_FILE}")
    print(f"ファイルサイズ: {size_mb:.2f} MB")
    print(f"処理セッション: {processed}")
    print(f"エラー: {errors}")
    print(f"終了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

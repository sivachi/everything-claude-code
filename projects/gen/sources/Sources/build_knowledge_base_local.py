# -*- coding: utf-8 -*-
"""AI竹尾ナレッジベース構築（ローカル版）

google.generativeaiを使わず、正規表現によるノイズ除去のみを行うバージョン
"""

import os
import re

# ==========================================
# 1. 設定
# ==========================================
# 入力ファイル名
INPUT_FILE = "全HTMLテキスト抽出.txt"
# 出力ファイル名
OUTPUT_FILE = "AI竹尾_ナレッジベース_完成版.md"

# ==========================================
# 2. クリーニング関数
# ==========================================

def clean_text_regex(text):
    """
    正規表現による強力なノイズ除去
    """
    lines = text.split('\n')
    cleaned_lines = []

    # 削除対象のパターン（行全体がマッチしたら削除）
    remove_patterns_line = [
        r"^うん[。、]?$",
        r"^うんうん[。、うん]*$",
        r"^ああ[。、]?$",
        r"^えっと[。、]?$",
        r"^えー[。、]?$",
        r"^あのー[。、]?$",
        r"^はい[。、]?$",
        r"^なるほど[。、]?$",
        r"^そうですね[。、]?$",
        r"^そう[。、]?$",
        r"^そっか[。、]?$",
        r"^へえ[。、]?$",
        r"^ええ[。、]?$",
        r"^おお[。、]?$",
        r"^うーん[。、]?$",
        r"^確かに[。、]?$",
        r"^ほんと[。、]?$",
        r"^録音[。、]?$",
        r"^録画[。、]?$",
        r"^スタート[。、]?$",
        r"^お$",
        r"^={10,}$",  # 区切り線
    ]

    # 文中の置換対象（先頭から削除）
    replace_patterns_start = [
        (r"^えっと[、。]?\s*", ""),
        (r"^あの[ー]?[、。]?\s*", ""),
        (r"^ま[、。]\s*", ""),
        (r"^で[、。]\s*", ""),
        (r"^うん[、。]\s*", ""),
    ]

    # 文中の置換対象（どこでも）
    replace_patterns_anywhere = [
        (r"うん。うん。", ""),
        (r"うん。うん。うん。", ""),
        (r"うんうん", ""),
        (r"ああ、", ""),
        (r"うん、", ""),
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue  # 空行スキップ

        # 行削除判定
        should_remove = False
        for p in remove_patterns_line:
            if re.match(p, line):
                should_remove = True
                break
        if should_remove:
            continue

        # 先頭の置換
        for p, r in replace_patterns_start:
            line = re.sub(p, r, line)

        # 文中の置換
        for p, r in replace_patterns_anywhere:
            line = re.sub(p, r, line)

        line = line.strip()
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

def get_tags(file_name, content):
    """ファイル名と内容からタグを生成"""
    tags = set()

    fn_lower = file_name.lower()
    if 'dream' in fn_lower:
        tags.add('#夢占い')
    if 'タケチング' in file_name or 'たけちゃん' in file_name:
        tags.add('#タケチング')
    if '囲炉裏' in file_name or 'コンサル' in file_name:
        tags.add('#コンサル')
    if '神社' in file_name:
        tags.add('#神社')
    if '愛' in file_name:
        tags.add('#愛')
    if '笑' in file_name:
        tags.add('#笑')
    if '心虹会' in file_name:
        tags.add('#心虹会')

    # コンテンツからタグ
    keywords = {
        '#過去世': ['過去世', '前世'],
        '#守護霊': ['守護霊', '護霊さん'],
        '#金縛り': ['金縛り'],
        '#夢解釈': ['夢を見', '夢の中で', '夢で'],
        '#仕事': ['仕事', '会社', '営業', 'ビジネス'],
        '#恋愛': ['恋愛', '彼氏', '彼女', 'デート'],
        '#結婚': ['結婚', '離婚', '旦那', '夫婦'],
        '#家族': ['親', '母', '父', '兄弟', '姉妹', '子供'],
        '#供養': ['供養', '法事', '法要'],
        '#霊的現象': ['幽霊', '霊が', '霊さん'],
        '#エゴ': ['エゴ'],
        '#魂の色': ['黒', '白'],
        '#チャクラ': ['チャクラ'],
        '#波動': ['波動'],
        '#お金': ['お金', '収入', '稼'],
    }

    for tag, kws in keywords.items():
        for kw in kws:
            if kw in content:
                tags.add(tag)
                break

    return ' '.join(sorted(tags)) if tags else '#一般'

def process_session(file_name, session_text):
    """
    1セッション分のテキストを構造化する
    """
    # クリーニング
    cleaned = clean_text_regex(session_text)

    if not cleaned.strip():
        return None

    # タグ生成
    tags = get_tags(file_name, cleaned)

    # 出力形式に整形
    # ファイル名から.htmlを除去
    display_name = file_name
    if display_name.endswith('.html'):
        display_name = display_name[:-5]

    # 長すぎる場合は省略
    max_len = 8000
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "\n\n[... 以下省略 ...]"

    output = f"""### 出典: {display_name}

**【相談内容 / 文脈】**
（以下の対話から相談者の悩みや質問を抽出）

**【竹尾氏の教え / 回答】**
{cleaned}

**【関連タグ】**
{tags}

---
"""
    return output

# ==========================================
# 3. メイン処理
# ==========================================
def main():
    print(f"--- 処理開始: {INPUT_FILE} ---")

    if not os.path.exists(INPUT_FILE):
        print(f"エラー: {INPUT_FILE} が見つかりません。")
        return

    # 全ファイルを読み込み
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        full_text = f.read()

    # 【ファイル名】でセッションごとに分割
    sessions = re.split(r'【ファイル名】', full_text)

    # 最初の要素は空の可能性があるので除外
    if not sessions[0].strip():
        sessions = sessions[1:]

    total_sessions = len(sessions)
    print(f"検出されたセッション数: {total_sessions}")

    final_output = "# AI竹尾 ナレッジベース (完成版)\n\n"
    final_output += "竹尾氏の対話から抽出した教えをまとめたナレッジベースです。\n"
    final_output += "AI竹尾チャットボットの学習データとして使用します。\n\n"
    final_output += "---\n\n"

    processed_count = 0

    # 各セッションを処理
    for i, session in enumerate(sessions):
        # ファイル名と本文を分離
        parts = session.split('\n', 1)
        file_name = parts[0].strip()
        body = parts[1] if len(parts) > 1 else ""

        if not body.strip():
            continue

        if (i + 1) % 50 == 0:
            print(f"[{i+1}/{total_sessions}] 処理中...")

        # 構造化処理
        result = process_session(file_name, body)

        if result:
            final_output += result + "\n"
            processed_count += 1

    # 結果を保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_output)

    # ファイルサイズ
    size = os.path.getsize(OUTPUT_FILE)
    print(f"\n--- 完了！---")
    print(f"出力ファイル: {OUTPUT_FILE}")
    print(f"処理セッション数: {processed_count}")
    print(f"ファイルサイズ: {size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    main()

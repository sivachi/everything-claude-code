#!/usr/bin/env python3
"""
03_output.py — 分類済みチャンクからカテゴリ別マークダウンを生成

処理内容:
  - output/classified.jsonl を読み込み
  - スピリチュアル分類.mdのカテゴリ体系に従って整理
  - カテゴリ別にマークダウンファイルを output_md/カテゴリ別/ に出力
  - 出典（source_file）を各項目に付与

出力形式（運営・コンサルでのスピリチュアルQA.md を参考）:
  ## カテゴリ名
  ### トピック名
  - 要約内容
  **出典：** ファイル名

使用方法:
  python3 scripts/03_output.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"
CLASSIFIED_FILE = OUTPUT_DIR / "classified.jsonl"
CATEGORY_OUTPUT_DIR = PROJECT_DIR / "output_md" / "カテゴリ別"

# カテゴリ番号の上位番号 → カテゴリ名のマッピング
MAIN_CATEGORIES = {
    "1": "存在",
    "2": "魂",
    "3": "世界のしくみ",
    "4": "能力",
    "5": "実践",
    "6": "道具",
    "7": "読み取り",
    "8": "伝説・未知",
    "9": "日常との関わり",
}

SUB_CATEGORIES = {
    "1-1": "神聖な存在",
    "1-2": "霊的な存在",
    "1-3": "人間以外の知的存在",
    "2-1": "魂そのもの",
    "2-2": "生まれ変わり",
    "2-3": "魂のつながり",
    "2-4": "原因と学び",
    "3-1": "見えない力",
    "3-2": "意識",
    "3-3": "世界構造",
    "3-4": "時間",
    "3-5": "現実変化",
    "4-1": "感じる力",
    "4-2": "見る力",
    "4-3": "聞く・受け取る力",
    "4-4": "影響を与える力",
    "4-5": "未来に関わる力",
    "5-1": "癒やし",
    "5-2": "浄化",
    "5-3": "守り",
    "5-4": "供養・祈祷",
    "5-5": "修行",
    "5-6": "死後のプロセス",
    "6-1": "清めの道具",
    "6-2": "石と自然物",
    "6-3": "読み取りの道具",
    "7-1": "日常のサイン",
    "7-2": "占い・リーディング",
    "8-1": "失われた文明",
    "8-2": "特別な場所",
    "8-3": "隠された世界観",
    "9-1": "恋愛と人間関係",
    "9-2": "お金と仕事",
    "9-3": "心と体の変化",
}


def clean_source_name(source_file):
    """ファイル名を出典表示用に整形"""
    name = source_file
    # 拡張子除去
    for ext in [".md", ".txt", ".html"]:
        name = name.replace(ext, "")
    return name


def get_main_category(category_id):
    """カテゴリIDから上位カテゴリ番号を取得"""
    if not category_id or category_id in ("none", "error", "unknown"):
        return None
    return category_id.split("-")[0]


def get_sub_category(category_id):
    """カテゴリIDからサブカテゴリ番号を取得"""
    if not category_id or category_id in ("none", "error", "unknown"):
        return None
    parts = category_id.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return None


def main():
    if not CLASSIFIED_FILE.exists():
        print(f"エラー: {CLASSIFIED_FILE} が見つかりません。先に 02_classify.py を実行してください。")
        return

    # 分類結果読み込み
    records = []
    with open(CLASSIFIED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    print(f"分類済みチャンク: {len(records)} 件")

    # スピリチュアル関連のみ抽出
    spiritual = [r for r in records if r.get("is_spiritual") and r.get("category_id") not in ("none", "error", "unknown")]
    print(f"スピリチュアル関連: {len(spiritual)} 件")

    # カテゴリ別に整理
    by_main = defaultdict(lambda: defaultdict(list))
    for r in spiritual:
        main_cat = get_main_category(r["category_id"])
        sub_cat = get_sub_category(r["category_id"])
        if main_cat:
            by_main[main_cat][sub_cat or main_cat].append(r)

    # 出力ディレクトリ作成
    CATEGORY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # カテゴリ別ファイル生成
    for main_num in sorted(by_main.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        main_name = MAIN_CATEGORIES.get(main_num, f"カテゴリ{main_num}")
        filename = f"{main_num}_{main_name}.md"
        filepath = CATEGORY_OUTPUT_DIR / filename

        lines = [f"# {main_num}. {main_name}", ""]

        sub_items = by_main[main_num]
        for sub_num in sorted(sub_items.keys()):
            sub_name = SUB_CATEGORIES.get(sub_num, sub_num)
            items = sub_items[sub_num]

            lines.append(f"## {sub_num} {sub_name}")
            lines.append("")

            # トピック別にグループ化
            by_topic = defaultdict(list)
            for item in items:
                topic = item.get("topic", "その他")
                by_topic[topic].append(item)

            for topic, topic_items in by_topic.items():
                lines.append(f"### {topic}")
                lines.append("")

                for item in topic_items:
                    summary = item.get("summary", "")
                    if summary:
                        lines.append(f"- {summary}")

                # 出典をまとめる
                sources = sorted(set(clean_source_name(item["source_file"]) for item in topic_items))
                lines.append("")
                lines.append(f"**出典：** {', '.join(sources)}")
                lines.append("")

            lines.append("---")
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        count = sum(len(v) for v in sub_items.values())
        print(f"  ✓ {filename} ({count} 項目)")

    # 非スピリチュアルチャンクも別ファイルに
    non_spiritual = [r for r in records if not r.get("is_spiritual") or r.get("category_id") in ("none", "error", "unknown")]
    if non_spiritual:
        misc_path = CATEGORY_OUTPUT_DIR / "0_その他・雑談.md"
        lines = ["# その他・雑談", "", "スピリチュアルに直接関係しない内容のまとめ。", ""]
        for item in non_spiritual:
            summary = item.get("summary", "")
            source = clean_source_name(item["source_file"])
            if summary:
                lines.append(f"- {summary}")
                lines.append(f"  **出典：** {source}")
                lines.append("")
        misc_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  ✓ 0_その他・雑談.md ({len(non_spiritual)} 項目)")

    # 全体統合ファイル
    all_path = CATEGORY_OUTPUT_DIR / "全カテゴリ統合.md"
    all_lines = ["# 謎の会 スピリチュアル知見集", ""]
    all_lines.append("全ソースから抽出・分類したスピリチュアル関連の知見をカテゴリ別に整理したもの。")
    all_lines.append("")
    all_lines.append("---")
    all_lines.append("")

    for main_num in sorted(by_main.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        main_name = MAIN_CATEGORIES.get(main_num, f"カテゴリ{main_num}")
        all_lines.append(f"## {main_num}. {main_name}")
        all_lines.append("")

        sub_items = by_main[main_num]
        for sub_num in sorted(sub_items.keys()):
            sub_name = SUB_CATEGORIES.get(sub_num, sub_num)
            items = sub_items[sub_num]

            all_lines.append(f"### {sub_num} {sub_name}")
            all_lines.append("")

            by_topic = defaultdict(list)
            for item in items:
                topic = item.get("topic", "その他")
                by_topic[topic].append(item)

            for topic, topic_items in by_topic.items():
                all_lines.append(f"#### {topic}")
                all_lines.append("")
                for item in topic_items:
                    summary = item.get("summary", "")
                    if summary:
                        all_lines.append(f"- {summary}")
                sources = sorted(set(clean_source_name(item["source_file"]) for item in topic_items))
                all_lines.append("")
                all_lines.append(f"**出典：** {', '.join(sources)}")
                all_lines.append("")

        all_lines.append("---")
        all_lines.append("")

    all_path.write_text("\n".join(all_lines), encoding="utf-8")
    print(f"\n  ✓ 全カテゴリ統合.md")

    print(f"\n出力先: {CATEGORY_OUTPUT_DIR}")


if __name__ == "__main__":
    main()

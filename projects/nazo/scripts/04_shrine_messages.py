#!/usr/bin/env python3
"""
04_shrine_messages.py — 神社メッセージdocxファイルから神社ごとのMDファイルを生成

処理内容:
  - /Users/tadaakikurata/works/神社メッセージ/*.docx を読み込み
  - 神社ごとにメッセージと解説を整理
  - PIIマスクを適用
  - output_md/神社メッセージ/ にMDファイルを出力

使用方法:
  python3 scripts/04_shrine_messages.py
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

try:
    import docx
except ImportError:
    print("python-docx が必要です: pip install python-docx")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent.parent
SHRINE_MSG_DIR = Path("/Users/tadaakikurata/works/神社メッセージ")
OUTPUT_DIR = PROJECT_DIR / "output_md" / "神社メッセージ"

# GENプロジェクト準拠マスクルール + 神社メッセージ固有の人名
MASK_RULES = [
    # ── 施設・サービス・イベント名 ──
    ("囲炉裏",     "[施設A]",     False),
    ("Dream",      "[施設B]",     False),
    ("ワープ",     "[施設C]",     False),
    ("亀戸",       "[場所A]",     False),
    ("錦糸町",     "[場所B]",     False),

    # ── しんちゃん ──
    ("しんちゃん", "[人物E]", False),

    # ── 玄本人（タケ/竹/竹尾） ──
    ("竹尾",        "[人物G]", False),
    ("たけちゃん",  "[人物G]", False),
    ("タケちゃん",  "[人物G]", False),
    ("竹ちゃん",    "[人物G]", False),
    ("たけさん",    "[人物G]さん", False),
    ("タケさん",    "[人物G]さん", False),
    ("竹さん",      "[人物G]さん", False),
    (r"たけ(?!ど|れど|のこ)", "[人物G]", True),
    (r"タケ(?!ハラ)", "[人物G]", True),
    (r"竹(?!林|の子|ノコ|刀|串|馬|べら|内|島|下|中)", "[人物G]", True),

    # ── 美穂 ──
    ("みほ",   "[人物A]", False),
    ("ミホ",   "[人物A]", False),
    ("美穂",   "[人物A]", False),

    # ── 満美 ──
    ("まみ",   "[人物B]", False),
    ("マミ",   "[人物B]", False),
    ("満美",   "[人物B]", False),

    # ── 麻貴 ──
    ("まき",   "[人物C]", False),
    ("マキ",   "[人物C]", False),
    ("麻貴",   "[人物C]", False),

    # ── カレン ──
    ("かれん", "[人物D]", False),
    ("カレン", "[人物D]", False),

    # ── クラッチ/倉田 ──
    ("くらっち",  "[人物F]", False),
    ("クラッチ",  "[人物F]", False),
    ("倉田",      "[人物F]", False),
    ("倉っち",    "[人物F]", False),
    ("クラさん",  "[人物F]さん", False),
    ("倉さん",    "[人物F]さん", False),

    # ── ムロ・室 ──
    ("室さん",   "[人物H]さん", False),
    ("室くん",   "[人物H]くん", False),
    ("室ちゃん", "[人物H]ちゃん", False),
    ("むろ",     "[人物H]", False),
    ("ムロ",     "[人物H]", False),

    # ── カズ ──
    ("カズさん",   "[人物I]さん", False),
    ("カズくん",   "[人物I]くん", False),
    ("カズちゃん", "[人物I]ちゃん", False),
    ("カズ君",     "[人物I]君", False),
    ("かずさん",   "[人物I]さん", False),
    ("かずくん",   "[人物I]くん", False),
    ("かずちゃん", "[人物I]ちゃん", False),
    ("かず君",     "[人物I]君", False),
    (r"カズ(?!レーザー)", "[人物I]", True),

    # ── ルミ・留美 ──
    ("留美",       "[人物J]", False),
    ("ルミさん",   "[人物J]さん", False),
    ("ルミちゃん", "[人物J]ちゃん", False),
    ("るみさん",   "[人物J]さん", False),
    ("るみちゃん", "[人物J]ちゃん", False),
    ("ルミ",       "[人物J]", False),

    # ── 久良良 ──
    ("久良良", "[人物K]", False),

    # ── 浜マ ──
    ("浜マ", "[人物L]", False),

    # ── 苗字（人物M〜V） ──
    ("松田",   "[人物M]", False),
    ("木村",   "[人物N]", False),
    ("戸谷",   "[人物O]", False),
    ("山中",   "[人物P]", False),
    ("岩佐",   "[人物Q]", False),
    ("松崎",   "[人物R]", False),
    ("渡辺",   "[人物S]", False),
    ("渡邊",   "[人物S]", False),
    ("高田",   "[人物T]", False),
    ("髙田",   "[人物T]", False),
    ("智子",   "[人物U]", False),
    ("直美",   "[人物V]", False),

    # ── 神社メッセージ固有の人名 ──
    ("安室",     "[人物Y]", False),
    ("大森",     "[人物Z]", False),
    ("斎藤",     "[人物K]", False),
    ("斉藤",     "[人物K]", False),
    ("稲山",     "[人物AA]", False),
    ("島根",     "[人物AB]", False),
    ("高須",     "[人物AC]", False),
    ("堀川",     "[人物AD]", False),
    ("角谷",     "[人物AE]", False),
    ("丸山",     "[人物AF]", False),
    ("佐藤",     "[人物AG]", False),
    ("仲村",     "[人物AH]", False),
    ("宇都宮",   "[人物AI]", False),
    ("尼留",     "[人物AJ]", False),
    ("樽川",     "[人物AK]", False),
    ("巫",       "[人物AL]", False),
    ("片瀨",     "[人物J]", False),
    ("片瀬",     "[人物J]", False),
    ("守屋",     "[人物AM]", False),
    ("安食",     "[人物AN]", False),
    ("小内",     "[人物AO]", False),
    ("札野",     "[人物AP]", False),
]

# 実際の神社名リスト（人名と区別するため）
KNOWN_SHRINES = {
    "三峯神社", "富士山本宮浅間大社", "新屋山神社", "武蔵御嶽神社",
    "有鹿神社", "寒川神社", "東国三社", "鹿島神宮", "香取神宮", "息栖神社",
    "北口本宮冨士浅間神社", "湯島天満宮", "神田明神", "愛宕神社",
    "浅草神社", "今戸神社", "戸隠神社", "川越氷川神社",
    "赤城神社", "石楯尾神社", "宮山神社",
    # 戸隠五社
    "奥社", "中社", "宝光社", "火之御子社", "九頭龍社", "九頭龍神社",
}

# 神社パーツ（部分一致用）
SHRINE_SUFFIXES = ("神社", "大社", "神宮", "天満宮", "明神", "奥社", "中社", "宝光社", "火之御子社")


def is_shrine_name(name):
    """神社名かどうか判定"""
    if name in KNOWN_SHRINES:
        return True
    # ビジネスメッセージ付き
    clean = re.sub(r'\s*[\(（].*?[\)）]', '', name)
    if clean in KNOWN_SHRINES:
        return True
    if any(name.endswith(s) for s in SHRINE_SUFFIXES):
        return True
    if any(clean.endswith(s) for s in SHRINE_SUFFIXES):
        return True
    return False


def mask_text(text):
    for pattern, replacement, use_regex in MASK_RULES:
        if use_regex:
            text = re.sub(pattern, replacement, text)
        else:
            text = text.replace(pattern, replacement)
    return text


def normalize_shrine_name(name):
    """神社名を正規化し、神様名を抽出"""
    name = name.strip()
    deity = ""
    note = ""
    # 括弧内を解析
    m = re.search(r'[\(（]\s*(.+?)\s*[\)）]', name)
    if m:
        inner = m.group(1)
        base = re.sub(r'\s*[\(（].*?[\)）]', '', name).strip()
        # 神様名かビジネスか判定
        if inner == "ビジネス":
            note = "ビジネス"
        elif any(k in inner for k in ("命", "神", "尊", "大明神", "天照", "比女", "比売")):
            deity = inner
        else:
            note = inner
        name = base
    return name, deity, note


def parse_docx(filepath):
    """docxファイルを解析して神社ごとのメッセージを抽出"""
    doc = docx.Document(str(filepath))
    paragraphs = [p.text for p in doc.paragraphs]

    # ファイル名から回数と日付を取得
    fname = filepath.stem
    event_info = fname

    entries = []  # [{shrine, deity, person, message, commentary, event_info}]

    # 区切り線以降が詳細解説部分
    separator_idx = None
    for i, text in enumerate(paragraphs):
        if "┈" in text or "━" in text or "───" in text or ("*" * 10) in text:
            separator_idx = i
            break

    # 一覧部分（separator前）と詳細部分（separator後）を分けて処理
    if separator_idx is None:
        detail_paras = paragraphs
    else:
        detail_paras = paragraphs[separator_idx + 1:]

    # ファイル名から神社名を推定（＜人名＞形式のファイル用）
    default_shrine = ""
    m_fname = re.search(r'【(.+?)】', event_info)
    if m_fname:
        default_shrine = m_fname.group(1)
    elif "三峯" in event_info:
        default_shrine = "三峯神社"
    elif "有鹿" in event_info:
        default_shrine = "有鹿神社"
    elif "神田明神" in event_info and "赤城" in event_info:
        default_shrine = "神田明神＆赤城神社"
    elif "神田明神" in event_info:
        default_shrine = "神田明神"

    # 詳細部分を解析
    current_person = ""
    current_shrine = ""
    current_deity = ""
    current_shrine_note = ""
    current_message = ""
    current_commentary = []

    def flush():
        nonlocal current_person, current_shrine, current_deity, current_message, current_commentary
        if current_shrine and (current_message or current_commentary):
            entries.append({
                "shrine": current_shrine,
                "deity": current_deity,
                "shrine_note": current_shrine_note,
                "person": mask_text(current_person),
                "message": current_message,
                "commentary": mask_text("\n".join(current_commentary).strip()),
                "event_info": event_info,
            })
        current_commentary = []
        current_message = ""

    for text in detail_paras:
        text = text.strip()
        if not text:
            continue

        # 人名行: ◇名前 or 名前さん（タブ付き）
        if text.startswith("◇"):
            flush()
            current_person = re.sub(r'^◇\s*', '', text).strip()
            current_shrine = ""
            current_deity = ""
            current_message = ""
            continue

        # 直接人名行（タブ区切りの名前、区切り線後のパターン）
        person_match = re.match(r'^(.+?さん)\s*$', text)
        if person_match and len(text) < 30 and not any(k in text for k in ("神社", "大社", "神宮", "天満宮")):
            flush()
            current_person = person_match.group(1).strip()
            # ＜人名＞形式のファイルでは神社名をdefaultから取る
            if default_shrine and not current_shrine:
                current_shrine = default_shrine
            else:
                current_shrine = ""
            current_deity = ""
            current_message = ""
            continue

        # 神社名行: ＜神社名＞ or <神社名> or ＜神社名(神様名)＞
        m = re.match(r'[＜<](.+?)[＞>]', text)
        if m:
            candidate = m.group(1)
            if is_shrine_name(candidate):
                flush()
                current_shrine, current_deity, current_shrine_note = normalize_shrine_name(candidate)
                rest = text[m.end():].strip()
                if rest:
                    current_message = rest
                continue
            # ＜人名＞形式の場合
            elif "さん" in candidate:
                flush()
                current_person = candidate
                if default_shrine:
                    current_shrine = default_shrine
                current_deity = ""
                current_message = ""
                continue

        # 括弧内の神様名だけの行（有鹿神社ファイルのパターン）
        deity_match = re.match(r'^[\(（]\s*(.+?)\s*[\)）]$', text)
        if deity_match and current_shrine:
            inner = deity_match.group(1)
            if any(k in inner for k in ("命", "神", "尊", "大明神", "天照", "比女", "比売")):
                current_deity = inner
                continue

        # 【メッセージ】形式
        msg_match = re.match(r'^【(.+?)】$', text)
        if msg_match and current_shrine and not current_message:
            current_message = msg_match.group(1)
            continue

        # メッセージ本文行（神社名の直後で、タケさんの解説ではない行）
        if current_shrine and not current_message and not text.startswith("[人物G]") and "：" not in text[:10]:
            current_message = text
            continue

        # 解説部分
        if current_shrine:
            current_commentary.append(text)

    flush()

    return entries


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SHRINE_MSG_DIR.exists():
        print(f"エラー: {SHRINE_MSG_DIR} が見つかりません")
        sys.exit(1)

    # 重複除去: (1) 付きファイルをスキップ、特殊ファイルもスキップ
    docx_files = []
    for f in sorted(SHRINE_MSG_DIR.glob("*.docx")):
        if "(1)" in f.name:
            continue
        if "全て" in f.name or "全員" in f.name:
            continue
        if "堀川" in f.name:
            continue
        docx_files.append(f)

    print(f"対象docxファイル: {len(docx_files)} 件")

    # 全ファイルから抽出
    all_entries = []
    for f in docx_files:
        entries = parse_docx(f)
        all_entries.extend(entries)
        print(f"  {f.name}: {len(entries)} エントリ")

    print(f"\n全エントリ: {len(all_entries)} 件")

    # 不正エントリ除外（神社名が長すぎるor明らかに誤抽出）
    valid_entries = []
    for entry in all_entries:
        shrine = entry["shrine"]
        if len(shrine) > 15:
            continue
        if "お守り" in shrine or "仲良い" in shrine or "笑" in shrine or "プレゼント" in shrine or "神様達" in entry.get("deity", ""):
            continue
        if not entry["message"] and not entry["commentary"]:
            continue
        valid_entries.append(entry)
    all_entries = valid_entries
    print(f"有効エントリ: {len(all_entries)} 件")

    # 神様ごと（神様名がわかれば神様、わからなければ神社）にグループ化
    by_deity = defaultdict(list)
    for entry in all_entries:
        if entry["deity"]:
            key = f"{entry['deity']}（{entry['shrine']}）"
        else:
            key = entry["shrine"]
        by_deity[key].append(entry)

    print(f"神様/神社数: {len(by_deity)}")

    # 神様/神社ごとにMDファイル生成
    for deity_key in sorted(by_deity.keys()):
        entries = by_deity[deity_key]
        safe_name = deity_key.replace("/", "／")
        filepath = OUTPUT_DIR / f"{safe_name}.md"

        # タイトル生成
        sample = entries[0]
        if sample["deity"]:
            title = f"{sample['deity']}（{sample['shrine']}）"
            subtitle = f"{sample['shrine']}の神様「{sample['deity']}」から受け取ったメッセージとその解説。全{len(entries)}件。"
        else:
            title = f"{sample['shrine']}"
            subtitle = f"{sample['shrine']}の神様から受け取ったメッセージとその解説。全{len(entries)}件。"

        # タグ情報
        all_shrines = sorted(set(e["shrine"] for e in entries))
        all_deities = sorted(set(e["deity"] for e in entries if e["deity"]))

        lines = [f"# {title} — 神社メッセージ", ""]
        lines.append(subtitle)
        lines.append("")
        lines.append("**タグ:**")
        for s in all_shrines:
            lines.append(f"- 神社: {s}")
        for d in all_deities:
            lines.append(f"- 神様: {d}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for entry in entries:
            person = entry["person"]
            message = entry["message"]
            commentary = entry["commentary"]
            event = mask_text(entry["event_info"])
            note = entry.get("shrine_note", "")
            deity = entry.get("deity", "")

            lines.append(f"## {person}")
            # エントリ単位のタグ
            tag_parts = [f"神社: {entry['shrine']}"]
            if deity:
                tag_parts.append(f"神様: {deity}")
            if note:
                tag_parts.append(f"備考: {note}")
            lines.append(f"*{' / '.join(tag_parts)}*")
            lines.append("")
            if message:
                lines.append(f"> {message}")
                lines.append("")
            if commentary:
                lines.append(commentary)
                lines.append("")
            lines.append(f"**出典：** {event}")
            lines.append("")
            lines.append("---")
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        print(f"  ✓ {safe_name}.md ({len(entries)} 件)")

    print(f"\n出力先: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

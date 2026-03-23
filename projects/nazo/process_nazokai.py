#!/usr/bin/env python3
"""
謎の会 HTMLファイル → フィラー除去 + PIIマスク → MD出力
"""

import re
import os
from pathlib import Path
from html.parser import HTMLParser

INPUT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = INPUT_DIR / "output_md"

# ── フィラー除去パターン ──
# 単独フィラー（行全体がフィラーのみの場合は行ごと削除）
FILLER_ONLY_PATTERNS = [
    r"^うん。$", r"^うん$", r"^はい。$", r"^はい$",
    r"^ああ。$", r"^ああ$", r"^ええ。$", r"^ええ$",
    r"^へえ。$", r"^へえ$", r"^ふーん。$", r"^ふーん$",
    r"^なるほど。$", r"^なるほど$",
    r"^そうですね。$", r"^そうですね$",
    r"^うんうん。$", r"^うんうん$",
    r"^はいはい。$", r"^はいはい$",
    r"^はいはいはい。$", r"^はいはいはい$",
    r"^うん。うん。$", r"^うん。うん。うん。$",
]
FILLER_ONLY_RE = [re.compile(p) for p in FILLER_ONLY_PATTERNS]

# インラインフィラー（文中から除去）
INLINE_FILLERS = [
    (r"えっと、?\s*", ""),
    (r"えーっと、?\s*", ""),
    (r"あのー?、?\s*", ""),
    (r"まあ、?\s*", ""),
    (r"ま、\s*", ""),
    (r"なんか、?\s*", ""),
    (r"こう、?\s*", ""),
    (r"ほら、?\s*", ""),
    (r"ね、\s*", ""),
    (r"(?:うん。\s*){2,}", ""),  # 連続うん
    (r"(?:はい。\s*){2,}", ""),  # 連続はい
]
INLINE_FILLER_RE = [(re.compile(p), r) for p, r in INLINE_FILLERS]

# ── マスクルール（genプロジェクト準拠） ──
MASK_RULES = [
    # 施設
    ("囲炉裏",     "[施設A]",     False),
    ("Dream",      "[施設B]",     False),
    ("ワープ",     "[施設C]",     False),

    # 場所
    ("亀戸",       "[場所A]",     False),
    ("錦糸町",     "[場所B]",     False),
    ("亀戸文化センター", "[場所A]文化センター", False),

    # しんちゃん
    ("しんちゃん", "[人物E]", False),

    # 玄本人（タケ/竹/竹尾）
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

    # 美穂
    ("みほ",   "[人物A]", False),
    ("ミホ",   "[人物A]", False),
    ("美穂",   "[人物A]", False),

    # 満美
    ("まみ",   "[人物B]", False),
    ("マミ",   "[人物B]", False),
    ("満美",   "[人物B]", False),

    # 麻貴
    ("まき",   "[人物C]", False),
    ("マキ",   "[人物C]", False),
    ("麻貴",   "[人物C]", False),

    # カレン
    ("かれん", "[人物D]", False),
    ("カレン", "[人物D]", False),

    # クラッチ/倉田
    ("くらっち",  "[人物F]", False),
    ("クラッチ",  "[人物F]", False),
    ("倉田",      "[人物F]", False),
    ("倉っち",    "[人物F]", False),
    ("クラッチー","[人物F]", False),
    ("クラチー",  "[人物F]", False),
    ("クラさん",  "[人物F]さん", False),
    ("倉さん",    "[人物F]さん", False),

    # ムロ・室
    ("室さん",   "[人物H]さん", False),
    ("室くん",   "[人物H]くん", False),
    ("室ちゃん", "[人物H]ちゃん", False),
    ("むろ",     "[人物H]", False),
    ("ムロ",     "[人物H]", False),

    # カズ
    ("カズさん",   "[人物I]さん", False),
    ("カズくん",   "[人物I]くん", False),
    ("カズちゃん", "[人物I]ちゃん", False),
    ("カズ君",     "[人物I]君", False),
    ("かずさん",   "[人物I]さん", False),
    ("かずくん",   "[人物I]くん", False),
    ("かずちゃん", "[人物I]ちゃん", False),
    ("かず君",     "[人物I]君", False),
    (r"カズ(?!レーザー)", "[人物I]", True),

    # ルミ・留美
    ("留美",       "[人物J]", False),
    ("ルミコ",     "[人物J]コ", False),
    ("るみこ",     "[人物J]こ", False),
    ("ルミさん",   "[人物J]さん", False),
    ("ルミちゃん", "[人物J]ちゃん", False),
    ("るみさん",   "[人物J]さん", False),
    ("るみちゃん", "[人物J]ちゃん", False),
    ("ルミ",       "[人物J]", False),

    # 久良良
    ("久良良", "[人物K]", False),

    # 浜マ
    ("浜マ", "[人物L]", False),

    # 苗字
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

    # 追加: HTMLファイルに出現する名前
    ("まどか",   "[人物W]", False),
    ("マドカ",   "[人物W]", False),
    ("小屋",     "[人物X]", False),
]

# ── ファイル名マスクルール ──
# 長い・具体的なパターンを先に処理（二重マスク防止）
FILENAME_MASK_RULES = [
    ("Shink U", "運営"),
    ("ShinkU", "運営"),
    ("ShinkUmtg", "運営MTG"),
    ("タケ宅", "[人物G]宅"),
    ("亀戸文化センター", "[場所A]文化センター"),
    ("亀戸", "[場所A]"),
    ("錦糸町", "[場所B]"),
]


class HTMLTextExtractor(HTMLParser):
    """HTMLからテキストを抽出"""
    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self._current = []
        self._in_p = False
        self._in_h = False
        self._tag = ""

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self._in_p = True
            self._current = []
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_h = True
            self._tag = tag
            self._current = []

    def handle_endtag(self, tag):
        if tag == "p" and self._in_p:
            self._in_p = False
            text = "".join(self._current).strip()
            if text:
                self.paragraphs.append(("p", text))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._in_h:
            self._in_h = False
            text = "".join(self._current).strip()
            if text:
                level = int(tag[1])
                self.paragraphs.append(("h", (level, text)))

    def handle_data(self, data):
        if self._in_p or self._in_h:
            self._current.append(data)


def mask_text(text: str) -> str:
    for pattern, replacement, use_regex in MASK_RULES:
        if use_regex:
            text = re.sub(pattern, replacement, text)
        else:
            text = text.replace(pattern, replacement)
    return text


def remove_fillers(text: str) -> str:
    for regex in FILLER_ONLY_RE:
        if regex.match(text):
            return ""
    for regex, repl in INLINE_FILLER_RE:
        text = regex.sub(repl, text)
    return text.strip()


def mask_filename(name: str) -> str:
    for pattern, replacement in FILENAME_MASK_RULES:
        name = name.replace(pattern, replacement)
    return name


def process_file(html_path: Path) -> str:
    content = html_path.read_text(encoding="utf-8")
    extractor = HTMLTextExtractor()
    extractor.feed(content)

    lines = []
    for typ, data in extractor.paragraphs:
        if typ == "h":
            level, text = data
            text = mask_text(text)
            lines.append(f"{'#' * level} {text}")
            lines.append("")
        elif typ == "p":
            text = mask_text(data)
            text = remove_fillers(text)
            if text:
                lines.append(text)
                lines.append("")

    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    html_files = sorted(INPUT_DIR.glob("*.html"))
    print(f"対象HTMLファイル: {len(html_files)} 件")

    for html_path in html_files:
        stem = html_path.stem
        # .pdf.html や .mp3.html → 元の拡張子を除去
        for ext in [".mp3", ".m4a", ".pdf", ".m4a のコピー", ".MP3 のコピー"]:
            if stem.endswith(ext):
                stem = stem[:-len(ext)]
                break

        masked_stem = mask_filename(stem)
        out_path = OUTPUT_DIR / f"{masked_stem}.md"

        md_content = process_file(html_path)

        # 空行の連続を最大1つに
        md_content = re.sub(r"\n{3,}", "\n\n", md_content)

        out_path.write_text(md_content, encoding="utf-8")
        print(f"  ✓ {html_path.name} → {out_path.name}")

    print(f"\n完了: {len(html_files)} ファイル → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

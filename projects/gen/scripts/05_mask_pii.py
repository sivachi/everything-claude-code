#!/usr/bin/env python3
"""
05_mask_pii.py
==============
GEN (玄) RAGパイプライン — PII・固有名詞マスク処理

対象ファイル:
  output/chunks.jsonl  （text / source_file / context_turns フィールド）

マスクマップ:
  [施設A]     = 囲炉裏
  [施設B]     = Dream
  [施設C]     = ワープ
  [イベントA] = 謎会
  [人物A]     = 美穂・みほ・ミホ
  [人物B]     = 満美・まみ・マミ
  [人物C]     = 麻貴・まき・マキ
  [人物D]     = カレン・かれん
  [人物E]     = しんちゃん
  [人物F]     = クラッチ・くらっち・倉田・倉っち・クラさん・倉さん
  [人物G]     = タケ・たけ・竹・竹尾（玄本人）
  [人物H]     = ムロ・むろ・室さん/くん/ちゃん
  [人物I]     = カズ・かず（さん/くん/ちゃん/君 付き）
  [人物J]     = ルミ・るみ・留美
  [人物K]     = 久良良
  [人物L]     = 浜マ
  [人物M]     = 松田
  [人物N]     = 木村
  [人物O]     = 戸谷
  [人物P]     = 山中
  [人物Q]     = 岩佐
  [人物R]     = 松崎
  [人物S]     = 渡辺・渡邊
  [人物T]     = 高田・髙田
  [人物U]     = 智子
  [人物V]     = 直美

使用方法:
  python3 scripts/05_mask_pii.py [--dry-run]
"""

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_DIR    = Path("/Users/tadaakikurata/works/claude-code/projects/gen")
CHUNKS_FILE = BASE_DIR / "output" / "chunks.jsonl"
BACKUP_FILE = BASE_DIR / "output" / "chunks_backup.jsonl"

# ─────────────────────────────────────────────────────────
# マスクルール定義
#   (pattern, replacement, use_regex)
#   ※ 長い・具体的なパターンを先に処理すること
# ─────────────────────────────────────────────────────────
MASK_RULES = [
    # ── 施設・サービス・イベント名 ─────────────────────
    ("囲炉裏",     "[施設A]",     False),
    ("Dream",      "[施設B]",     False),
    ("ワープ",     "[施設C]",     False),
    ("謎会",       "[イベントA]", False),

    # ── しんちゃん（しん単独は一般語のため複合語のみ） ─
    ("しんちゃん", "[人物E]", False),

    # ── 玄本人（タケ/竹/竹尾） ─────────────────────────
    # フルネーム・複合を先に処理してから単独を処理
    ("竹尾",        "[人物G]", False),
    ("たけちゃん",  "[人物G]", False),
    ("タケちゃん",  "[人物G]", False),
    ("竹ちゃん",    "[人物G]", False),
    ("たけさん",    "[人物G]さん", False),
    ("タケさん",    "[人物G]さん", False),
    ("竹さん",      "[人物G]さん", False),
    # たけ単独：「たけど」「たけれど」「たけのこ」は除外
    (r"たけ(?!ど|れど|のこ)", "[人物G]", True),
    # タケ単独：タケハラ（地名）は除外
    (r"タケ(?!ハラ)", "[人物G]", True),
    # 竹単独：竹尾は処理済み、竹林・竹の子・竹刀・竹串・竹馬・竹べらなどは除外
    (r"竹(?!林|の子|ノコ|刀|串|馬|べら|内|島|下|中)", "[人物G]", True),

    # ── 美穂（みほ） ──────────────────────────────────
    ("みほ",   "[人物A]", False),
    ("ミホ",   "[人物A]", False),
    ("美穂",   "[人物A]", False),

    # ── 満美（まみ） ──────────────────────────────────
    ("まみ",   "[人物B]", False),
    ("マミ",   "[人物B]", False),
    ("満美",   "[人物B]", False),

    # ── 麻貴（まき） ──────────────────────────────────
    ("まき",   "[人物C]", False),
    ("マキ",   "[人物C]", False),
    ("麻貴",   "[人物C]", False),

    # ── カレン（かれん） ──────────────────────────────
    ("かれん", "[人物D]", False),
    ("カレン", "[人物D]", False),

    # ── クラッチ/倉田（くらっち/倉田） ───────────────
    # 長いパターンを先に処理
    ("くらっち",  "[人物F]", False),
    ("クラッチ",  "[人物F]", False),
    ("倉田",      "[人物F]", False),
    ("倉っち",    "[人物F]", False),
    ("クラさん",  "[人物F]さん", False),
    ("倉さん",    "[人物F]さん", False),

    # ── ムロ・室 ──────────────────────────────────────
    # さん/くん/ちゃん付きを先に（保持したほうが自然）
    ("室さん",   "[人物H]さん", False),
    ("室くん",   "[人物H]くん", False),
    ("室ちゃん", "[人物H]ちゃん", False),
    ("むろ",     "[人物H]", False),
    ("ムロ",     "[人物H]", False),

    # ── カズ ──────────────────────────────────────────
    # 「かず」単独は誤検知が多いのでさん/くん/ちゃん/君付きのみ
    ("カズさん",   "[人物I]さん", False),
    ("カズくん",   "[人物I]くん", False),
    ("カズちゃん", "[人物I]ちゃん", False),
    ("カズ君",     "[人物I]君", False),
    ("かずさん",   "[人物I]さん", False),
    ("かずくん",   "[人物I]くん", False),
    ("かずちゃん", "[人物I]ちゃん", False),
    ("かず君",     "[人物I]君", False),
    # カタカナ単独（カズレーザー等の有名人は除外）
    (r"カズ(?!レーザー)", "[人物I]", True),

    # ── ルミ・留美 ─────────────────────────────────────
    ("留美",       "[人物J]", False),
    ("ルミさん",   "[人物J]さん", False),
    ("ルミちゃん", "[人物J]ちゃん", False),
    ("るみさん",   "[人物J]さん", False),
    ("るみちゃん", "[人物J]ちゃん", False),
    ("ルミ",       "[人物J]", False),  # カタカナ単独

    # ── 久良良 ─────────────────────────────────────────
    ("久良良", "[人物K]", False),

    # ── 浜マ ───────────────────────────────────────────
    ("浜マ", "[人物L]", False),

    # ── 苗字（人物M〜T） ──────────────────────────────
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

    # ── 智子・直美 ─────────────────────────────────────
    ("智子",   "[人物U]", False),
    ("直美",   "[人物V]", False),
]


def mask_text(text: str) -> tuple:
    """テキストにマスクルールを適用。変更件数も返す。"""
    counts = {}
    for pattern, replacement, use_regex in MASK_RULES:
        if use_regex:
            new_text, n = re.subn(pattern, replacement, text)
        else:
            n = text.count(pattern)
            new_text = text.replace(pattern, replacement)
        if n > 0:
            counts[pattern] = counts.get(pattern, 0) + n
        text = new_text
    return text, counts


def mask_context_turns(turns: list) -> list:
    """context_turns リスト内のテキストもマスク（文字列・辞書両対応）"""
    masked = []
    for turn in turns:
        if isinstance(turn, dict):
            t = turn.copy()
            if "text" in t:
                t["text"], _ = mask_text(t["text"])
            masked.append(t)
        elif isinstance(turn, str):
            # 文字列要素（"user: ..." 等）も処理
            masked.append(mask_text(turn)[0])
        else:
            masked.append(turn)
    return masked


def main():
    parser = argparse.ArgumentParser(description="PII・固有名詞マスク処理")
    parser.add_argument("--dry-run", action="store_true", help="件数確認のみ（書き換えなし）")
    args = parser.parse_args()

    # バックアップから復元（元データで毎回再処理 → 二重マスク防止）
    if BACKUP_FILE.exists():
        shutil.copy2(BACKUP_FILE, CHUNKS_FILE)
        print(f"バックアップから復元: {BACKUP_FILE} → {CHUNKS_FILE}")
    else:
        # バックアップがなければ現ファイルを新たにバックアップ
        shutil.copy2(CHUNKS_FILE, BACKUP_FILE)
        print(f"バックアップ作成: {BACKUP_FILE}")

    lines = CHUNKS_FILE.read_text(encoding="utf-8").splitlines()
    total_stats: dict = {}
    masked_lines = []
    modified_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        chunk = json.loads(line)
        changed = False

        # ── text フィールドをマスク ──
        original_text = chunk.get("text", "")
        masked_text, stats = mask_text(original_text)
        if masked_text != original_text:
            changed = True
        chunk["text"] = masked_text

        # ── source_file フィールドをマスク（ファイル名の固有名詞） ──
        if "source_file" in chunk:
            original_src = chunk["source_file"]
            masked_src, src_stats = mask_text(original_src)
            if masked_src != original_src:
                changed = True
                chunk["source_file"] = masked_src
                for k, v in src_stats.items():
                    stats[k] = stats.get(k, 0) + v

        # ── context_turns フィールドをマスク（文字列・辞書両対応） ──
        if "context_turns" in chunk and chunk["context_turns"]:
            original_turns = chunk["context_turns"]
            masked_turns = mask_context_turns(original_turns)
            if masked_turns != original_turns:
                changed = True
            chunk["context_turns"] = masked_turns

        # 統計集計
        for k, v in stats.items():
            total_stats[k] = total_stats.get(k, 0) + v

        if changed:
            modified_count += 1
        masked_lines.append(json.dumps(chunk, ensure_ascii=False))

    # ── 統計表示 ──
    print("\n" + "=" * 60)
    print("【マスク処理 統計】")
    print(f"  対象チャンク: {len(masked_lines):,} 件")
    print(f"  変更チャンク: {modified_count:,} 件")
    print()
    print("  置換パターン別件数:")
    for pattern, replacement, _ in MASK_RULES:
        n = total_stats.get(pattern, 0)
        if n > 0:
            disp = pattern if len(pattern) <= 12 else pattern[:12] + "..."
            print(f"    {disp:18s} → {replacement:14s} : {n:,} 件")
    print("=" * 60)

    if args.dry_run:
        print("\n[dry-run] 書き換えは行いませんでした")
        # dry-run なので復元したファイルを元に戻す
        shutil.copy2(BACKUP_FILE, CHUNKS_FILE)
        return

    # ── 書き込み ──
    CHUNKS_FILE.write_text("\n".join(masked_lines) + "\n", encoding="utf-8")
    print(f"\n書き込み完了: {CHUNKS_FILE}")
    print("次のステップ: python3 scripts/03_index.py --rebuild")


if __name__ == "__main__":
    main()

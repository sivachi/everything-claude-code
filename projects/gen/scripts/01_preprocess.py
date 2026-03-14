#!/usr/bin/env python3
"""
01_preprocess.py
================
GEN (玄) RAGパイプライン — ステップ1: HTMLセッション書き起こしの前処理

概要:
  258本のHTMLファイル（音声書き起こし）を3タイプに分類し、
  適切なチャンキング戦略でJSONL形式に変換する。

タイプ分類:
  speaker_dialogue  : 「竹尾さん：」等の話者ラベルあり対話 → GENターン抽出 (文脈付き)
  unlabeled_audio   : 話者ラベルなし音声書き起こし → 段落結合チャンキング
  document          : 神社メッセージ等の文書形式 → セクション段落チャンキング

出力:
  /Users/tadaakikurata/works/ai_takeo_local/output/chunks.jsonl
  /Users/tadaakikurata/works/ai_takeo_local/output/preprocess_stats.json

チャンク形式 (JSONL 1行 = 1チャンク):
  {
    "chunk_id"          : "uuid4",
    "source_file"       : "ファイル名.html",
    "file_type"         : "speaker_dialogue|unlabeled_audio|document",
    "text"              : "チャンク本文",
    "char_count"        : 412,
    "is_gen_turn"       : true|false|null,   # speaker_dialogueのみ true/false
    "context_turns"     : ["前の発話1", ...], # speaker_dialogueのみ
    "session_date"      : "2024-08-02",      # ファイル名から抽出 (取得できた場合)
    "chunk_index"       : 0,                  # ファイル内での連番
  }

使用方法:
  python3 01_preprocess.py [--dry-run] [--resume] [--verbose]

オプション:
  --dry-run   : 実際のファイル書き込みをせず統計のみ表示
  --resume    : 既存のchunks.jsonlがあれば処理済みファイルをスキップ
  --verbose   : 各ファイルの処理状況を詳細表示
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
SOURCES_DIR = Path(
    "/Users/tadaakikurata/works/ai_takeo/AI竹尾プロジェクト(人格コピー)/Sources"
)
OUTPUT_DIR = Path("/Users/tadaakikurata/works/ai_takeo_local/output")
OUTPUT_JSONL = OUTPUT_DIR / "chunks.jsonl"
OUTPUT_STATS = OUTPUT_DIR / "preprocess_stats.json"

# ─────────────────────────────────────────────
# チャンキング設定
# ─────────────────────────────────────────────
MIN_LINE_CHARS = 25          # これ未満の行はフィラーとして除去
TARGET_CHUNK_CHARS = 400     # 目標チャンク文字数
MAX_CHUNK_CHARS = 600        # これを超えたら強制分割
CONTEXT_TURNS = 3            # speaker_dialogue: GENターン前に含める発話数

# ─────────────────────────────────────────────
# 話者ラベルのパターン
# ─────────────────────────────────────────────
# GENを示すラベル (竹尾さん / タケさん / タケ / 竹 / 竹尾)
GEN_SPEAKER_PATTERNS = [
    r"^竹尾さん[：:]",
    r"^タケさん[：:]",
    r"^タケ[：:]",
    r"^竹[：:]",
    r"^竹尾[：:]",
]

# 話者ラベル全般を検出するパターン (名前 + 全角/半角コロン)
SPEAKER_LABEL_RE = re.compile(r"^([^：:\n。、]{1,15})[：:](.+)")
GEN_LABEL_RE = re.compile("|".join(GEN_SPEAKER_PATTERNS))

# 日付をファイル名から抽出するパターン
DATE_RE = re.compile(
    r"(\d{4})[-_/]?(\d{2})[-_/]?(\d{2})"  # YYYYMMDD / YYYY-MM-DD
    r"|(\d{6})"                              # YYMMDD
)


# ─────────────────────────────────────────────
# ユーティリティ関数
# ─────────────────────────────────────────────

def extract_date_from_filename(filename: str) -> Optional[str]:
    """ファイル名から日付文字列を抽出 (例: 20240802 → "2024-08-02")"""
    m = DATE_RE.search(filename)
    if not m:
        return None
    if m.group(1):  # YYYYMMDD / YYYY-MM-DD 形式
        y, mo, d = m.group(1), m.group(2), m.group(3)
        try:
            dt = datetime(int(y), int(mo), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
    if m.group(4):  # YYMMDD 形式
        s = m.group(4)
        if len(s) == 6:
            try:
                y = int("20" + s[:2])
                mo = int(s[2:4])
                d = int(s[4:6])
                dt = datetime(y, mo, d)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def parse_html_paragraphs(html_path: Path) -> List[str]:
    """HTMLファイルから <p> タグのテキストを抽出し、正規化して返す"""
    with open(html_path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(separator=" ").strip()
        # 改行文字を空白に統一
        text = re.sub(r"[\r\n\x0b\x0c]+", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def is_filler(text: str) -> bool:
    """フィラー発話（あいづち等）を判定"""
    if len(text) < MIN_LINE_CHARS:
        return True
    # 短い相槌パターン
    filler_patterns = [
        r"^(うん|はい|ええ|そう|なるほど|ああ|おお|へえ|ふん)[。。\s]*$",
        r"^[笑（）\s]+$",
    ]
    for pat in filler_patterns:
        if re.match(pat, text):
            return True
    return False


def detect_file_type(paragraphs) -> str:
    """
    ファイルタイプを判定:
      speaker_dialogue  : GENの話者ラベル(竹尾さん：等)が存在する
      document          : 対話でない文書(神社メッセージ等) — ◇ や ★ マークが多い
      unlabeled_audio   : それ以外の話者ラベルなし音声書き起こし
    """
    # 先頭50段落をサンプリング
    sample = paragraphs[:50]

    # GENラベルを持つ段落が1件以上 → speaker_dialogue
    gen_count = sum(1 for p in sample if GEN_LABEL_RE.match(p))
    if gen_count > 0:
        return "speaker_dialogue"

    # 文書マーカー (◇ ★ ◎ ＜ など) の密度が高い → document
    doc_markers = sum(
        1 for p in sample if re.match(r"^[◇◎★☆＜〈【《]", p)
    )
    if doc_markers >= 3:
        return "document"

    return "unlabeled_audio"


# ─────────────────────────────────────────────
# チャンキング戦略
# ─────────────────────────────────────────────

def chunk_speaker_dialogue(
    paragraphs: List[str],
    source_file: str,
    session_date: Optional[str],
) -> List[dict]:
    """
    話者ラベルあり対話: GENのターンを特定し、前のCONTEXT_TURNS発話を文脈として付加する。
    GENでない発話もチャンクとして保存する（RAGで「どんな質問にGENが答えたか」の文脈として有用）。
    """
    chunks = []

    # (speaker_label, text) のタプルリストに変換
    turns: List[Tuple[str, str]] = []
    for p in paragraphs:
        m = SPEAKER_LABEL_RE.match(p)
        if m:
            speaker = m.group(1).strip()
            text = m.group(2).strip()
            if text:
                turns.append((speaker, text))
        else:
            # ラベルなし発話は直前のターンに追記
            if turns and p and not is_filler(p):
                prev_speaker, prev_text = turns[-1]
                turns[-1] = (prev_speaker, prev_text + "　" + p)
            elif p and not is_filler(p):
                turns.append(("unknown", p))

    chunk_idx = 0
    for i, (speaker, text) in enumerate(turns):
        is_gen = bool(GEN_LABEL_RE.match(speaker + "："))

        # 文脈ターン (GENターンの前 CONTEXT_TURNS 発話)
        context = []
        if is_gen and i > 0:
            start = max(0, i - CONTEXT_TURNS)
            for j in range(start, i):
                sp, tx = turns[j]
                context.append(f"{sp}：{tx}")

        full_text = text
        if len(full_text) < MIN_LINE_CHARS:
            continue

        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "source_file": source_file,
            "file_type": "speaker_dialogue",
            "text": full_text,
            "char_count": len(full_text),
            "is_gen_turn": is_gen,
            "context_turns": context,
            "session_date": session_date,
            "chunk_index": chunk_idx,
        })
        chunk_idx += 1

    return chunks


def chunk_paragraphs(
    paragraphs: List[str],
    source_file: str,
    file_type: str,
    session_date: Optional[str],
) -> List[dict]:
    """
    話者ラベルなし音声書き起こし / 文書:
    段落を結合して TARGET_CHUNK_CHARS 前後のチャンクを作る。
    MAX_CHUNK_CHARS を超える段落は単独でチャンクにする。
    """
    # フィラー除去
    clean_paras = [p for p in paragraphs if not is_filler(p)]

    chunks = []
    chunk_idx = 0
    current_parts: List[str] = []
    current_len = 0

    def flush():
        nonlocal current_parts, current_len, chunk_idx
        if not current_parts:
            return
        text = "　".join(current_parts)
        if len(text) >= MIN_LINE_CHARS:
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "source_file": source_file,
                "file_type": file_type,
                "text": text,
                "char_count": len(text),
                "is_gen_turn": None,
                "context_turns": [],
                "session_date": session_date,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1
        current_parts = []
        current_len = 0

    for para in clean_paras:
        para_len = len(para)

        # 単体で MAX を超える → 単独チャンク
        if para_len > MAX_CHUNK_CHARS:
            flush()
            # 長い段落を MAX_CHUNK_CHARS で分割
            for start in range(0, para_len, MAX_CHUNK_CHARS):
                segment = para[start : start + MAX_CHUNK_CHARS]
                if len(segment) >= MIN_LINE_CHARS:
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "source_file": source_file,
                        "file_type": file_type,
                        "text": segment,
                        "char_count": len(segment),
                        "is_gen_turn": None,
                        "context_turns": [],
                        "session_date": session_date,
                        "chunk_index": chunk_idx,
                    })
                    chunk_idx += 1
            continue

        # 結合後に TARGET を超えるなら flush してから追加
        if current_len + para_len > TARGET_CHUNK_CHARS and current_parts:
            flush()

        current_parts.append(para)
        current_len += para_len

        # TARGET に達したら flush
        if current_len >= TARGET_CHUNK_CHARS:
            flush()

    flush()  # 残余
    return chunks


# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

def process_file(html_path: Path) -> Tuple[List[dict], str]:
    """1ファイルを処理してチャンクリストとファイルタイプを返す"""
    filename = html_path.name
    session_date = extract_date_from_filename(filename)

    paragraphs = parse_html_paragraphs(html_path)
    if not paragraphs:
        return [], "empty"

    file_type = detect_file_type(paragraphs)

    if file_type == "speaker_dialogue":
        chunks = chunk_speaker_dialogue(paragraphs, filename, session_date)
    else:
        chunks = chunk_paragraphs(paragraphs, filename, file_type, session_date)

    return chunks, file_type


def main():
    parser = argparse.ArgumentParser(description="GEN RAG前処理: HTML → chunks.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="書き込みせず統計のみ表示")
    parser.add_argument("--resume", action="store_true", help="処理済みファイルをスキップ")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細ログ表示")
    args = parser.parse_args()

    # HTMLファイル一覧取得
    html_files = sorted(SOURCES_DIR.glob("*.html"))
    total_files = len(html_files)
    print(f"[01_preprocess] 対象ファイル数: {total_files}")

    if not html_files:
        print("ERROR: HTMLファイルが見つかりません。パスを確認してください。")
        print(f"  SOURCES_DIR = {SOURCES_DIR}")
        sys.exit(1)

    # resumeモード: 処理済みファイルを記録したセットを構築
    processed_files: set[str] = set()
    if args.resume and OUTPUT_JSONL.exists():
        print(f"[resume] 既存チャンクファイルを読み込み中: {OUTPUT_JSONL}")
        with open(OUTPUT_JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    processed_files.add(obj.get("source_file", ""))
                except json.JSONDecodeError:
                    pass
        print(f"[resume] 処理済みファイル数: {len(processed_files)}")

    # 統計カウンタ
    stats = {
        "total_files": total_files,
        "processed_files": 0,
        "skipped_files": 0,
        "file_types": {"speaker_dialogue": 0, "unlabeled_audio": 0, "document": 0, "empty": 0},
        "total_chunks": 0,
        "gen_turn_chunks": 0,
        "non_gen_chunks": 0,
        "unlabeled_chunks": 0,
        "total_chars": 0,
        "avg_chunk_chars": 0,
        "processed_at": datetime.now().isoformat(),
    }

    # 出力ファイルオープン (resumeなら追記、それ以外は上書き)
    write_mode = "a" if args.resume else "w"
    out_fh = None
    if not args.dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_fh = open(OUTPUT_JSONL, write_mode, encoding="utf-8")

    try:
        for i, html_path in enumerate(html_files, 1):
            filename = html_path.name

            # skip if already processed
            if args.resume and filename in processed_files:
                stats["skipped_files"] += 1
                if args.verbose:
                    print(f"  [{i:3d}/{total_files}] SKIP: {filename}")
                continue

            chunks, file_type = process_file(html_path)
            stats["file_types"][file_type] = stats["file_types"].get(file_type, 0) + 1
            stats["processed_files"] += 1
            stats["total_chunks"] += len(chunks)

            for chunk in chunks:
                stats["total_chars"] += chunk["char_count"]
                if chunk["is_gen_turn"] is True:
                    stats["gen_turn_chunks"] += 1
                elif chunk["is_gen_turn"] is False:
                    stats["non_gen_chunks"] += 1
                else:
                    stats["unlabeled_chunks"] += 1

                if not args.dry_run and out_fh:
                    out_fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

            if args.verbose:
                print(
                    f"  [{i:3d}/{total_files}] {file_type:20s} | {len(chunks):4d} chunks | {filename}"
                )
            elif i % 50 == 0 or i == total_files:
                print(f"  進捗: {i}/{total_files} ファイル処理済み ({stats['total_chunks']} チャンク)")

    finally:
        if out_fh:
            out_fh.close()

    # 平均チャンク文字数
    if stats["total_chunks"] > 0:
        stats["avg_chunk_chars"] = round(stats["total_chars"] / stats["total_chunks"])

    # 統計出力
    print("\n" + "=" * 60)
    print("【前処理 完了】")
    print(f"  処理ファイル数  : {stats['processed_files']} / {total_files}")
    print(f"  スキップ        : {stats['skipped_files']}")
    print(f"  ファイルタイプ  : {stats['file_types']}")
    print(f"  総チャンク数    : {stats['total_chunks']}")
    print(f"    GENターン     : {stats['gen_turn_chunks']}")
    print(f"    非GENターン   : {stats['non_gen_chunks']}")
    print(f"    ラベルなし    : {stats['unlabeled_chunks']}")
    print(f"  平均チャンク長  : {stats['avg_chunk_chars']} 文字")
    if not args.dry_run:
        print(f"  出力先          : {OUTPUT_JSONL}")
    print("=" * 60)

    if not args.dry_run:
        with open(OUTPUT_STATS, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"  統計ファイル    : {OUTPUT_STATS}")

    return stats


if __name__ == "__main__":
    main()

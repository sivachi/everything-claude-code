#!/usr/bin/env python3
"""
01_chunk.py — ソースファイル（MD + TXT + GEN HTML）をトピック単位でチャンク化し chunks.jsonl に出力

処理内容:
  - output_md/イベント/*.md と output_md/運営・コンサル/*.md を読み込み
  - 録音データ/*.txt（whisper文字起こし）を読み込み
  - GENプロジェクトのソースHTML（projects/gen/sources/Sources/*.html）を読み込み
  - トピック区切り（見出し / 空行連続 / 話題転換）でチャンク分割
  - 各チャンクにメタデータ（source_file, chunk_id, source_type）を付与
  - output/chunks.jsonl に出力

使用方法:
  python3 scripts/01_chunk.py [--include-gen]
"""

import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

PROJECT_DIR = Path(__file__).resolve().parent.parent
GEN_SOURCES_DIR = PROJECT_DIR.parent / "gen" / "sources" / "Sources"
OUTPUT_DIR = PROJECT_DIR / "output"
CHUNKS_FILE = OUTPUT_DIR / "chunks.jsonl"

# チャンク最小文字数（短すぎるチャンクは前のチャンクに統合）
MIN_CHUNK_LEN = 50
# チャンク最大文字数（超えたら分割）
MAX_CHUNK_LEN = 2000


class HTMLTextExtractor(HTMLParser):
    """HTMLからテキストを抽出（process_nazokai.pyと同等）"""
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


def html_to_text(html_content):
    """HTMLコンテンツをプレーンテキストに変換"""
    extractor = HTMLTextExtractor()
    extractor.feed(html_content)
    lines = []
    for typ, data in extractor.paragraphs:
        if typ == "h":
            level, text = data
            lines.append(f"{'#' * level} {text}")
            lines.append("")
        elif typ == "p":
            lines.append(data)
            lines.append("")
    return "\n".join(lines)


def read_gen_html_files():
    """GENプロジェクトのソースHTMLを読み込む"""
    sources = []
    if not GEN_SOURCES_DIR.exists():
        print(f"  警告: GENソースディレクトリが見つかりません: {GEN_SOURCES_DIR}")
        return sources
    for html_path in sorted(GEN_SOURCES_DIR.glob("*.html")):
        try:
            content = html_path.read_text(encoding="utf-8")
            text = html_to_text(content)
            if text.strip():
                sources.append({
                    "file": f"GEN:{html_path.name}",
                    "text": text,
                    "source_type": "GENソース",
                })
        except Exception as e:
            print(f"  エラー: {html_path.name}: {e}")
    return sources


def read_md_files():
    """output_md配下のMDファイルを読み込む"""
    sources = []
    for subdir in ["イベント", "運営・コンサル", "神社メッセージ"]:
        md_dir = PROJECT_DIR / "output_md" / subdir
        if not md_dir.exists():
            continue
        for md_path in sorted(md_dir.glob("*.md")):
            # スピリチュアル分類.md や 運営・コンサルでのスピリチュアルQA.md は除外
            if "スピリチュアル" in md_path.name:
                continue
            text = md_path.read_text(encoding="utf-8")
            sources.append({
                "file": md_path.name,
                "text": text,
                "source_type": subdir,
            })
    return sources


def read_txt_files():
    """録音データ配下のTXTファイルを読み込む"""
    sources = []
    txt_dir = PROJECT_DIR / "録音データ"
    if not txt_dir.exists():
        return sources
    for txt_path in sorted(txt_dir.glob("*.txt")):
        text = txt_path.read_text(encoding="utf-8")
        sources.append({
            "file": txt_path.name,
            "text": text,
            "source_type": "録音文字起こし",
        })
    return sources


def chunk_md(text, source_file, source_type):
    """MDテキストをトピック単位でチャンク化"""
    chunks = []
    current_lines = []
    current_heading = ""

    for line in text.split("\n"):
        # 見出し行で区切る
        if re.match(r"^#{1,4}\s+", line):
            # 今までのバッファをチャンクに
            if current_lines:
                chunk_text = "\n".join(current_lines).strip()
                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "heading": current_heading,
                    })
            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # 残り
    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "heading": current_heading,
            })

    # 短いチャンクを統合
    merged = []
    for chunk in chunks:
        if merged and len(chunk["text"]) < MIN_CHUNK_LEN:
            merged[-1]["text"] += "\n\n" + chunk["text"]
        else:
            merged.append(chunk)

    # 長いチャンクを分割
    final = []
    for chunk in merged:
        if len(chunk["text"]) > MAX_CHUNK_LEN:
            parts = split_long_chunk(chunk["text"], MAX_CHUNK_LEN)
            for i, part in enumerate(parts):
                final.append({
                    "text": part,
                    "heading": chunk["heading"],
                })
        else:
            final.append(chunk)

    # メタデータ付与
    result = []
    for i, chunk in enumerate(final):
        result.append({
            "chunk_id": f"{source_file}_{i:04d}",
            "source_file": source_file,
            "source_type": source_type,
            "heading": chunk["heading"],
            "text": chunk["text"],
            "char_count": len(chunk["text"]),
        })
    return result


def chunk_txt(text, source_file, source_type):
    """TXTテキスト（whisper文字起こし）をチャンク化"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    chunks = []
    current_lines = []
    current_len = 0

    for line in lines:
        current_lines.append(line)
        current_len += len(line)

        # 一定量たまったら区切る
        if current_len >= 800:
            chunk_text = "\n".join(current_lines).strip()
            chunks.append({
                "text": chunk_text,
                "heading": "",
            })
            current_lines = []
            current_len = 0

    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if chunk_text and len(chunk_text) >= MIN_CHUNK_LEN:
            chunks.append({
                "text": chunk_text,
                "heading": "",
            })
        elif chunk_text and chunks:
            chunks[-1]["text"] += "\n" + chunk_text

    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "chunk_id": f"{source_file}_{i:04d}",
            "source_file": source_file,
            "source_type": source_type,
            "heading": chunk["heading"],
            "text": chunk["text"],
            "char_count": len(chunk["text"]),
        })
    return result


def split_long_chunk(text, max_len):
    """長いテキストを段落区切りで分割"""
    paragraphs = text.split("\n\n")
    parts = []
    current = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_len and current:
            parts.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        parts.append("\n\n".join(current))

    return parts


def main():
    include_gen = "--include-gen" in sys.argv
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_chunks = []

    # MDファイル処理
    md_sources = read_md_files()
    print(f"MDファイル: {len(md_sources)} 件")
    for src in md_sources:
        chunks = chunk_md(src["text"], src["file"], src["source_type"])
        all_chunks.extend(chunks)
        print(f"  {src['file']}: {len(chunks)} チャンク")

    # TXTファイル処理
    txt_sources = read_txt_files()
    print(f"\nTXTファイル（文字起こし）: {len(txt_sources)} 件")
    for src in txt_sources:
        chunks = chunk_txt(src["text"], src["file"], src["source_type"])
        all_chunks.extend(chunks)
        print(f"  {src['file']}: {len(chunks)} チャンク")

    # GENソースHTML処理
    if include_gen:
        gen_sources = read_gen_html_files()
        print(f"\nGENソースHTML: {len(gen_sources)} 件")
        for src in gen_sources:
            chunks = chunk_md(src["text"], src["file"], src["source_type"])
            all_chunks.extend(chunks)
            print(f"  {src['file']}: {len(chunks)} チャンク")
    else:
        print("\n※ GENソースを含めるには --include-gen オプションを指定")

    # 出力
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\n合計: {len(all_chunks)} チャンク → {CHUNKS_FILE}")

    # 統計
    stats = {
        "total_chunks": len(all_chunks),
        "md_files": len(md_sources),
        "txt_files": len(txt_sources),
        "avg_char_count": sum(c["char_count"] for c in all_chunks) // max(len(all_chunks), 1),
        "by_source_type": {},
    }
    for chunk in all_chunks:
        st = chunk["source_type"]
        stats["by_source_type"][st] = stats["by_source_type"].get(st, 0) + 1

    stats_file = OUTPUT_DIR / "chunk_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"統計 → {stats_file}")


if __name__ == "__main__":
    main()

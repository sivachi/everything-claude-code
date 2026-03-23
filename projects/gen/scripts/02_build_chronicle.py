#!/usr/bin/env python3
"""
02_build_chronicle.py
======================
GEN (玄) RAGパイプライン — ステップ2: Chronicle Graph 構築

概要:
  玄_在り方.md から Chronicle Graph を解析・構築し、
  RAGアプリ（04_app.py）が使いやすい形式で保存する。

入力:
  /Users/tadaakikurata/works/claude-code/projects/gen/玄_在り方.md

出力:
  output/chronicle_graph.json   — グラフ全体（ノード + エッジ + メタデータ）
  output/chronicle_sections.json — 全セクション（番号・タイトル・本文・関連エッジ）
  output/chronicle_full_text.txt  — システムプロンプト用の在り方フルテキスト

chronicle_graph.json 構造:
  {
    "entity": "GEN",
    "nodes": [
      {"id": "...", "edge_type": "believes"},
      ...
    ],
    "edges": [
      {"source": "GEN", "target": "...", "type": "believes"},
      ...
    ],
    "edge_type_labels": {
      "believes":          "信念 — GENが深く信じる世界観・原則",
      "values":            "価値観 — GENが優先する判断基準・行動指針",
      "rejects":           "拒絶 — GENが明確に否定・警戒するもの",
      "diagnoses_via":     "診断法 — 相手・状況を読み解くレンズ",
      "communicates_using":"伝達法 — GENが使うコミュニケーション技法",
      "practices":         "実践法 — GENが日常で実践する具体的行動"
    },
    "metadata": { "total_nodes": ..., "total_edges": ..., ... }
  }

chronicle_sections.json 構造:
  [
    {
      "section_id": "1.1",
      "chapter": 1,
      "chapter_title": "魂のシステムと根源的死生観",
      "title": "死後の「反省会」と300年の後悔",
      "content": "...",
      "edge_candidates": [
        {"type": "believes", "target": "今この瞬間にしか挑戦できない"},
        ...
      ],
      "is_new": false      # ★NEW が付いていれば true
    },
    ...
  ]

使用方法:
  python3 02_build_chronicle.py [--verbose]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
ARKATA_MD = Path("/Users/tadaakikurata/works/claude-code/projects/gen/玄_在り方.md")
OUTPUT_DIR = Path("/Users/tadaakikurata/works/claude-code/projects/gen/output")
OUTPUT_GRAPH    = OUTPUT_DIR / "chronicle_graph.json"
OUTPUT_SECTIONS = OUTPUT_DIR / "chronicle_sections.json"
OUTPUT_FULLTEXT = OUTPUT_DIR / "chronicle_full_text.txt"

# エッジタイプの日本語ラベル（app表示・プロンプト用）
EDGE_TYPE_LABELS: Dict[str, str] = {
    "believes":           "信念 — GENが深く信じる世界観・原則",
    "values":             "価値観 — GENが優先する判断基準・行動指針",
    "rejects":            "拒絶 — GENが明確に否定・警戒するもの",
    "diagnoses_via":      "診断法 — 相手・状況を読み解くレンズ",
    "communicates_using": "伝達法 — GENが使うコミュニケーション技法",
    "practices":          "実践法 — GENが日常で実践する具体的行動",
}

# ─────────────────────────────────────────────
# 正規表現
# ─────────────────────────────────────────────
# セクションヘッダー: "### 1.1 タイトル" / "### 2.7 タイトル ★NEW"
SECTION_H3_RE  = re.compile(
    r"^###\s+(\d+\.\d+)\s+(.+?)(?:\s+★(?:NEW|v4\.0拡充))?\s*$"
)
# チャプターヘッダー: "## 1. 魂のシステムと根源的死生観"
CHAPTER_H2_RE  = re.compile(r"^##\s+(\d+)\.\s+(.+)")
# Chapter 0 専用: "## 0. タイトル"
CHAPTER0_RE    = re.compile(r"^##\s+0\.\s+(.+)")
# Chronicle エッジ候補ブロック内の行: "(GEN, type, target)"
EDGE_CAND_RE   = re.compile(
    r"\(GEN\s*,\s*(\w+)\s*,\s*(.+?)\s*\)"
)
# Chronicle Graph JSON ブロック開始
CG_SECTION_RE  = re.compile(r"^##\s+Chronicle Graph")
# ★NEW マーカー
NEW_MARKER_RE  = re.compile(r"★(?:NEW|v4\.0拡充)")


# ─────────────────────────────────────────────
# パーサー: Chronicle Graph JSON抽出
# ─────────────────────────────────────────────

def extract_chronicle_json(lines: List[str]) -> dict:
    """
    在り方.md の Chronicle Graph セクションから JSON ブロックを抽出してパース。
    Returns the parsed dict {"entity": "GEN", "edges": [...]}
    """
    in_cg_section = False
    in_json_block = False
    json_lines: List[str] = []

    for line in lines:
        stripped = line.rstrip()
        if CG_SECTION_RE.match(stripped):
            in_cg_section = True
            continue
        if in_cg_section:
            if stripped == "```json":
                in_json_block = True
                continue
            if in_json_block:
                if stripped == "```":
                    break  # JSON ブロック終了
                json_lines.append(stripped)

    if not json_lines:
        raise ValueError("Chronicle Graph の ```json ブロックが見つかりませんでした")

    return json.loads("\n".join(json_lines))


# ─────────────────────────────────────────────
# パーサー: セクション抽出
# ─────────────────────────────────────────────

def parse_sections(lines: List[str]) -> List[dict]:
    """
    在り方.md から全セクションを解析して返す。

    Returns list of section dicts:
    {
        "section_id": "1.1",
        "chapter": 1,
        "chapter_title": "...",
        "title": "...",
        "content": "...",
        "edge_candidates": [{"type": "...", "target": "..."}, ...],
        "is_new": bool
    }
    """
    sections: List[dict] = []
    current_section: Optional[dict] = None
    current_chapter_num: int = 0
    current_chapter_title: str = ""
    current_content_lines: List[str] = []
    in_edge_block = False
    in_cg_section = False

    def flush_section():
        nonlocal current_section, current_content_lines
        if current_section is None:
            return
        # コンテンツ整形
        content = "\n".join(current_content_lines).strip()
        # Chronicle エッジ候補ブロックを content から除去
        content = re.sub(
            r"\*\*Chronicle エッジ候補:\*\*\s*```.*?```",
            "",
            content,
            flags=re.DOTALL,
        ).strip()
        current_section["content"] = content
        sections.append(current_section)
        current_section = None
        current_content_lines = []

    for line in lines:
        stripped = line.rstrip()

        # Chronicle Graph セクションに入ったら終了
        if CG_SECTION_RE.match(stripped):
            in_cg_section = True
            flush_section()
            break

        # ブラッシュアップ履歴に入ったら終了
        if stripped.startswith("## ブラッシュアップ履歴"):
            flush_section()
            break

        # チャプター（## N. タイトル）
        m_ch = CHAPTER_H2_RE.match(stripped)
        if m_ch:
            flush_section()
            current_chapter_num = int(m_ch.group(1))
            raw_title = m_ch.group(2)
            current_chapter_title = NEW_MARKER_RE.sub("", raw_title).strip()
            in_edge_block = False
            continue

        # Chapter 0 の本文（## 0. ...）はすでに CHAPTER_H2_RE でキャッチされる
        # チャプター副題（### ― ... ―）はスキップ
        if stripped.startswith("### ―") or stripped.startswith("### ※"):
            continue

        # サブセクション（### N.M タイトル）
        m_sec = SECTION_H3_RE.match(stripped)
        if m_sec:
            flush_section()
            sec_id = m_sec.group(1)
            raw_title = stripped[4:].strip()  # "### " を取り除いた全体
            is_new = bool(NEW_MARKER_RE.search(raw_title))
            clean_title = NEW_MARKER_RE.sub("", m_sec.group(2)).strip()
            clean_title = re.sub(r"\s+★.*", "", clean_title).strip()
            current_section = {
                "section_id": sec_id,
                "chapter": current_chapter_num,
                "chapter_title": current_chapter_title,
                "title": clean_title,
                "content": "",
                "edge_candidates": [],
                "is_new": is_new,
            }
            current_content_lines = []
            in_edge_block = False
            continue

        # Chapter 0 は section_id "0" として扱う
        if current_chapter_num == 0 and current_section is None:
            if stripped and not stripped.startswith("#"):
                # Chapter 0 の本文を単一セクションとして収集
                # (既存セクション flush 済みなので、初回だけ作成)
                if current_section is None:
                    current_section = {
                        "section_id": "0",
                        "chapter": 0,
                        "chapter_title": current_chapter_title,
                        "title": current_chapter_title,
                        "content": "",
                        "edge_candidates": [],
                        "is_new": False,
                    }
                    current_content_lines = []

        if current_section is None:
            continue

        # Chronicle エッジ候補ブロック
        if "**Chronicle エッジ候補:**" in stripped:
            in_edge_block = True
            current_content_lines.append(stripped)
            continue

        if in_edge_block:
            # コードブロック終了
            if stripped == "```" and current_content_lines and "```" in current_content_lines[-3:]:
                in_edge_block = False
            # エッジ候補を解析
            for m in EDGE_CAND_RE.finditer(stripped):
                edge_type = m.group(1).strip()
                target = m.group(2).strip()
                current_section["edge_candidates"].append(
                    {"type": edge_type, "target": target}
                )
            current_content_lines.append(stripped)
            continue

        current_content_lines.append(stripped)

    flush_section()
    return sections


# ─────────────────────────────────────────────
# グラフ構築
# ─────────────────────────────────────────────

def build_graph(chronicle_json: dict, sections: List[dict]) -> dict:
    """
    Chronicle JSON + sections から グラフ構造を構築して返す。

    Returns:
    {
        "entity": "GEN",
        "nodes": [...],
        "edges": [...],
        "edge_type_labels": {...},
        "metadata": {...}
    }
    """
    edges = chronicle_json.get("edges", [])

    # 全ターゲットノードを収集
    nodes = [{"id": "GEN", "edge_type": None}]
    seen_targets = set()
    for edge in edges:
        tgt = edge["target"]
        if tgt not in seen_targets:
            nodes.append({"id": tgt, "edge_type": edge["type"]})
            seen_targets.add(tgt)

    # エッジにソースを明示
    graph_edges = [
        {"source": "GEN", "target": e["target"], "type": e["type"]}
        for e in edges
    ]

    # セクションとエッジのマッピング（target → 関連セクション）
    target_to_sections: Dict[str, List[str]] = {}
    for sec in sections:
        for ec in sec.get("edge_candidates", []):
            t = ec["target"]
            if t not in target_to_sections:
                target_to_sections[t] = []
            target_to_sections[t].append(sec["section_id"])

    # ノードに関連セクションを付加
    for node in nodes:
        if node["id"] != "GEN":
            node["related_sections"] = target_to_sections.get(node["id"], [])

    # 統計
    edge_type_counter = Counter(e["type"] for e in edges)

    metadata = {
        "version": "4.0",
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "edge_type_counts": dict(edge_type_counter),
        "total_sections": len(sections),
    }

    return {
        "entity": "GEN",
        "nodes": nodes,
        "edges": graph_edges,
        "edge_type_labels": EDGE_TYPE_LABELS,
        "target_to_sections": target_to_sections,
        "metadata": metadata,
    }


# ─────────────────────────────────────────────
# システムプロンプト用フルテキスト生成
# ─────────────────────────────────────────────

def build_full_text(lines: List[str]) -> str:
    """
    在り方.md から Chronicle Graph セクション以降を除いた
    システムプロンプト用フルテキストを生成する。

    除去対象:
      - ``` ... ``` コードブロック（Chronicle エッジ候補定義）
      - **Chronicle エッジ候補:** ラベル行
      - バックチック行 (```)
    """
    clean_lines: List[str] = []
    in_code_block = False
    EDGE_LABEL_RE = re.compile(r"^\*\*Chronicle エッジ候補")

    for line in lines:
        stripped = line.rstrip()

        # Chronicle Graph セクション以降はスキップ
        if CG_SECTION_RE.match(stripped):
            break

        # Chronicle エッジ候補ラベル行をスキップ
        if EDGE_LABEL_RE.match(stripped):
            continue

        # バックチック行 → コードブロックトグル、行自体は出力しない
        if stripped.strip() in ("```json", "```", "```  "):
            in_code_block = not in_code_block
            continue

        # コードブロック内（エッジ定義行）はスキップ
        if in_code_block:
            continue

        clean_lines.append(stripped)

    # 連続する空行を1行に圧縮
    result_lines: List[str] = []
    prev_blank = False
    for l in clean_lines:
        is_blank = l.strip() == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(l)
        prev_blank = is_blank

    return "\n".join(result_lines).strip()


# ─────────────────────────────────────────────
# クエリインデックス構築
# ─────────────────────────────────────────────

def build_query_index(graph: dict, sections: List[dict]) -> dict:
    """
    エッジターゲット文字列を形態素レベルで分解した
    簡易キーワード → エッジ のインデックスを生成する。
    （形態素解析なし: 文字列を2-gramで分割して索引化）

    Returns: { "bigram": [edge_indices...], ... }
    """
    # bigram インデックス
    bigram_index: Dict[str, List[int]] = {}
    for i, edge in enumerate(graph["edges"]):
        text = edge["target"]
        # 2-gram
        for j in range(len(text) - 1):
            bg = text[j : j + 2]
            if bg not in bigram_index:
                bigram_index[bg] = []
            bigram_index[bg].append(i)

    return {
        "bigram": bigram_index,
        "edges": graph["edges"],  # インデックス参照用
    }


# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Chronicle Graph 構築: 在り方.md → JSON出力"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細ログ")
    args = parser.parse_args()

    if not ARKATA_MD.exists():
        print(f"ERROR: 在り方.md が見つかりません: {ARKATA_MD}")
        sys.exit(1)

    print(f"[02_build_chronicle] 入力: {ARKATA_MD}")

    # ファイル読み込み
    with open(ARKATA_MD, encoding="utf-8") as f:
        lines = f.readlines()

    print(f"  行数: {len(lines)}")

    # 1. Chronicle Graph JSON 抽出
    print("\n[1/4] Chronicle Graph JSON を抽出中...")
    chronicle_json = extract_chronicle_json(lines)
    edge_count = len(chronicle_json.get("edges", []))
    print(f"  エッジ数: {edge_count}")

    # 2. セクション解析
    print("\n[2/4] セクションを解析中...")
    sections = parse_sections(lines)
    print(f"  セクション数: {len(sections)}")
    if args.verbose:
        for sec in sections:
            edge_c = len(sec.get("edge_candidates", []))
            new_mark = " ★NEW" if sec["is_new"] else ""
            print(f"    §{sec['section_id']} {sec['title']}{new_mark} (エッジ候補: {edge_c})")

    # 3. グラフ構築
    print("\n[3/4] グラフを構築中...")
    graph = build_graph(chronicle_json, sections)
    meta = graph["metadata"]
    print(f"  ノード数: {meta['total_nodes']}")
    print(f"  エッジ数: {meta['total_edges']}")
    print(f"  エッジタイプ別:")
    for et, cnt in meta["edge_type_counts"].items():
        label = EDGE_TYPE_LABELS.get(et, et)
        print(f"    {et:20s}: {cnt:3d}  ({label[:20]}...)")

    # 4. フルテキスト生成
    print("\n[4/4] システムプロンプト用フルテキストを生成中...")
    full_text = build_full_text(lines)
    print(f"  文字数: {len(full_text):,}")

    # 出力
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # chronicle_graph.json
    with open(OUTPUT_GRAPH, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"\n  → {OUTPUT_GRAPH}")

    # chronicle_sections.json
    with open(OUTPUT_SECTIONS, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
    print(f"  → {OUTPUT_SECTIONS}")

    # chronicle_full_text.txt
    with open(OUTPUT_FULLTEXT, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"  → {OUTPUT_FULLTEXT}")

    # ─── サマリー ───
    print("\n" + "=" * 60)
    print("【Chronicle Graph 構築 完了】")
    print(f"  エッジ数         : {meta['total_edges']}")
    print(f"  ノード数         : {meta['total_nodes']}")
    print(f"  セクション数     : {len(sections)}")
    print(f"    うち NEW追加   : {sum(1 for s in sections if s['is_new'])}")
    print(f"  フルテキスト長   : {len(full_text):,} 文字")

    # エッジタイプ別サマリー
    print("\n  [エッジタイプ別カウント]")
    for et, cnt in meta["edge_type_counts"].items():
        bar = "█" * min(cnt, 40)
        print(f"  {et:20s} {cnt:3d} {bar}")

    print("=" * 60)

    return graph, sections


if __name__ == "__main__":
    main()

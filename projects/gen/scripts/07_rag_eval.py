#!/usr/bin/env python3
"""
07_rag_eval.py
==============
RAG精度比較テスト — 改善前 vs 改善後

テスト項目:
  1. RRFのみ vs RRF + リランキング → スコア分散・上位関連性
  2. bigram Chronicle vs ベクトル Chronicle → エッジ関連性
  3. チャンク単体 vs 文脈拡張チャンク → 情報量
  4. プロファイルなし vs あり → プロンプト差分

使用方法:
  python3 07_rag_eval.py
"""

import json
import re
import sys
import time
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from typing import List, Dict
from statistics import mean

import numpy as np

BASE_DIR = Path("/Users/tadaakikurata/works/claude-code/projects/gen")
CHROMA_DIR = BASE_DIR / "output" / "chroma_db"
CHUNKS_FILE = BASE_DIR / "output" / "chunks.jsonl"
GRAPH_FILE = BASE_DIR / "output" / "chronicle_graph.json"
REPORT_JSON = BASE_DIR / "output" / "rag_eval_report.json"
REPORT_MD = BASE_DIR / "output" / "rag_eval_report.md"

# ─────────────────────────────────────────────
# テストクエリ（多様なテーマ）
# ─────────────────────────────────────────────
TEST_CASES = [
    {"query": "愛とは何ですか？", "keywords": ["愛", "受容", "思いやり", "関係"]},
    {"query": "人間関係で大切にしていることは？", "keywords": ["人間関係", "相手", "信頼", "関わり"]},
    {"query": "仕事や生き方についてどう考えていますか？", "keywords": ["仕事", "生き方", "選択", "使命"]},
    {"query": "辛いときにどうやって乗り越えますか？", "keywords": ["辛い", "乗り越え", "不安", "挑戦"]},
    {"query": "自分を変えたいときに何が必要ですか？", "keywords": ["変化", "成長", "自分", "行動"]},
    {"query": "お金と幸せの関係は？", "keywords": ["お金", "幸せ", "幸福", "与える"]},
    {"query": "子育てで大事なことは？", "keywords": ["子育て", "見守り", "成長", "育てる"]},
    {"query": "魂の成長とは？", "keywords": ["魂", "成長", "進化", "学び"]},
    {"query": "自己肯定感を上げるにはどうすればいい？", "keywords": ["自己肯定感", "自分", "受容", "習慣"]},
    {"query": "不安が強い時に心を整える方法は？", "keywords": ["不安", "心", "整える", "呼吸"]},
    {"query": "夫婦関係を良くするために必要なことは？", "keywords": ["夫婦", "関係", "対話", "信頼"]},
    {"query": "チームで信頼を作るには何が大切ですか？", "keywords": ["チーム", "信頼", "対話", "協力"]},
    {"query": "過去の失敗を引きずらない考え方は？", "keywords": ["失敗", "過去", "学び", "再挑戦"]},
    {"query": "リーダーとしての在り方を教えてください", "keywords": ["リーダー", "在り方", "支える", "責任"]},
    {"query": "挑戦を続けるモチベーションの保ち方は？", "keywords": ["挑戦", "継続", "モチベーション", "目的"]},
    {"query": "本当の幸せを感じるために必要なことは？", "keywords": ["幸せ", "幸福", "心", "バランス"]},
]


def tokenize_ja(text: str) -> List[str]:
    text = re.sub(r'[。、！？!?\s\u3000]+', ' ', text).strip()
    tokens = []
    for part in text.split():
        if len(part) >= 2:
            for i in range(len(part) - 1):
                tokens.append(part[i:i+2])
        if part:
            tokens.append(part)
    return tokens if tokens else [""]


def keyword_relevance(text: str, keywords: List[str]) -> float:
    """テキスト内に期待キーワードがどれだけ含まれるかを0-1で返す。"""
    if not keywords:
        return 0.0
    hit = 0
    for kw in keywords:
        if kw in text:
            hit += 1
    return hit / len(keywords)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """2ベクトルのcosine類似度を返す。"""
    denom = (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)) + 1e-10
    return float(np.dot(vec_a, vec_b) / denom)


def semantic_relevance_scores(ruri_model, query: str, chunks: List[Dict]) -> List[float]:
    """クエリと各チャンクの意味類似度を算出。"""
    if not chunks:
        return []
    query_emb = ruri_model.encode(["クエリ: " + query], convert_to_numpy=True)[0]
    texts = ["文章: " + c.get("text", "")[:1200] for c in chunks]
    text_embs = ruri_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [cosine_similarity(query_emb, emb) for emb in text_embs]


def chronicle_semantic_scores(ruri_model, query: str, edges: List[Dict]) -> List[float]:
    """クエリとChronicleエッジtargetの意味類似度を算出。"""
    if not edges:
        return []
    query_emb = ruri_model.encode(["クエリ: " + query], convert_to_numpy=True)[0]
    targets = ["文章: " + e.get("target", "")[:1200] for e in edges]
    target_embs = ruri_model.encode(targets, convert_to_numpy=True, show_progress_bar=False)
    return [cosine_similarity(query_emb, emb) for emb in target_embs]


def build_markdown_report(summary: Dict, query_metrics: List[Dict]) -> str:
    """評価結果のMarkdownレポートを生成。"""
    lines = [
        "# RAG精度比較レポート",
        "",
        "## 総合サマリー",
        f"- クエリ数: {summary['num_queries']}",
        f"- キーワード適合度 平均: {summary['avg_keyword_old']:.3f} -> {summary['avg_keyword_new']:.3f}",
        f"- 意味類似度 平均: {summary['avg_semantic_old']:.3f} -> {summary['avg_semantic_new']:.3f}",
        f"- RRFスコア分散 平均: {summary['avg_rrf_spread']:.6f}",
        f"- リランクスコア分散 平均: {summary['avg_rerank_spread']:.3f}",
        f"- Chronicle意味類似度 平均: {summary['avg_chronicle_sem_old']:.3f} -> {summary['avg_chronicle_sem_new']:.3f}",
        f"- 文脈拡張率 平均: x{summary['avg_context_expand_ratio']:.2f}",
        "",
        "### 改善クエリ数",
        f"- キーワード適合度改善: {summary['keyword_improved_count']}/{summary['num_queries']}",
        f"- 意味類似度改善: {summary['semantic_improved_count']}/{summary['num_queries']}",
        f"- Chronicle意味類似度改善: {summary['chronicle_sem_improved_count']}/{summary['num_queries']}",
        "",
        "## クエリ別結果",
    ]
    for i, qm in enumerate(query_metrics, 1):
        lines += [
            f"### Q{i}. {qm['query']}",
            f"- キーワード適合度: {qm['keyword_old']:.3f} -> {qm['keyword_new']:.3f}",
            f"- 意味類似度: {qm['semantic_old']:.3f} -> {qm['semantic_new']:.3f}",
            f"- Chronicle意味類似度: {qm['chronicle_sem_old']:.3f} -> {qm['chronicle_sem_new']:.3f}",
            f"- Chronicle hit数(参考): {qm['chronicle_old_hits']} -> {qm['chronicle_new_hits']}",
            f"- 文脈拡張率: x{qm['context_expand_ratio']:.2f}",
            "",
        ]
    return "\n".join(lines)


def main():
    print("=" * 70)
    print("RAG精度比較テスト: 改善前 vs 改善後")
    print("=" * 70)

    # ─── 初期化 ───
    print("\n[初期化]")

    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    print("  ruri-v3-310m ロード中...")
    ruri_model = SentenceTransformer("cl-nagoya/ruri-v3-310m")
    print(f"  ruri-v3 OK ({time.time()-t0:.1f}s)")

    t0 = time.time()
    print("  リランカーロード中...")
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from scripts_06 import load_reranker, rerank, build_chronicle_embeddings, query_chronicle_vector
    from scripts_06 import expand_chunk_context, build_chunk_index_map
    reranker = load_reranker()
    print(f"  リランカー OK ({time.time()-t0:.1f}s)")

    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col_all = client.get_collection("gen_chunks")
    col_hi = client.get_collection("gen_chunks_hi")

    from rank_bm25 import BM25Okapi
    all_chunks = []
    with open(str(CHUNKS_FILE), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    tokenized = [tokenize_ja(c.get("text", "")) for c in all_chunks]
    bm25 = BM25Okapi(tokenized)

    with open(GRAPH_FILE, encoding="utf-8") as f:
        graph = json.load(f)

    # Chronicle embeddingsを構築/キャッシュ
    print("  Chronicle embeddings 構築中...")
    edge_embeddings, edge_list = build_chronicle_embeddings(ruri_model, graph)
    print(f"  Chronicle embeddings OK ({len(edge_list)} edges)")

    # チャンクインデックスマップ構築
    chunk_index_map = build_chunk_index_map(all_chunks)

    print(f"\n  準備完了")
    print(f"  gen_chunks: {col_all.count()} / gen_chunks_hi: {col_hi.count()}")

    # ─── ハイブリッド検索（従来版） ───
    def search_hybrid_old(query, top_k=5, hi_only=True, rrf_k=60):
        query_vec = ruri_model.encode(["クエリ: " + query], convert_to_numpy=True)[0].tolist()
        candidate_n = top_k * 4

        sem_results = []
        hi_res = col_hi.query(query_embeddings=[query_vec], n_results=min(candidate_n, col_hi.count()),
                              include=["documents", "metadatas", "distances"])
        for doc, meta, dist in zip(hi_res["documents"][0], hi_res["metadatas"][0], hi_res["distances"][0]):
            sem_results.append({"text": doc, "source": meta.get("source_file", ""),
                               "distance": dist, "collection": "hi",
                               "is_gen_turn": True, "chunk_id": ""})

        if not hi_only:
            hi_texts = {r["text"] for r in sem_results}
            all_res = col_all.query(query_embeddings=[query_vec], n_results=min(candidate_n, col_all.count()),
                                   include=["documents", "metadatas", "distances"])
            for doc, meta, dist in zip(all_res["documents"][0], all_res["metadatas"][0], all_res["distances"][0]):
                if doc not in hi_texts:
                    sem_results.append({"text": doc, "source": meta.get("source_file", ""),
                                       "distance": dist, "collection": "all",
                                       "is_gen_turn": meta.get("is_gen_turn") == "True", "chunk_id": ""})

        tokenized_query = tokenize_ja(query)
        bm25_scores = bm25.get_scores(tokenized_query)
        top_bm25_idx = bm25_scores.argsort()[::-1][:candidate_n]
        bm25_results = []
        for idx in top_bm25_idx:
            if float(bm25_scores[idx]) <= 0:
                break
            chunk = all_chunks[idx]
            is_gen = chunk.get("is_gen_turn") in (True, "True")
            if hi_only and not is_gen:
                continue
            bm25_results.append({"text": chunk.get("text", ""), "source": chunk.get("source_file", ""),
                                "bm25_score": float(bm25_scores[idx]), "collection": "bm25",
                                "is_gen_turn": is_gen, "chunk_id": chunk.get("chunk_id", "")})

        rrf_scores = {}
        doc_lookup = {}
        for rank, r in enumerate(sem_results):
            t = r["text"]
            rrf_scores[t] = rrf_scores.get(t, 0) + 1 / (rrf_k + rank + 1)
            if t not in doc_lookup:
                doc_lookup[t] = r
        for rank, r in enumerate(bm25_results):
            t = r["text"]
            rrf_scores[t] = rrf_scores.get(t, 0) + 1 / (rrf_k + rank + 1)
            if t not in doc_lookup:
                doc_lookup[t] = r

        sorted_texts = sorted(rrf_scores, key=lambda t: -rrf_scores[t])
        results = []
        for t in sorted_texts:
            entry = doc_lookup[t].copy()
            entry["rrf_score"] = rrf_scores[t]
            results.append(entry)
        return results

    # ─── Chronicle検索（従来版: bigram） ───
    def query_chronicle_old(query, top_n=8):
        edges = graph["edges"]
        query_bigrams = set()
        for i in range(len(query) - 1):
            query_bigrams.add(query[i:i+2])
        scored = []
        for edge in edges:
            target = edge["target"]
            target_bigrams = set()
            for i in range(len(target) - 1):
                target_bigrams.add(target[i:i+2])
            overlap = len(query_bigrams & target_bigrams)
            if overlap > 0:
                scored.append((overlap, edge))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:top_n]]

    # ─── テスト実行 ───
    print("\n" + "=" * 70)
    print("比較テスト開始")
    print("=" * 70)

    metrics: List[Dict] = []

    for qi, test_case in enumerate(TEST_CASES, 1):
        query = test_case["query"]
        expected_keywords = test_case["keywords"]
        print(f"\n{'─' * 70}")
        print(f"Q{qi}: {query}")
        print(f"{'─' * 70}")

        # --- 従来版 ---
        old_results = search_hybrid_old(query, top_k=10, hi_only=True)
        old_top5 = old_results[:5]

        # --- 改善版: リランキング ---
        # RRF上位10件をリランカーで再スコアリング → 上位5件
        new_top5 = rerank(reranker, query, old_results[:10], top_k=5)

        print(f"\n  【チャンク検索: RRFのみ vs RRF+リランキング】")
        print(f"  {'RRFのみ (従来)':40s} | {'RRF+リランク (改善)':40s}")
        print(f"  {'─' * 40} | {'─' * 40}")

        for i in range(5):
            old_text = old_top5[i]["text"][:35].replace("\n", " ") if i < len(old_top5) else ""
            old_score = f"RRF={old_top5[i].get('rrf_score', 0):.5f}" if i < len(old_top5) else ""
            new_text = new_top5[i]["text"][:35].replace("\n", " ") if i < len(new_top5) else ""
            new_score = f"RE={new_top5[i].get('rerank_score', 0):.3f}" if i < len(new_top5) else ""
            print(f"  {i+1}. {old_score} {old_text:30s} | {i+1}. {new_score} {new_text:30s}")

        # スコア分散の比較
        old_scores = [r.get("rrf_score", 0) for r in old_top5]
        new_scores = [r.get("rerank_score", 0) for r in new_top5]
        if old_scores:
            old_spread = max(old_scores) - min(old_scores)
        else:
            old_spread = 0
        if new_scores:
            new_spread = max(new_scores) - min(new_scores)
        else:
            new_spread = 0
        print(f"\n  スコア分散: RRF={old_spread:.6f} → リランク={new_spread:.3f}")

        # 定量評価①: キーワード適合度（top5平均）
        old_kw_scores = [keyword_relevance(r["text"], expected_keywords) for r in old_top5]
        new_kw_scores = [keyword_relevance(r["text"], expected_keywords) for r in new_top5]
        old_kw_avg = mean(old_kw_scores) if old_kw_scores else 0.0
        new_kw_avg = mean(new_kw_scores) if new_kw_scores else 0.0
        print(f"  キーワード適合度(top5平均): {old_kw_avg:.3f} → {new_kw_avg:.3f}")

        # 定量評価②: 意味類似度（ruri cosine）
        old_sem_scores = semantic_relevance_scores(ruri_model, query, old_top5)
        new_sem_scores = semantic_relevance_scores(ruri_model, query, new_top5)
        old_sem_avg = mean(old_sem_scores) if old_sem_scores else 0.0
        new_sem_avg = mean(new_sem_scores) if new_sem_scores else 0.0
        print(f"  意味類似度(top5平均): {old_sem_avg:.3f} → {new_sem_avg:.3f}")

        # --- Chronicle比較 ---
        old_chronicle = query_chronicle_old(query, top_n=5)
        new_chronicle = query_chronicle_vector(ruri_model, query, edge_embeddings, edge_list, top_n=5)
        old_chronicle_sem = chronicle_semantic_scores(ruri_model, query, old_chronicle)
        new_chronicle_sem = chronicle_semantic_scores(ruri_model, query, new_chronicle)
        old_chronicle_sem_avg = mean(old_chronicle_sem) if old_chronicle_sem else 0.0
        new_chronicle_sem_avg = mean(new_chronicle_sem) if new_chronicle_sem else 0.0

        print(f"\n  【Chronicle検索: bigram vs ベクトル】")
        print(f"  {'bigram (従来)':40s} | {'ベクトル (改善)':40s}")
        print(f"  {'─' * 40} | {'─' * 40}")

        for i in range(5):
            old_e = old_chronicle[i]["target"][:35] if i < len(old_chronicle) else ""
            new_e = new_chronicle[i]["target"][:35] if i < len(new_chronicle) else ""
            new_sim = f"sim={new_chronicle[i].get('similarity', 0):.3f}" if i < len(new_chronicle) else ""
            print(f"  {i+1}. {old_e:38s} | {i+1}. {new_sim} {new_e}")
        print(f"  Chronicle意味類似度(top5平均): {old_chronicle_sem_avg:.3f} → {new_chronicle_sem_avg:.3f}")

        # --- 文脈拡張 ---
        if new_top5:
            top_chunk = new_top5[0]
            original_text = top_chunk["text"]

            # chunk_idを探す
            # BM25由来ならchunk_idがある。セマンティック由来ならtextで検索
            chunk_id = top_chunk.get("chunk_id", "")
            if not chunk_id:
                # textから逆引き
                for c in all_chunks:
                    if c.get("text", "") == original_text:
                        chunk_id = c.get("chunk_id", "")
                        top_chunk["chunk_id"] = chunk_id
                        top_chunk["source_file"] = c.get("source_file", "")
                        break

            expanded_text = expand_chunk_context(
                top_chunk, all_chunks, chunk_index_map, window=1
            )

            print(f"\n  【文脈拡張: 1位チャンク】")
            print(f"  元の長さ: {len(original_text)}文字 → 拡張後: {len(expanded_text)}文字")
            context_expand_ratio = len(expanded_text) / max(len(original_text), 1)
            if len(expanded_text) > len(original_text):
                print(f"  → 改善: 前後の文脈が追加され、情報量が{context_expand_ratio:.1f}倍に")
        else:
            context_expand_ratio = 1.0

        # クエリ別メトリクス保存
        metrics.append({
            "query": query,
            "keyword_old": old_kw_avg,
            "keyword_new": new_kw_avg,
            "semantic_old": old_sem_avg,
            "semantic_new": new_sem_avg,
            "rrf_spread": old_spread,
            "rerank_spread": new_spread,
            "chronicle_old_hits": len(old_chronicle),
            "chronicle_new_hits": len(new_chronicle),
            "chronicle_sem_old": old_chronicle_sem_avg,
            "chronicle_sem_new": new_chronicle_sem_avg,
            "context_expand_ratio": context_expand_ratio,
        })

    # ─── サマリー ───
    num_queries = len(metrics)
    avg_keyword_old = mean([m["keyword_old"] for m in metrics]) if metrics else 0.0
    avg_keyword_new = mean([m["keyword_new"] for m in metrics]) if metrics else 0.0
    avg_semantic_old = mean([m["semantic_old"] for m in metrics]) if metrics else 0.0
    avg_semantic_new = mean([m["semantic_new"] for m in metrics]) if metrics else 0.0
    avg_rrf_spread = mean([m["rrf_spread"] for m in metrics]) if metrics else 0.0
    avg_rerank_spread = mean([m["rerank_spread"] for m in metrics]) if metrics else 0.0
    avg_chronicle_old_hits = mean([m["chronicle_old_hits"] for m in metrics]) if metrics else 0.0
    avg_chronicle_new_hits = mean([m["chronicle_new_hits"] for m in metrics]) if metrics else 0.0
    avg_chronicle_sem_old = mean([m["chronicle_sem_old"] for m in metrics]) if metrics else 0.0
    avg_chronicle_sem_new = mean([m["chronicle_sem_new"] for m in metrics]) if metrics else 0.0
    avg_context_expand_ratio = mean([m["context_expand_ratio"] for m in metrics]) if metrics else 1.0

    keyword_improved_count = sum(1 for m in metrics if m["keyword_new"] > m["keyword_old"])
    semantic_improved_count = sum(1 for m in metrics if m["semantic_new"] > m["semantic_old"])
    chronicle_sem_improved_count = sum(1 for m in metrics if m["chronicle_sem_new"] > m["chronicle_sem_old"])

    # プロファイル差分テスト（機能存在確認）
    sample_profile_prompt = build_profile_prompt({
        "name": "テスト太郎",
        "themes": ["仕事", "人間関係"],
        "stage": "変化期",
        "notes": "継続実行を重視",
        "conversation_summary": "前回は自己受容について話した",
        "session_count": 3,
    })
    profile_section_ok = "【この方について（過去のセッション情報）】" in sample_profile_prompt

    summary = {
        "num_queries": num_queries,
        "avg_keyword_old": avg_keyword_old,
        "avg_keyword_new": avg_keyword_new,
        "avg_semantic_old": avg_semantic_old,
        "avg_semantic_new": avg_semantic_new,
        "avg_rrf_spread": avg_rrf_spread,
        "avg_rerank_spread": avg_rerank_spread,
        "avg_chronicle_old_hits": avg_chronicle_old_hits,
        "avg_chronicle_new_hits": avg_chronicle_new_hits,
        "avg_chronicle_sem_old": avg_chronicle_sem_old,
        "avg_chronicle_sem_new": avg_chronicle_sem_new,
        "avg_context_expand_ratio": avg_context_expand_ratio,
        "keyword_improved_count": keyword_improved_count,
        "semantic_improved_count": semantic_improved_count,
        "chronicle_sem_improved_count": chronicle_sem_improved_count,
        "profile_section_ok": profile_section_ok,
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "queries": metrics}, f, ensure_ascii=False, indent=2)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(build_markdown_report(summary, metrics))

    print("\n" + "=" * 70)
    print("【精度比較テスト 完了】")
    print("=" * 70)
    print(f"  キーワード適合度 平均: {avg_keyword_old:.3f} → {avg_keyword_new:.3f}"
          f"  ({keyword_improved_count}/{num_queries}クエリで改善)")
    print(f"  意味類似度 平均:       {avg_semantic_old:.3f} → {avg_semantic_new:.3f}"
          f"  ({semantic_improved_count}/{num_queries}クエリで改善)")
    print(f"  Chronicle意味類似度:   {avg_chronicle_sem_old:.3f} → {avg_chronicle_sem_new:.3f}"
          f"  ({chronicle_sem_improved_count}/{num_queries}クエリで改善)")
    print(f"  Chronicle hit数(参考): {avg_chronicle_old_hits:.2f} → {avg_chronicle_new_hits:.2f}")
    print(f"  文脈拡張率 平均:       x{avg_context_expand_ratio:.2f}")
    print(f"  プロファイル機能確認:  {'OK' if profile_section_ok else 'NG'}")
    print(f"\n  レポート出力:")
    print(f"    - {REPORT_JSON}")
    print(f"    - {REPORT_MD}")


if __name__ == "__main__":
    # モジュールインポートのためsys.pathを調整
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    # 06_rag_improvements.py をインポート可能にする
    import importlib
    spec = importlib.util.spec_from_file_location(
        "scripts_06",
        str(BASE_DIR / "scripts" / "06_rag_improvements.py")
    )
    scripts_06 = importlib.util.module_from_spec(spec)
    sys.modules["scripts_06"] = scripts_06
    spec.loader.exec_module(scripts_06)

    # グローバルにインポートし直す
    from scripts_06 import (
        load_reranker, rerank,
        build_chronicle_embeddings, query_chronicle_vector,
        expand_chunk_context, build_chunk_index_map, build_profile_prompt,
    )

    main()

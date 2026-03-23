#!/usr/bin/env python3
"""
06_rag_improvements.py
======================
RAG精度改善モジュール — 04_app.py から利用する追加機能群

改善内容:
  1. クロスエンコーダーリランキング
     - RRF統合後の候補をクエリとペアで再スコアリング
     - モデル: hotchpotch/japanese-reranker-cross-encoder-xsmall-v1 (日本語特化, ~50MB)
  2. Chronicle Graph ベクトル検索
     - 123エッジのtargetをruri-v3で事前embedding
     - bigram → cosine類似度に置き換え
  3. チャンク文脈拡張（コンテキストウィンドウ）
     - 検索ヒットしたチャンクの前後チャンクを結合して文脈を補完
  4. お客様プロファイル
     - JSON形式で名前・過去テーマ・段階を保持
     - システムプロンプトに差し込み

すべてローカル実行 — ランニングコスト0円
"""

import json
import os
import hashlib
import numpy as np
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR = Path("/Users/tadaakikurata/works/claude-code/projects/gen")
CHRONICLE_EMBEDDINGS_FILE = BASE_DIR / "output" / "chronicle_edge_embeddings.npy"
CHRONICLE_EDGES_FILE = BASE_DIR / "output" / "chronicle_edge_list.json"
CHRONICLE_META_FILE = BASE_DIR / "output" / "chronicle_edge_meta.json"
PROFILES_DIR = BASE_DIR / "profiles"

# リランカーモデル
RERANKER_MODEL = "hotchpotch/japanese-reranker-cross-encoder-xsmall-v1"


# ─────────────────────────────────────────────
# 1. クロスエンコーダーリランキング
# ─────────────────────────────────────────────

def load_reranker():
    """日本語クロスエンコーダーをロード"""
    import warnings
    warnings.filterwarnings("ignore")
    from sentence_transformers import CrossEncoder
    return CrossEncoder(RERANKER_MODEL, max_length=512)


def rerank(
    reranker,
    query: str,
    candidates: List[Dict],
    top_k: int = 5,
    alpha: float = 0.85,
) -> List[Dict]:
    """
    クロスエンコーダー + RRFスコアで候補チャンクをハイブリッドリランキング。

    RRF統合後の候補（通常top_k*2〜3件）をクエリとペアにして
    クロスエンコーダーでスコアリングし、上位top_k件を返す。

    Args:
        reranker: CrossEncoderモデル
        query: ユーザークエリ
        candidates: RRF統合後の候補リスト
        top_k: 返す件数
        alpha: クロスエンコーダー寄与率（0〜1）
    """
    if not candidates:
        return []

    alpha = max(0.0, min(1.0, alpha))

    # クエリ×チャンクのペアを作成
    pairs = [(query, c["text"][:512]) for c in candidates]

    # クロスエンコーダーでスコアリング
    scores = reranker.predict(pairs)

    rerank_scores = np.array([float(s) for s in scores], dtype=np.float32)
    base_scores = np.array([float(c.get("rrf_score", 0.0)) for c in candidates], dtype=np.float32)

    # min-max正規化（分母ゼロは同値扱い）
    rerank_min, rerank_max = float(rerank_scores.min()), float(rerank_scores.max())
    if rerank_max - rerank_min > 1e-10:
        rerank_norm = (rerank_scores - rerank_min) / (rerank_max - rerank_min)
    else:
        rerank_norm = np.ones_like(rerank_scores)

    base_min, base_max = float(base_scores.min()), float(base_scores.max())
    if base_max - base_min > 1e-10:
        base_norm = (base_scores - base_min) / (base_max - base_min)
    else:
        base_norm = np.ones_like(base_scores)

    # ハイブリッドスコア:
    #   cross-encoder の意味理解を主軸にしつつ、RRFの安定性を少量残す
    hybrid_scores = alpha * rerank_norm + (1.0 - alpha) * base_norm

    # スコアを付与してソート
    for i, c in enumerate(candidates):
        c["rerank_score"] = float(rerank_scores[i])
        c["rrf_norm"] = float(base_norm[i])
        c["rerank_norm"] = float(rerank_norm[i])
        c["hybrid_score"] = float(hybrid_scores[i])

    reranked = sorted(candidates, key=lambda x: -x["hybrid_score"])
    return reranked[:top_k]


# ─────────────────────────────────────────────
# 2. Chronicle Graph ベクトル検索
# ─────────────────────────────────────────────

def build_chronicle_embeddings(ruri_model, graph: dict) -> Tuple[np.ndarray, List[dict]]:
    """
    Chronicle Graphの全エッジtargetをruri-v3でembeddingし、
    npy + jsonで保存する（初回のみ実行、以降はキャッシュ読み込み）。
    """
    import warnings
    warnings.filterwarnings("ignore")

    edges = graph["edges"]
    edge_payload = json.dumps(edges, ensure_ascii=False, sort_keys=True)
    edge_hash = hashlib.sha256(edge_payload.encode("utf-8")).hexdigest()

    # キャッシュチェック
    if (
        CHRONICLE_EMBEDDINGS_FILE.exists()
        and CHRONICLE_EDGES_FILE.exists()
        and CHRONICLE_META_FILE.exists()
    ):
        embeddings = np.load(str(CHRONICLE_EMBEDDINGS_FILE))
        with open(CHRONICLE_EDGES_FILE, encoding="utf-8") as f:
            cached_edges = json.load(f)
        with open(CHRONICLE_META_FILE, encoding="utf-8") as f:
            meta = json.load(f)

        # エッジ内容ハッシュ・件数・embedding件数が一致した場合のみキャッシュ使用
        valid_shape = embeddings.shape[0] == len(cached_edges)
        if (
            meta.get("edge_hash") == edge_hash
            and meta.get("edge_count") == len(edges)
            and valid_shape
        ):
            return embeddings, cached_edges

    # embedding生成
    texts = ["文章: " + e["target"] for e in edges]
    embeddings = ruri_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    # 保存
    np.save(str(CHRONICLE_EMBEDDINGS_FILE), embeddings)
    with open(CHRONICLE_EDGES_FILE, "w", encoding="utf-8") as f:
        json.dump(edges, f, ensure_ascii=False, indent=2)
    with open(CHRONICLE_META_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"edge_hash": edge_hash, "edge_count": len(edges)},
            f,
            ensure_ascii=False,
            indent=2,
        )

    return embeddings, edges


def query_chronicle_vector(
    ruri_model,
    query: str,
    edge_embeddings: np.ndarray,
    edges: List[dict],
    top_n: int = 8,
) -> List[Dict]:
    """
    クエリをruri-v3でembeddingし、Chronicle Graphエッジとcosine類似度で検索。
    bigram方式と比べて意味的に近いエッジを取得できる。
    """
    import warnings
    warnings.filterwarnings("ignore")

    query_emb = ruri_model.encode(["クエリ: " + query], convert_to_numpy=True)[0]

    # cosine類似度計算
    # normalize
    query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-10)
    edge_norms = edge_embeddings / (np.linalg.norm(edge_embeddings, axis=1, keepdims=True) + 1e-10)
    similarities = edge_norms @ query_norm

    # 上位top_nを取得
    top_indices = np.argsort(similarities)[::-1][:top_n]

    results = []
    for idx in top_indices:
        edge = edges[idx].copy()
        edge["similarity"] = float(similarities[idx])
        results.append(edge)

    return results


# ─────────────────────────────────────────────
# 3. チャンク文脈拡張
# ─────────────────────────────────────────────

def expand_chunk_context(
    chunk: Dict,
    all_chunks: List[Dict],
    chunk_index_map: Dict[str, int],
    window: int = 1,
) -> str:
    """
    検索ヒットしたチャンクの前後windowチャンク（同一ソースファイル内）を結合して
    文脈を補完する。

    Args:
        chunk: ヒットしたチャンク
        all_chunks: 全チャンクリスト
        chunk_index_map: chunk_id → all_chunksのインデックス のマップ
        window: 前後何チャンク結合するか (デフォルト1)
    """
    chunk_id = chunk.get("chunk_id", "")
    if not chunk_id:
        return chunk["text"]
    idx = chunk_index_map.get(chunk_id)
    if idx is None:
        return chunk["text"]

    source = chunk.get("source", chunk.get("source_file", ""))
    parts = []

    # 前のチャンク（同一ソース）
    for offset in range(-window, 0):
        neighbor_idx = idx + offset
        if 0 <= neighbor_idx < len(all_chunks):
            neighbor = all_chunks[neighbor_idx]
            if neighbor.get("source_file", "") == source:
                parts.append(neighbor.get("text", ""))

    # 本体
    parts.append(chunk["text"])

    # 後のチャンク（同一ソース）
    for offset in range(1, window + 1):
        neighbor_idx = idx + offset
        if 0 <= neighbor_idx < len(all_chunks):
            neighbor = all_chunks[neighbor_idx]
            if neighbor.get("source_file", "") == source:
                parts.append(neighbor.get("text", ""))

    return "　".join(parts)


def build_chunk_index_map(all_chunks: List[Dict]) -> Dict[str, int]:
    """chunk_id → リストインデックス のマッピングを構築"""
    index_map: Dict[str, int] = {}
    for i, chunk in enumerate(all_chunks):
        chunk_id = chunk.get("chunk_id", "")
        if chunk_id:
            index_map[chunk_id] = i
    return index_map


def _safe_profile_path(name: str) -> Path:
    """プロファイル名を正規化し、安全な保存先パスを返す。"""
    safe_name = re.sub(r"[^0-9A-Za-z_\-ぁ-んァ-ヶ一-龥]", "_", (name or "").strip())
    if not safe_name:
        safe_name = "default"
    profile_path = (PROFILES_DIR / f"{safe_name}.json").resolve()
    profiles_root = PROFILES_DIR.resolve()
    if not str(profile_path).startswith(str(profiles_root) + os.sep):
        raise ValueError("不正なプロファイル名です")
    return profile_path


# ─────────────────────────────────────────────
# 4. お客様プロファイル
# ─────────────────────────────────────────────

def load_profile(name: str) -> Optional[Dict]:
    """
    profiles/{name}.json からプロファイルを読み込む。
    なければNoneを返す。
    """
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = _safe_profile_path(name)
    if not profile_path.exists():
        return None
    with open(profile_path, encoding="utf-8") as f:
        return json.load(f)


def save_profile(name: str, profile: Dict):
    """プロファイルを保存"""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = _safe_profile_path(name)
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def create_default_profile(name: str) -> Dict:
    """デフォルトプロファイルを作成"""
    profile = {
        "name": name,
        "themes": [],
        "stage": "",
        "notes": "",
        "conversation_summary": "",
        "session_count": 0,
    }
    save_profile(name, profile)
    return profile


def update_profile_after_session(
    name: str,
    conversation_summary: str,
    themes: List[str] = None,
):
    """セッション後にプロファイルを更新"""
    profile = load_profile(name) or create_default_profile(name)
    profile["session_count"] = profile.get("session_count", 0) + 1
    profile["conversation_summary"] = conversation_summary
    if themes:
        existing = set(profile.get("themes", []))
        existing.update(themes)
        profile["themes"] = list(existing)
    save_profile(name, profile)
    return profile


def build_profile_prompt(profile: Dict) -> str:
    """プロファイルからシステムプロンプト用テキストを生成"""
    if not profile:
        return ""

    lines = [
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "【この方について（過去のセッション情報）】",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"名前: {profile.get('name', '不明')}",
    ]

    if profile.get("session_count"):
        lines.append(f"セッション回数: {profile['session_count']}回目")

    if profile.get("themes"):
        lines.append(f"過去のテーマ: {', '.join(profile['themes'])}")

    if profile.get("stage"):
        lines.append(f"現在の段階: {profile['stage']}")

    if profile.get("notes"):
        lines.append(f"メモ: {profile['notes']}")

    if profile.get("conversation_summary"):
        lines.append(f"\n前回の要約:\n{profile['conversation_summary']}")

    return "\n".join(lines)


def list_profiles() -> List[str]:
    """保存済みプロファイル名一覧を返す"""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return [p.stem for p in PROFILES_DIR.glob("*.json")]

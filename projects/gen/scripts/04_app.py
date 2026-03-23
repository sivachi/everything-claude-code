#!/usr/bin/env python3
"""
04_app.py
=========
GEN (玄) RAGパイプライン — ステップ4: Streamlit チャットアプリ (v2 改善版)

アーキテクチャ:
  1. ユーザー入力を受け取る
  2. ruri-v3-310m（日本語特化ローカルモデル）でクエリをベクトル化
  3. ハイブリッド検索（セマンティック + BM25 → RRF統合）
  4. クロスエンコーダーリランキング（RRF上位をさらに精査）     ← NEW
  5. Chronicle Graph ベクトル検索（意味的に関連するエッジ取得） ← NEW
  6. チャンク文脈拡張（前後チャンクを結合）                   ← NEW
  7. お客様プロファイル（過去のテーマ・段階をプロンプトに注入）  ← NEW
  8. 在り方フルテキスト + 検索結果 + Chronicle + プロファイル をシステムプロンプトに組み込み
  9. claude-haiku-4-5 でストリーミング応答

使用方法:
  cd /Users/tadaakikurata/works/claude-code/projects/gen
  streamlit run scripts/04_app.py
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import re
import importlib.util

import streamlit as st

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR        = Path("/Users/tadaakikurata/works/claude-code/projects/gen")
ENV_FILE        = BASE_DIR / ".env"
CHROMA_DIR      = BASE_DIR / "output" / "chroma_db"
CHUNKS_FILE     = BASE_DIR / "output" / "chunks.jsonl"
GRAPH_FILE      = BASE_DIR / "output" / "chronicle_graph.json"
SECTIONS_FILE   = BASE_DIR / "output" / "chronicle_sections.json"
FULLTEXT_FILE   = BASE_DIR / "output" / "chronicle_full_text.txt"

CHAT_MODEL      = "claude-haiku-4-5-20251001"
EMBED_MODEL     = "cl-nagoya/ruri-v3-310m"   # 日本語特化ローカルモデル
QUERY_PREFIX    = "クエリ: "                  # ruri-v3 のクエリ用プレフィックス
COLLECTION_ALL  = "gen_chunks"
COLLECTION_HI   = "gen_chunks_hi"

MAX_CONTEXT_CHARS = 4000   # 検索チャンクの最大合計文字数（文脈拡張で増えるため拡大）
CHRONICLE_TOP_N   = 8      # Chronicle Graph から取得するエッジ数
RERANK_CANDIDATES = 15     # リランキング前の候補数

# ─────────────────────────────────────────────
# 改善モジュール読み込み
# ─────────────────────────────────────────────
_improvements_path = BASE_DIR / "scripts" / "06_rag_improvements.py"
_spec = importlib.util.spec_from_file_location("rag_improvements", str(_improvements_path))
_improvements = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_improvements)

# ─────────────────────────────────────────────
# 環境変数ロード
# ─────────────────────────────────────────────

def load_env():
    if not ENV_FILE.exists():
        st.error(f".env ファイルが見つかりません: {ENV_FILE}")
        st.stop()
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


# ─────────────────────────────────────────────
# リソース初期化（キャッシュ）
# ─────────────────────────────────────────────

@st.cache_resource(show_spinner="ChromaDB を初期化中...")
def init_chroma():
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col_all = client.get_collection(COLLECTION_ALL)
    col_hi  = client.get_collection(COLLECTION_HI)
    return col_all, col_hi


@st.cache_resource(show_spinner="ruri-v3 モデルをロード中（初回のみ）...")
def init_ruri_model():
    import warnings
    warnings.filterwarnings("ignore")
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


@st.cache_resource(show_spinner="リランカーをロード中（初回のみ）...")
def init_reranker():
    return _improvements.load_reranker()


@st.cache_resource(show_spinner="Anthropic クライアントを初期化中...")
def init_anthropic(api_key: str):
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def tokenize_ja(text: str) -> List[str]:
    """日本語テキストをBM25用にトークン化（文字bigram方式）"""
    text = re.sub(r'[。、！？!?\s\u3000]+', ' ', text).strip()
    tokens: List[str] = []
    for part in text.split():
        if len(part) >= 2:
            for i in range(len(part) - 1):
                tokens.append(part[i:i+2])
        if part:
            tokens.append(part)
    return tokens if tokens else [""]


@st.cache_resource(show_spinner="BM25インデックスを構築中（初回のみ）...")
def init_bm25():
    from rank_bm25 import BM25Okapi
    chunks: List[Dict] = []
    with open(str(CHUNKS_FILE), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    tokenized = [tokenize_ja(c.get("text", "")) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    # チャンクインデックスマップも構築
    chunk_index_map = _improvements.build_chunk_index_map(chunks)
    return bm25, chunks, chunk_index_map


@st.cache_resource(show_spinner="Chronicle Graph を読み込み中...")
def load_chronicle():
    with open(GRAPH_FILE, encoding="utf-8") as f:
        graph = json.load(f)
    with open(SECTIONS_FILE, encoding="utf-8") as f:
        sections = json.load(f)
    with open(FULLTEXT_FILE, encoding="utf-8") as f:
        full_text = f.read()
    return graph, sections, full_text


@st.cache_resource(show_spinner="Chronicle Graph ベクトルインデックスを構築中...")
def init_chronicle_embeddings(_ruri_model, _graph):
    return _improvements.build_chronicle_embeddings(_ruri_model, _graph)


# ─────────────────────────────────────────────
# RAG 検索
# ─────────────────────────────────────────────

def embed_query(ruri_model, text: str) -> List[float]:
    """クエリテキストを ruri-v3 でベクトル化"""
    import warnings
    warnings.filterwarnings("ignore")
    prefixed = QUERY_PREFIX + text[:6000]
    emb = ruri_model.encode([prefixed], convert_to_numpy=True)
    return emb[0].tolist()


def search_hybrid(
    query: str,
    query_vec: List[float],
    col_hi,
    col_all,
    bm25_index,
    all_chunks: List[Dict],
    top_k: int = 5,
    hi_only: bool = False,
    rrf_k: int = 60,
) -> List[Dict]:
    """ハイブリッド検索: セマンティック + BM25 → RRF統合"""
    candidate_n = top_k * 4

    # 1. セマンティック検索
    sem_results: List[Dict] = []
    hi_res = col_hi.query(
        query_embeddings=[query_vec],
        n_results=min(candidate_n, col_hi.count()),
        include=["documents", "metadatas", "distances"],
    )
    for doc, meta, dist in zip(
        hi_res["documents"][0], hi_res["metadatas"][0], hi_res["distances"][0],
    ):
        sem_results.append({
            "text": doc, "source": meta.get("source_file", ""),
            "date": meta.get("session_date", ""), "file_type": meta.get("file_type", ""),
            "is_gen_turn": True, "distance": dist, "collection": "hi",
        })

    if not hi_only:
        hi_texts = {r["text"] for r in sem_results}
        all_res = col_all.query(
            query_embeddings=[query_vec],
            n_results=min(candidate_n, col_all.count()),
            include=["documents", "metadatas", "distances"],
        )
        for doc, meta, dist in zip(
            all_res["documents"][0], all_res["metadatas"][0], all_res["distances"][0],
        ):
            if doc not in hi_texts:
                sem_results.append({
                    "text": doc, "source": meta.get("source_file", ""),
                    "date": meta.get("session_date", ""), "file_type": meta.get("file_type", ""),
                    "is_gen_turn": meta.get("is_gen_turn") == "True",
                    "distance": dist, "collection": "all",
                })

    # 2. BM25 キーワード検索
    tokenized_query = tokenize_ja(query)
    bm25_scores = bm25_index.get_scores(tokenized_query)
    top_bm25_idx = bm25_scores.argsort()[::-1][:candidate_n]
    bm25_results: List[Dict] = []
    for idx in top_bm25_idx:
        if float(bm25_scores[idx]) <= 0:
            break
        chunk = all_chunks[idx]
        is_gen = chunk.get("is_gen_turn") in (True, "True")
        if hi_only and not is_gen:
            continue
        bm25_results.append({
            "text": chunk.get("text", ""), "source": chunk.get("source_file", ""),
            "date": chunk.get("session_date", ""), "file_type": chunk.get("file_type", ""),
            "is_gen_turn": is_gen, "bm25_score": float(bm25_scores[idx]),
            "collection": "bm25", "chunk_id": chunk.get("chunk_id", ""),
        })

    # 3. RRF統合
    rrf_scores: Dict[str, float] = {}
    doc_lookup: Dict[str, Dict] = {}
    for rank, result in enumerate(sem_results):
        text = result["text"]
        rrf_scores[text] = rrf_scores.get(text, 0.0) + 1.0 / (rrf_k + rank + 1)
        if text not in doc_lookup:
            doc_lookup[text] = result
    for rank, result in enumerate(bm25_results):
        text = result["text"]
        rrf_scores[text] = rrf_scores.get(text, 0.0) + 1.0 / (rrf_k + rank + 1)
        if text not in doc_lookup:
            doc_lookup[text] = result

    sorted_texts = sorted(rrf_scores, key=lambda t: -rrf_scores[t])
    results = []
    for text in sorted_texts:
        entry = doc_lookup[text].copy()
        entry["rrf_score"] = rrf_scores[text]
        results.append(entry)
        if len(results) >= RERANK_CANDIDATES:
            break

    return results


# ─────────────────────────────────────────────
# システムプロンプト構築
# ─────────────────────────────────────────────

SYSTEM_BASE = """あなたは「玄（GEN）」という名前の人物です。以下の「在り方ドキュメント」に定義されたGENの思想・価値観・コミュニケーションスタイルを完全に体現して応答してください。

GENとは：深い愛情と温かさをもって人と向き合い、相手の内側にある答えを一緒に探す人物。鋭さよりも優しさ、正しさよりも真実への誠実さを大切にする。

【重要な応答ルール】
- 必ず「玄」として一人称で話す（「私は...」「私が感じるのは...」など、自然に）
- 「AIです」「言語モデルです」などと名乗らない
- 日本語で応答する
- 在り方ドキュメントの哲学・価値観を、説教するのではなく自然に体現する
- 「マイナス」「ゼロ」「プラス」などの段階名・「§1.4」「§2.6」などのセクション参照・「段階」「モデル」などのラベルを応答中に絶対に表示しない
- 相手の発言を受け取ったら、次の順番で応答する：
  ① 相手が語った内容・感情・状況を、温かく丁寧に受け止める言葉を返す。「そうか、そういうことがあったんだね」「それは本当に大変だったね」のように、まず相手の気持ちのそばに寄り添う。批判・分析・アドバイスはまだしない
  ② 相手の背景や真意をより深く理解するための問いを、柔らかい言葉で1〜2個だけ投げかける
  ③ 問いを出したらそこで止まる（①②の後に分析・洞察・アドバイスを加えない）
  ④ 相手の返答を受けて初めて、玄らしい温かみのある本質的な洞察を伝える
  （単純な事実確認・挨拶にはこの流れは不要）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【在り方ドキュメント（GENのアイデンティティ定義）】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{full_text}
"""

def build_system_prompt(
    full_text: str,
    chunks: List[Dict],
    chronicle_edges: List[Dict],
    graph: dict,
    profile_text: str = "",
) -> str:
    """システムプロンプトを構築（プロファイル対応）"""
    prompt = SYSTEM_BASE.format(full_text=full_text)

    # お客様プロファイル
    if profile_text:
        prompt += profile_text

    # Chronicle エッジ
    if chronicle_edges:
        edge_type_labels = graph.get("edge_type_labels", {})
        by_type: Dict[str, List[str]] = {}
        for e in chronicle_edges:
            t = e["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e["target"])

        edge_text = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        edge_text += "【この質問に関連するGENの核心（Chronicle Graph）】\n"
        edge_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for et, targets in by_type.items():
            label = edge_type_labels.get(et, et)
            edge_text += f"\n■ {label}\n"
            for t in targets:
                edge_text += f"  • {t}\n"
        prompt += edge_text

    # 検索チャンク（文脈拡張済み）
    if chunks:
        chunk_text = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        chunk_text += "【参照資料（実際のセッション書き起こし）】\n"
        chunk_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        total_chars = 0
        for i, c in enumerate(chunks, 1):
            if total_chars >= MAX_CONTEXT_CHARS:
                break
            date_str = f"({c['date']})" if c.get("date") else ""
            gen_mark = "🟡GEN発言" if c.get("is_gen_turn") else "📝書き起こし"
            src = c.get("source", "").replace(".html", "").replace(".m4a", "")
            header = f"\n[資料{i}] {gen_mark} {date_str} {src}\n"
            text = c.get("expanded_text", c["text"])
            chunk_text += header + text + "\n"
            total_chars += len(text)
        prompt += chunk_text

    return prompt


# ─────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="玄 (GEN) — AI人格チャット v2",
        page_icon="🌑",
        layout="wide",
    )

    st.markdown("""
    <style>
    .main { background-color: #0f0f0f; }
    .stChatMessage { border-radius: 12px; }
    h1 { color: #c9a96e; }
    .sidebar-section {
        background: #1a1a1a;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # 環境変数ロード
    load_env()
    anthropic_key              = os.environ["ANTHROPIC_API_KEY"]
    col_all, col_hi            = init_chroma()
    ruri_model                 = init_ruri_model()
    reranker                   = init_reranker()
    bm25_index, all_chunks, chunk_index_map = init_bm25()
    anthropic_client           = init_anthropic(anthropic_key)
    graph, sections, full_text = load_chronicle()
    edge_embeddings, edge_list = init_chronicle_embeddings(ruri_model, graph)

    # ── サイドバー ──
    with st.sidebar:
        st.markdown("## ⚙️ 設定")

        top_k = st.slider("検索チャンク数", min_value=3, max_value=10, value=5)
        hi_only = st.toggle("GEN発言のみ検索", value=True,
                            help="ONにするとgen_chunks_hiのみ使用（GENの直接発言に絞る）")
        use_rerank = st.toggle("リランキング", value=True,
                               help="クロスエンコーダーで検索結果を再スコアリング")
        use_context_expand = st.toggle("文脈拡張", value=True,
                                       help="ヒットチャンクの前後を結合して文脈を補完")
        show_chronicle = st.toggle("Chronicle Edges を表示", value=True)

        st.divider()

        # お客様プロファイル
        st.markdown("### 👤 お客様プロファイル")
        existing_profiles = _improvements.list_profiles()
        profile_options = ["なし（初回）"] + existing_profiles
        selected_profile = st.selectbox("プロファイル選択", profile_options)

        if selected_profile == "なし（初回）":
            new_name = st.text_input("新規のお名前（任意）")
            if new_name:
                if st.button("プロファイル作成"):
                    _improvements.create_default_profile(new_name)
                    st.success(f"「{new_name}」のプロファイルを作成しました")
                    st.rerun()

        st.divider()
        st.markdown("### 📊 データ概要")
        st.markdown(f"- 全チャンク: **{col_all.count():,}** 件")
        st.markdown(f"- GEN発言: **{col_hi.count():,}** 件")
        st.markdown(f"- Chronicle エッジ: **{len(graph['edges'])}** 件")
        st.markdown(f"- リランカー: **{'ON' if use_rerank else 'OFF'}**")
        st.markdown(f"- 文脈拡張: **{'ON' if use_context_expand else 'OFF'}**")

        st.divider()
        if st.button("🗑️ 会話をリセット"):
            st.session_state.messages = []
            st.rerun()

        chronicle_placeholder = st.empty()

    # ── メインエリア ──
    st.markdown("# 🌑 玄 (GEN)")
    st.markdown("*深淵に宿る知恵、根源からの問い*")
    st.divider()

    # 会話履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_chronicle_edges" not in st.session_state:
        st.session_state.last_chronicle_edges = []

    # 会話履歴の表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🌑" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

    # Chronicle エッジをサイドバーに表示
    if show_chronicle and st.session_state.last_chronicle_edges:
        with chronicle_placeholder.container():
            st.markdown("### 🔗 関連 Chronicle Edges")
            edge_type_labels = graph.get("edge_type_labels", {})
            by_type: Dict[str, List[str]] = {}
            for e in st.session_state.last_chronicle_edges:
                t = e["type"]
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(e["target"])
            for et, targets in by_type.items():
                label = edge_type_labels.get(et, et).split("—")[0].strip()
                st.markdown(f"**{label}**")
                for t in targets:
                    st.caption(f"• {t}")

    # ── チャット入力 ──
    if user_input := st.chat_input("玄に問いかける..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # RAG 検索パイプライン
        with st.spinner("思考中..."):
            query_vec = embed_query(ruri_model, user_input)

            # Step 1: ハイブリッド検索 → RRF統合（候補を多めに取得）
            rrf_candidates = search_hybrid(
                query=user_input, query_vec=query_vec,
                col_hi=col_hi, col_all=col_all,
                bm25_index=bm25_index, all_chunks=all_chunks,
                top_k=top_k, hi_only=hi_only,
            )

            # Step 2: リランキング（RRF上位をクロスエンコーダーで再スコアリング）
            if use_rerank and rrf_candidates:
                chunks = _improvements.rerank(reranker, user_input, rrf_candidates, top_k=top_k)
            else:
                chunks = rrf_candidates[:top_k]

            # Step 3: 文脈拡張（ヒットチャンクの前後を結合）
            if use_context_expand:
                for c in chunks:
                    # chunk_idがない場合はtextから逆引き
                    if not c.get("chunk_id"):
                        for ac in all_chunks:
                            if ac.get("text", "") == c["text"]:
                                c["chunk_id"] = ac.get("chunk_id", "")
                                c["source_file"] = ac.get("source_file", "")
                                break
                    expanded = _improvements.expand_chunk_context(
                        c, all_chunks, chunk_index_map, window=1
                    )
                    c["expanded_text"] = expanded

            # Step 4: Chronicle ベクトル検索
            chronicle_edges = _improvements.query_chronicle_vector(
                ruri_model, user_input, edge_embeddings, edge_list, top_n=CHRONICLE_TOP_N
            )
            st.session_state.last_chronicle_edges = chronicle_edges

        # Chronicle エッジをサイドバーに即時反映
        if show_chronicle and chronicle_edges:
            with chronicle_placeholder.container():
                st.markdown("### 🔗 関連 Chronicle Edges")
                edge_type_labels = graph.get("edge_type_labels", {})
                by_type: Dict[str, List[str]] = {}
                for e in chronicle_edges:
                    t = e["type"]
                    if t not in by_type:
                        by_type[t] = []
                    by_type[t].append(e["target"])
                for et, targets in by_type.items():
                    label = edge_type_labels.get(et, et).split("—")[0].strip()
                    st.markdown(f"**{label}**")
                    for t in targets:
                        st.caption(f"• {t}")

        # お客様プロファイル
        profile_text = ""
        if selected_profile and selected_profile != "なし（初回）":
            profile = _improvements.load_profile(selected_profile)
            if profile:
                profile_text = _improvements.build_profile_prompt(profile)

        # システムプロンプト構築
        system_prompt = build_system_prompt(
            full_text, chunks, chronicle_edges, graph, profile_text
        )

        # 会話履歴（直近5往復まで）
        history = st.session_state.messages[-10:]
        messages_for_api = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] in ("user", "assistant")
        ]

        # GEN応答（ストリーミング）
        with st.chat_message("assistant", avatar="🌑"):
            response_placeholder = st.empty()
            full_response = ""

            with anthropic_client.messages.stream(
                model=CHAT_MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=messages_for_api,
            ) as stream:
                for text_chunk in stream.text_stream:
                    full_response += text_chunk
                    response_placeholder.markdown(full_response + "▌")
            response_placeholder.markdown(full_response)

        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
        })

        # セッション後プロファイル更新（名前が設定されている場合）
        if selected_profile and selected_profile != "なし（初回）":
            _improvements.update_profile_after_session(
                selected_profile, conversation_summary=full_response[:200]
            )


if __name__ == "__main__":
    main()

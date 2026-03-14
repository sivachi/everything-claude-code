#!/usr/bin/env python3
"""
04_app.py
=========
GEN (玄) RAGパイプライン — ステップ4: Streamlit チャットアプリ

アーキテクチャ:
  1. ユーザー入力を受け取る
  2. ruri-v3-310m（日本語特化ローカルモデル）でクエリをベクトル化
  3. ハイブリッド検索（セマンティック + BM25 → RRF統合）
     - セマンティック: ChromaDB（gen_chunks_hi 優先 → gen_chunks フォールバック）
     - BM25: chunks.jsonlから全チャンクをメモリ展開してキーワード検索
     - RRF: 両結果の順位をスコア化して統合
  4. Chronicle Graph から関連エッジ（信念・価値観・診断法など）を抽出
  5. 在り方フルテキスト + 検索結果 + Chronicle エッジ をシステムプロンプトに組み込む
  6. claude-haiku-4-5 でストリーミング応答

使用方法:
  cd /Users/tadaakikurata/works/ai_takeo_local
  streamlit run scripts/04_app.py

設定（サイドバーで変更可）:
  - 検索件数 (top_k): 3〜10件
  - GENターン優先モード: gen_chunks_hi のみ使用
  - Chronicle エッジ表示: サイドバーに関連エッジを表示
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import re

import streamlit as st

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR        = Path("/Users/tadaakikurata/works/ai_takeo_local")
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

MAX_CONTEXT_CHARS = 3000   # 検索チャンクの最大合計文字数
CHRONICLE_TOP_N   = 8      # Chronicle Graph から取得するエッジ数

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
            # setdefault ではなく強制上書き（Claude Code の環境変数に負けないよう）
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


@st.cache_resource(show_spinner="Anthropic クライアントを初期化中...")
def init_anthropic(api_key: str):
    """api_key を引数にとることでキーが変わった際にキャッシュが再生成される"""
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def tokenize_ja(text: str) -> List[str]:
    """
    日本語テキストをBM25用にトークン化。
    句読点・空白で分割後、文字bigramを生成する。
    bigramにすることで形態素解析なしでも日本語キーワードを拾える。
    """
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
    """
    chunks.jsonl を全件メモリ展開し BM25Okapi インデックスを構築。
    12,089チャンク × 355文字 ≒ 4MB なのでメモリ問題なし。
    """
    from rank_bm25 import BM25Okapi

    chunks: List[Dict] = []
    with open(str(CHUNKS_FILE), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    tokenized = [tokenize_ja(c.get("text", "")) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    return bm25, chunks


@st.cache_resource(show_spinner="Chronicle Graph を読み込み中...")
def load_chronicle():
    with open(GRAPH_FILE, encoding="utf-8") as f:
        graph = json.load(f)
    with open(SECTIONS_FILE, encoding="utf-8") as f:
        sections = json.load(f)
    with open(FULLTEXT_FILE, encoding="utf-8") as f:
        full_text = f.read()
    return graph, sections, full_text


# ─────────────────────────────────────────────
# RAG 検索
# ─────────────────────────────────────────────

def embed_query(ruri_model, text: str) -> List[float]:
    """クエリテキストを ruri-v3 でベクトル化（「クエリ: 」プレフィックス付き）"""
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
    """
    ハイブリッド検索: セマンティック（ChromaDB）+ BM25 → RRF統合

    RRF スコア = Σ 1 / (rrf_k + rank + 1)
    両検索で上位に出たチャンクほど高スコアになる。

    Args:
        query      : 元のクエリ文字列（BM25用）
        query_vec  : クエリの埋め込みベクトル（セマンティック用）
        rrf_k      : RRFの定数（デフォルト60が一般的）
    """
    candidate_n = top_k * 4  # RRF統合前の候補数（多めに取得して後で絞る）

    # ─────────────────────────────────────────
    # 1. セマンティック検索（ChromaDB）
    # ─────────────────────────────────────────
    sem_results: List[Dict] = []

    # gen_chunks_hi から候補取得
    hi_res = col_hi.query(
        query_embeddings=[query_vec],
        n_results=min(candidate_n, col_hi.count()),
        include=["documents", "metadatas", "distances"],
    )
    for doc, meta, dist in zip(
        hi_res["documents"][0],
        hi_res["metadatas"][0],
        hi_res["distances"][0],
    ):
        sem_results.append({
            "text": doc,
            "source": meta.get("source_file", ""),
            "date": meta.get("session_date", ""),
            "file_type": meta.get("file_type", ""),
            "is_gen_turn": True,
            "distance": dist,
            "collection": "hi",
        })

    if not hi_only:
        hi_texts = {r["text"] for r in sem_results}
        all_res = col_all.query(
            query_embeddings=[query_vec],
            n_results=min(candidate_n, col_all.count()),
            include=["documents", "metadatas", "distances"],
        )
        for doc, meta, dist in zip(
            all_res["documents"][0],
            all_res["metadatas"][0],
            all_res["distances"][0],
        ):
            if doc not in hi_texts:
                sem_results.append({
                    "text": doc,
                    "source": meta.get("source_file", ""),
                    "date": meta.get("session_date", ""),
                    "file_type": meta.get("file_type", ""),
                    "is_gen_turn": meta.get("is_gen_turn") == "True",
                    "distance": dist,
                    "collection": "all",
                })

    # ─────────────────────────────────────────
    # 2. BM25 キーワード検索
    # ─────────────────────────────────────────
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
            "text": chunk.get("text", ""),
            "source": chunk.get("source_file", ""),
            "date": chunk.get("session_date", ""),
            "file_type": chunk.get("file_type", ""),
            "is_gen_turn": is_gen,
            "bm25_score": float(bm25_scores[idx]),
            "collection": "bm25",
        })

    # ─────────────────────────────────────────
    # 3. RRF（Reciprocal Rank Fusion）統合
    #    text をキーとしてスコアを累積
    # ─────────────────────────────────────────
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

    # RRFスコア降順でソートして top_k を返す
    sorted_texts = sorted(rrf_scores, key=lambda t: -rrf_scores[t])
    results = []
    for text in sorted_texts:
        entry = doc_lookup[text].copy()
        entry["rrf_score"] = rrf_scores[text]
        results.append(entry)
        if len(results) >= top_k:
            break

    return results


# ─────────────────────────────────────────────
# Chronicle Graph クエリ
# ─────────────────────────────────────────────

def query_chronicle(graph: dict, query: str, top_n: int = CHRONICLE_TOP_N) -> List[Dict]:
    """
    クエリに関連する Chronicle エッジを bigram マッチングで取得。
    """
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
) -> str:
    """システムプロンプトを構築"""
    prompt = SYSTEM_BASE.format(full_text=full_text)

    # Chronicle エッジ（関連する信念・価値観・診断法など）
    if chronicle_edges:
        edge_type_labels = graph.get("edge_type_labels", {})
        edge_lines = []
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

    # 検索チャンク（実際のセッション発言・書き起こし）
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
            chunk_text += header + c["text"] + "\n"
            total_chars += len(c["text"])
        prompt += chunk_text

    return prompt


# ─────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="玄 (GEN) — AI人格チャット",
        page_icon="🌑",
        layout="wide",
    )

    # CSSカスタマイズ
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

    # 環境変数ロード（必ず最初に・強制上書き）
    load_env()
    anthropic_key         = os.environ["ANTHROPIC_API_KEY"]
    col_all, col_hi       = init_chroma()
    ruri_model            = init_ruri_model()
    bm25_index, all_chunks = init_bm25()
    anthropic_client      = init_anthropic(anthropic_key)
    graph, sections, full_text = load_chronicle()

    # ── サイドバー ──
    with st.sidebar:
        st.markdown("## ⚙️ 設定")

        top_k = st.slider("検索チャンク数", min_value=3, max_value=10, value=5)
        hi_only = st.toggle("GEN発言のみ検索", value=True,
                            help="ONにするとgen_chunks_hiのみ使用（GENの直接発言に絞る）")
        show_chronicle = st.toggle("Chronicle Edges を表示", value=True)

        st.divider()
        st.markdown("### 📊 データ概要")
        st.markdown(f"- 全チャンク: **{col_all.count():,}** 件")
        st.markdown(f"- GEN発言: **{col_hi.count():,}** 件")
        st.markdown(f"- Chronicle エッジ: **{len(graph['edges'])}** 件")

        st.divider()
        if st.button("🗑️ 会話をリセット"):
            st.session_state.messages = []
            st.rerun()

        # Chronicle エッジ表示エリア（最後の検索結果）
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
        # ユーザーメッセージ表示
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # RAG 検索（ハイブリッド: セマンティック + BM25 → RRF）
        with st.spinner("思考中..."):
            query_vec = embed_query(ruri_model, user_input)
            chunks = search_hybrid(
                query=user_input,
                query_vec=query_vec,
                col_hi=col_hi,
                col_all=col_all,
                bm25_index=bm25_index,
                all_chunks=all_chunks,
                top_k=top_k,
                hi_only=hi_only,
            )
            chronicle_edges = query_chronicle(graph, user_input)
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

        # システムプロンプト構築
        system_prompt = build_system_prompt(full_text, chunks, chronicle_edges, graph)

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

        # 会話履歴に保存
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
        })


if __name__ == "__main__":
    main()

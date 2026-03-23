#!/usr/bin/env python3
"""
03_index.py
===========
GEN (玄) RAGパイプライン — ステップ3: ChromaDB へのベクトルインデックス登録

概要:
  chunks.jsonl の全チャンクを ruri-v3-310m（日本語特化ローカルモデル）で埋め込み、
  ChromaDB のコレクションに登録する。

  2つのコレクションを作成:
    gen_chunks    : 全チャンク (12,089件)
    gen_chunks_hi : GENターンのみ (687件) — 高精度検索用

入力:
  output/chunks.jsonl

出力:
  output/chroma_db/   — ChromaDB 永続化ディレクトリ

使用方法:
  python3 03_index.py [--collection all|hi|both] [--batch-size 32] [--resume] [--rebuild]

オプション:
  --collection : all=全チャンク, hi=GENターンのみ, both=両方(デフォルト)
  --batch-size : 1バッチのチャンク数 (デフォルト: 32)
  --resume     : 既存コレクションに追記（スキップ機能付き）
  --rebuild    : 既存コレクションを削除して再構築（次元数変更時に使用）
  --dry-run    : モデルを呼ばず件数のみ確認
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR    = Path("/Users/tadaakikurata/works/claude-code/projects/gen")
CHUNKS_FILE = BASE_DIR / "output" / "chunks.jsonl"
CHROMA_DIR  = BASE_DIR / "output" / "chroma_db"

EMBED_MODEL    = "cl-nagoya/ruri-v3-310m"
DOC_PREFIX     = "文章: "          # ruri-v3 のドキュメント用プレフィックス
COLLECTION_ALL = "gen_chunks"
COLLECTION_HI  = "gen_chunks_hi"

MAX_TEXT_CHARS = 6000  # 長すぎるチャンクの切り詰め


# ─────────────────────────────────────────────
# チャンク読み込み
# ─────────────────────────────────────────────

def load_chunks(jsonl_path: Path) -> List[dict]:
    chunks = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


# ─────────────────────────────────────────────
# ChromaDB メタデータ変換
# ─────────────────────────────────────────────

def to_chroma_meta(chunk: dict) -> dict:
    """
    ChromaDB のメタデータはスカラー値のみ許容。
    List型 (context_turns) は JSON文字列に変換。
    None は "" に変換。
    """
    meta = {
        "source_file":        chunk.get("source_file", ""),
        "file_type":          chunk.get("file_type", ""),
        "char_count":         chunk.get("char_count", 0),
        "chunk_index":        chunk.get("chunk_index", 0),
        "session_date":       chunk.get("session_date") or "",
        "is_gen_turn":        str(chunk.get("is_gen_turn")),
        "context_turns_json": json.dumps(
            chunk.get("context_turns", []), ensure_ascii=False
        ),
    }
    return meta


# ─────────────────────────────────────────────
# ruri-v3 埋め込み生成
# ─────────────────────────────────────────────

def load_ruri_model():
    """ruri-v3-310m モデルをロード"""
    import warnings
    warnings.filterwarnings("ignore")
    from sentence_transformers import SentenceTransformer
    print(f"  モデルをロード中: {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)
    print(f"  モデルロード完了")
    return model


def embed_batch_ruri(
    model,
    texts: List[str],
    batch_size: int = 32,
) -> List[List[float]]:
    """テキストリストを ruri-v3 でバッチ埋め込み。
    ドキュメントには「文章: 」プレフィックスを付与。
    """
    import warnings
    warnings.filterwarnings("ignore")

    prefixed = [DOC_PREFIX + t[:MAX_TEXT_CHARS] for t in texts]
    embeddings = model.encode(
        prefixed,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [emb.tolist() for emb in embeddings]


# ─────────────────────────────────────────────
# インデックス登録
# ─────────────────────────────────────────────

def index_chunks(
    chunks: List[dict],
    collection,
    model,
    batch_size: int,
    resume: bool,
    label: str,
) -> Dict:
    """チャンクを ChromaDB コレクションに登録する。"""

    # resume: 既登録IDを取得してスキップ
    existing_ids: set = set()
    if resume:
        try:
            existing = collection.get(include=[])
            existing_ids = set(existing["ids"])
            print(f"  [{label}] 既登録: {len(existing_ids)} 件 → スキップ対象")
        except Exception:
            pass

    # 未登録チャンクのみ抽出
    pending = [c for c in chunks if c["chunk_id"] not in existing_ids]
    print(f"  [{label}] 登録対象: {len(pending)} 件 / 全 {len(chunks)} 件")

    if not pending:
        print(f"  [{label}] 全件登録済み。スキップ。")
        return {"registered": 0, "skipped": len(chunks)}

    registered = 0

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        texts = [c["text"] for c in batch]
        ids   = [c["chunk_id"] for c in batch]
        metas = [to_chroma_meta(c) for c in batch]

        # 埋め込み生成（ruri-v3）
        embeddings = embed_batch_ruri(model, texts, batch_size=batch_size)

        # ChromaDB に upsert
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metas,
        )

        registered += len(batch)
        progress_pct = registered / len(pending) * 100
        elapsed_batches = i // batch_size + 1
        print(
            f"  [{label}] {registered:5d}/{len(pending)} ({progress_pct:5.1f}%) "
            f"| batch {elapsed_batches} 完了"
        )

    return {
        "registered": registered,
        "skipped": len(existing_ids),
    }


# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ChromaDB へのベクトルインデックス登録（ruri-v3）")
    parser.add_argument(
        "--collection",
        choices=["all", "hi", "both"],
        default="both",
        help="登録対象コレクション: all=全件, hi=GENターンのみ, both=両方(デフォルト)",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="バッチサイズ(デフォルト: 32)")
    parser.add_argument("--resume", action="store_true", help="既存コレクションに追記")
    parser.add_argument("--rebuild", action="store_true", help="既存コレクションを削除して再構築")
    parser.add_argument("--dry-run", action="store_true", help="件数確認のみ（モデル呼び出しなし）")
    args = parser.parse_args()

    # チャンク読み込み
    print(f"[03_index] チャンク読み込み: {CHUNKS_FILE}")
    chunks_all = load_chunks(CHUNKS_FILE)
    chunks_hi  = [c for c in chunks_all if c.get("is_gen_turn") is True]

    print(f"  全チャンク数       : {len(chunks_all):,}")
    print(f"  GENターンチャンク  : {len(chunks_hi):,}")
    print(f"  登録先             : {CHROMA_DIR}")
    print(f"  Embeddingモデル    : {EMBED_MODEL}  (768次元, 日本語特化, ローカル推論)")

    if args.dry_run:
        print("\n[dry-run] ここで終了します（モデル呼び出しなし）")
        return

    # ruri-v3 モデルロード
    model = load_ruri_model()

    # ChromaDB クライアント
    try:
        import chromadb
        chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    except ImportError:
        print("ERROR: chromadb パッケージが見つかりません。pip install chromadb してください。")
        sys.exit(1)

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    start_time = time.time()

    # ── コレクションの準備（rebuild時は削除→再作成）──
    def get_collection(name: str):
        if args.rebuild:
            try:
                chroma_client.delete_collection(name)
                print(f"  [{name}] 既存コレクションを削除しました")
            except Exception:
                pass
        return chroma_client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── gen_chunks（全件）──
    if args.collection in ("all", "both"):
        print(f"\n[1/2] コレクション '{COLLECTION_ALL}' に登録中...")
        col_all = get_collection(COLLECTION_ALL)
        results["all"] = index_chunks(
            chunks_all, col_all, model,
            batch_size=args.batch_size,
            resume=args.resume,
            label=COLLECTION_ALL,
        )

    # ── gen_chunks_hi（GENターンのみ）──
    if args.collection in ("hi", "both"):
        print(f"\n[2/2] コレクション '{COLLECTION_HI}' に登録中...")
        col_hi = get_collection(COLLECTION_HI)
        results["hi"] = index_chunks(
            chunks_hi, col_hi, model,
            batch_size=args.batch_size,
            resume=args.resume,
            label=COLLECTION_HI,
        )

    elapsed = time.time() - start_time

    # ── サマリー ──
    print("\n" + "=" * 60)
    print("【インデックス登録 完了】")
    print(f"  所要時間: {elapsed:.1f} 秒")
    print(f"  モデル  : {EMBED_MODEL} (ローカル推論, APIコスト: 0円)")

    for key, r in results.items():
        name = COLLECTION_ALL if key == "all" else COLLECTION_HI
        print(f"\n  [{name}]")
        print(f"    登録: {r.get('registered', 0):,} 件")
        print(f"    スキップ: {r.get('skipped', 0):,} 件")

    print(f"\n  ChromaDB: {CHROMA_DIR}")
    print("=" * 60)

    # 登録確認
    print("\n[登録確認]")
    try:
        import chromadb as _chroma
        _client = _chroma.PersistentClient(path=str(CHROMA_DIR))
        for name in [COLLECTION_ALL, COLLECTION_HI]:
            try:
                col = _client.get_collection(name)
                # 次元数確認
                sample = col.get(limit=1, include=["embeddings"])
                dim = len(sample["embeddings"][0]) if sample["embeddings"] else "?"
                print(f"  {name}: {col.count():,} 件  (次元数: {dim})")
            except Exception:
                pass
    except Exception:
        pass


if __name__ == "__main__":
    main()

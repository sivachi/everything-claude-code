"""
ナレッジベースからRAGインデックスを構築するスクリプト
メモリ効率を考慮してバッチ処理で実行
"""

import os
import json
import numpy as np
import torch

torch.set_num_threads(1)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ファイルパス
SOURCE_FILE = "/Users/tadaakikurata/Downloads/Takeout/NotebookLM/AI竹尾プロジェクト(人格コピー)/Sources/AI竹尾_ナレッジベース_クリーン.md"
INDEX_PATH = "faiss_index"


def load_and_split(file_path: str) -> list[str]:
    """ファイルを読み込んでセクションに分割"""
    print(f"ファイルを読み込み中: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"ファイルサイズ: {len(content):,} 文字")

    # ### 出典: でセクション分割
    lines = content.split("\n")
    sections = []
    current = []

    for line in lines:
        if line.startswith("### 出典:") or line.startswith("### "):
            if current:
                text = "\n".join(current).strip()
                if len(text) > 50:
                    sections.append(text)
            current = [line]
        else:
            current.append(line)

    if current:
        text = "\n".join(current).strip()
        if len(text) > 50:
            sections.append(text)

    print(f"セクション数: {len(sections)}")
    return sections


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """テキストをチャンクに分割"""
    chunks = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text):
            for sep in ["。", "\n", ".", "、", ","]:
                last_sep = chunk.rfind(sep)
                if last_sep > chunk_size // 2:
                    chunk = chunk[: last_sep + 1]
                    end = start + last_sep + 1
                    break

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap

    return chunks


def main():
    import faiss
    from sentence_transformers import SentenceTransformer

    # 既存のインデックスを削除
    if os.path.exists(f"{INDEX_PATH}.index"):
        os.remove(f"{INDEX_PATH}.index")
    if os.path.exists(f"{INDEX_PATH}.json"):
        os.remove(f"{INDEX_PATH}.json")

    # ファイル読み込みとチャンキング
    sections = load_and_split(SOURCE_FILE)

    all_chunks = []
    for section in sections:
        chunks = chunk_text(section)
        all_chunks.extend(chunks)

    print(f"チャンク数: {len(all_chunks)}")

    # モデルロード
    print("\n埋め込みモデルをロード中...")
    model = SentenceTransformer(
        "cl-nagoya/ruri-v3-310m", device="cpu", trust_remote_code=True
    )
    dim = model.get_sentence_embedding_dimension()

    # Faissインデックス作成
    index = faiss.IndexFlatIP(dim)

    # バッチ処理で埋め込み生成
    print("\n埋め込みを生成中...")
    batch_size = 10
    all_embeddings = []

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        print(f"  バッチ {i//batch_size + 1}/{(len(all_chunks)-1)//batch_size + 1}")
        embeddings = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        all_embeddings.append(embeddings)

    embeddings = np.vstack(all_embeddings).astype(np.float32)
    print(f"埋め込み完了: {embeddings.shape}")

    # インデックスに追加
    index.add(embeddings)

    # 保存
    faiss.write_index(index, f"{INDEX_PATH}.index")
    with open(f"{INDEX_PATH}.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\n完了！")
    print(f"インデックス: {INDEX_PATH}.index")
    print(f"ドキュメント: {INDEX_PATH}.json")
    print(f"チャンク数: {len(all_chunks)}")


if __name__ == "__main__":
    main()

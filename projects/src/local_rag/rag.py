"""
ローカルRAGシステム
- 埋め込み: ruri-v3-310m（日本語特化、JMTEB SOTA）
- ベクトル検索: Faiss
- 生成: Ollama
"""

import os
import json
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import faiss
import ollama

# Apple Silicon対応
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class LocalRAG:
    def __init__(
        self,
        embedding_model: str = "cl-nagoya/ruri-v3-310m",
        llm_model: str = "gemma2:2b",
        index_path: str = "faiss_index",
    ):
        """
        Args:
            embedding_model: 埋め込みモデル名
            llm_model: Ollamaで使用するモデル名
            index_path: Faissインデックスの保存先
        """
        print(f"埋め込みモデルをロード中: {embedding_model}")
        # 安定動作のためtrust_remote_codeを有効化
        self.model = SentenceTransformer(
            embedding_model,
            device="cpu",
            trust_remote_code=True,
        )
        self.llm_model = llm_model
        self.index_path = index_path
        self.dim = self.model.get_sentence_embedding_dimension()

        self.index = None
        self.documents = []

        # 既存のインデックスがあれば読み込み
        if os.path.exists(f"{index_path}.index"):
            self.load_index()

    def add_documents(self, documents: list[str], chunk_size: int = 500, overlap: int = 100):
        """
        ドキュメントを追加してインデックスを構築

        Args:
            documents: 追加するドキュメントのリスト
            chunk_size: チャンクサイズ（文字数）
            overlap: チャンク間のオーバーラップ
        """
        # チャンキング
        chunks = []
        for doc in documents:
            doc_chunks = self._chunk_text(doc, chunk_size, overlap)
            chunks.extend(doc_chunks)

        print(f"{len(chunks)}個のチャンクを作成")

        # 埋め込み生成（メモリ節約のためバッチ処理）
        print("埋め込みを生成中...")
        batch_size = 4  # メモリ節約のため小さめに
        all_embeddings = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_embeddings = self.model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            all_embeddings.append(batch_embeddings)
            if (i // batch_size) % 50 == 0:
                print(f"  進捗: {i}/{len(chunks)}")

        embeddings = np.vstack(all_embeddings)

        # Faissインデックス作成（内積＝コサイン類似度、正規化済みのため）
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dim)

        self.index.add(embeddings.astype(np.float32))
        self.documents.extend(chunks)

        print(f"インデックスに{len(chunks)}個のチャンクを追加")
        self.save_index()

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """テキストをチャンクに分割"""
        chunks = []
        start = 0
        text = text.strip()

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # 文の途中で切れないように調整
            if end < len(text):
                # 句点、改行などで区切る
                for sep in ["。", "\n", ".", "、", ","]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > chunk_size // 2:
                        chunk = chunk[:last_sep + 1]
                        end = start + last_sep + 1
                        break

            if chunk.strip():
                chunks.append(chunk.strip())

            start = end - overlap

        return chunks

    def search(self, query: str, k: int = 3) -> list[dict]:
        """
        クエリに関連するドキュメントを検索

        Args:
            query: 検索クエリ
            k: 取得する件数

        Returns:
            検索結果のリスト
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # クエリを埋め込み
        query_vec = self.model.encode(
            query,
            normalize_embeddings=True,
        ).astype(np.float32).reshape(1, -1)

        # 検索
        distances, indices = self.index.search(query_vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.documents):
                results.append({
                    "content": self.documents[idx],
                    "score": float(dist),
                })

        return results

    def query(self, question: str, k: int = 3) -> str:
        """
        質問に対してRAGで回答を生成

        Args:
            question: 質問
            k: 参照するドキュメント数

        Returns:
            生成された回答
        """
        # 関連ドキュメントを検索
        results = self.search(question, k=k)

        if not results:
            return "関連するドキュメントが見つかりませんでした。"

        # コンテキストを構築
        context = "\n\n---\n\n".join([r["content"] for r in results])

        # プロンプト構築
        prompt = f"""以下のコンテキストを参考にして、質問に回答してください。
コンテキストに情報がない場合は、「情報が見つかりません」と回答してください。

## コンテキスト
{context}

## 質問
{question}

## 回答"""

        # Ollamaで生成
        try:
            response = ollama.generate(
                model=self.llm_model,
                prompt=prompt,
            )
            return response["response"]
        except Exception as e:
            return f"エラーが発生しました: {e}\nOllamaが起動しているか確認してください。"

    def save_index(self):
        """インデックスを保存"""
        if self.index is not None:
            faiss.write_index(self.index, f"{self.index_path}.index")
            with open(f"{self.index_path}.json", "w", encoding="utf-8") as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
            print(f"インデックスを保存: {self.index_path}")

    def load_index(self):
        """インデックスを読み込み"""
        if os.path.exists(f"{self.index_path}.index"):
            self.index = faiss.read_index(f"{self.index_path}.index")
            with open(f"{self.index_path}.json", "r", encoding="utf-8") as f:
                self.documents = json.load(f)
            print(f"インデックスを読み込み: {len(self.documents)}件")


def main():
    """デモ用のメイン関数"""
    # RAGシステムを初期化
    rag = LocalRAG(llm_model="gemma2:2b")

    # サンプルドキュメントを追加
    sample_docs = [
        """
        Pythonは汎用プログラミング言語です。1991年にグイド・ヴァンロッサムによって開発されました。
        シンプルで読みやすい文法が特徴で、初心者にも学びやすい言語として人気があります。
        データ分析、機械学習、Web開発など幅広い分野で使用されています。
        """,
        """
        機械学習は人工知能の一分野です。データからパターンを学習し、予測や分類を行います。
        教師あり学習、教師なし学習、強化学習の3つの主要なカテゴリがあります。
        深層学習（ディープラーニング）は機械学習の一手法で、ニューラルネットワークを使用します。
        """,
        """
        RAG（Retrieval-Augmented Generation）は、大規模言語モデルに外部知識を与える手法です。
        質問に関連するドキュメントを検索し、その内容をコンテキストとして言語モデルに渡します。
        これにより、最新の情報や専門知識を活用した回答が可能になります。
        """,
    ]

    # インデックスが空の場合のみ追加
    if not rag.documents:
        rag.add_documents(sample_docs)

    # 対話ループ
    print("\n" + "="*50)
    print("ローカルRAG Q&Aシステム")
    print("終了するには 'quit' または 'exit' と入力してください")
    print("="*50 + "\n")

    while True:
        question = input("質問: ").strip()
        if question.lower() in ["quit", "exit", "q"]:
            break
        if not question:
            continue

        print("\n回答を生成中...")
        answer = rag.query(question)
        print(f"\n回答: {answer}\n")


if __name__ == "__main__":
    main()

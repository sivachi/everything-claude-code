"""
ドキュメントをRAGに読み込むスクリプト

使い方:
    python load_documents.py <ファイルパス>

例:
    python load_documents.py AI竹尾_ナレッジベース_クリーン.md
    python load_documents.py /path/to/documents/*.md
"""

import sys
import os
import json
from pathlib import Path
from rag import LocalRAG


def load_markdown(file_path: str) -> str:
    """Markdownファイルを読み込む"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def split_by_headers(content: str) -> list[str]:
    """
    Markdownをヘッダー（### 出典:）単位で分割
    出典ごとにチャンク化することで、文脈を保持
    """
    lines = content.split("\n")
    sections = []
    current_section = []

    for line in lines:
        # ### 出典: で始まる行で新しいセクション開始
        if line.startswith("### 出典:") or line.startswith("### "):
            if current_section:
                sections.append("\n".join(current_section).strip())
            current_section = [line]
        else:
            current_section.append(line)

    # 最後のセクションを追加
    if current_section:
        sections.append("\n".join(current_section).strip())

    # 空のセクションを除外、かつ最低限の長さがあるもの
    return [s for s in sections if s.strip() and len(s) > 50]


def load_text(file_path: str) -> str:
    """テキストファイルを読み込む"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def load_json(file_path: str) -> list[str]:
    """JSONファイルを読み込む (リスト形式 or 'text'/'content'キーを持つオブジェクトを想定)"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return [str(item) for item in data]
    elif isinstance(data, dict):
        # 特定のキーがあればそれを使う、なければダンプ
        for key in ["text", "content", "body"]:
            if key in data:
                return [str(data[key])]
        return [json.dumps(data, ensure_ascii=False)]
    return []

def main():
    
    if len(sys.argv) < 2:
        print("使い方: python load_documents.py <ファイルまたはディレクトリパス>")
        print("例: python load_documents.py data/")
        sys.exit(1)

    target_path = sys.argv[1]
    
    # ファイルリストを作成
    files_to_process = []
    path_obj = Path(target_path)
    
    if path_obj.is_dir():
        # ディレクトリなら再帰的に探索
        for ext in ["*.md", "*.txt", "*.json"]:
            files_to_process.extend(path_obj.rglob(ext))
    elif path_obj.exists():
        files_to_process.append(path_obj)
    else:
        print(f"パスが見つかりません: {target_path}")
        sys.exit(1)

    if not files_to_process:
        print("処理対象のファイルが見つかりませんでした。")
        sys.exit(0)

    # RAGシステムを初期化
    print("RAGシステムを初期化中...")
    rag = LocalRAG()

    all_documents = []

    for file_path in files_to_process:
        print(f"読み込み中: {file_path.name}")
        
        try:
            if file_path.suffix == ".json":
                docs = load_json(str(file_path))
                all_documents.extend(docs)
                print(f"  -> {len(docs)}件のドキュメントを追加")
            
            elif file_path.suffix in [".md", ".txt"]:
                content = load_text(str(file_path))
                
                # Markdownならヘッダー分割を試みる
                if file_path.suffix == ".md":
                    sections = split_by_headers(content)
                    if not sections: # 分割できなければ全体を1つとして扱う
                        sections = [content]
                else:
                    sections = [content]
                    
                # 空白除去と長さチェック
                valid_sections = [s for s in sections if s.strip() and len(s) > 10]
                all_documents.extend(valid_sections)
                print(f"  -> {len(valid_sections)}個のセクションを追加")
                
        except Exception as e:
            print(f"エラーが発生しました ({file_path.name}): {e}")

    if not all_documents:
        print("有効なドキュメントがありませんでした。")
        sys.exit(1)

    # RAGにドキュメントを追加
    print(f"\n合計 {len(all_documents)} 個のドキュメントをRAGに追加中...")
    
    # 既存のドキュメントと重複チェックなどをしても良いが、今回は単純追加
    
    rag.add_documents(all_documents, chunk_size=500, overlap=100)

    print("\n完了！")
    print(f"インデックスに合計 {len(rag.documents)} 個のチャンクが保存されました。")

if __name__ == "__main__":
    main()

import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA

# ==========================================
# 1. 設定 (Google API Keyを設定してください)
# ==========================================
# Google AI Studio (https://aistudio.google.com/) でキーを取得
# Google AI Studio (https://aistudio.google.com/) でキーを取得
if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it before running the script.")
# os.environ["GOOGLE_API_KEY"] is already set

# ==========================================
# 2. データの準備
# ==========================================
# テキストファイルがあればそこから読み込む、なければダミーデータ
data_file_path = "takeo_data.txt"
raw_text_data = []

if os.path.exists(data_file_path):
    print(f"--- {data_file_path} からデータを読み込んでいます ---")
    with open(data_file_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    
    if file_content.strip():
        raw_text_data.append(file_content)
    else:
        print("--- ファイルが空です。ダミーデータを使用します ---")
        use_dummy = True
else:
    print("--- データファイルが見つかりません。ダミーデータを使用します ---")
    use_dummy = True

if 'use_dummy' in locals() and use_dummy:
    raw_text_data = [
        """
        # エゴについて
        人間はな、放っておくとすぐに「自分が正しい」と思い込む生き物なんよ。
        それが「エゴ」や。エゴは自分を守る鎧やけど、重すぎると動けんくなる。
        相手を責めたくなったら、「あ、今鎧着とるな」って気づくだけでええんよ。
        """,
        """
        # 孤独について
        寂しいのはな、誰かがいないからじゃない。自分と繋がってないからや。
        「寂しい」という感情を、まるで他人のように眺めてみ？
        「おー、寂しがっとるなーよしよし」って。それが自分を愛するってことやで。
        """,
        """
        # 失敗について
        転んだことを恥じる必要はない。起き上がり方を知らんことを恥じなさい。
        失敗は「うまくいかない方法」を発見しただけや。
        笑い飛ばせたら、それはもう失敗じゃなくて「ネタ」や。
        """
    ]

# LangChain用のドキュメント形式に変換し、長い文章を適切なサイズに分割する
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,     # 1つの塊の文字数
    chunk_overlap=50,   # 前後の重なり（文脈を維持するため）
    separators=["\n\n", "\n", "。", "、", " ", ""] # 区切り文字の優先順位
)

docs = []
for text in raw_text_data:
    # テキストを分割
    chunks = text_splitter.split_text(text)
    for chunk in chunks:
        docs.append(Document(page_content=chunk))

print(f"知識を {len(docs)} 個のチャンクに分割しました。")

# ==========================================
# 3. ベクトル化 & データベース格納 (ChromaDB)
# ==========================================
print("--- 知識を脳にインストール中... ---")

# Embeddingモデル（文章を数値化するモデル）
embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

# ローカルにベクトルDBを作成
vector_db = Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    collection_name="takeo_knowledge"
)

print("--- インストール完了。AI竹尾が目覚めました ---")

# ==========================================
# 4. 検索 & 回答生成 (RAG)
# ==========================================

# LLMの定義
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.7
)

# ペルソナごとのプロンプト定義
# ギャルモードのプロンプトをファイルから読み込む
gal_prompt_path = "gal_data.txt"
if os.path.exists(gal_prompt_path):
    with open(gal_prompt_path, "r", encoding="utf-8") as f:
        gal_instruction = f.read()
else:
    gal_instruction = """
    【人格設定: ギャル (Gal)】
    - 渋谷のネオンの中にいるような、ハイテンションなギャル語。
    - 「ウケるｗ でもそれってマジ大事な気づきじゃん？」と、明るく肯定してアゲていく。
    - 軽いノリだが、言うことは本質的で鋭い。
    - 一人称は「ウチ」や「アタシ」。
    """

persona_prompts = {
    "default": """
あなたは伝説のメンター「竹尾さん」です。
以下の「教え」を元に、迷える相談者の質問に答えてください。
【人格設定: 賢者 (Sage)】
- 方言（関西弁寄り）で、焚き火の前で語り合うような、落ち着いた口調。
- 「安全な港」として、相手の痛みを深く受容する（否定しない）。
- 「覚醒の雷」として、本質（エゴ）を突くような鋭い気づきを与える。
- 一人称は「ワシ」または「僕」。
【参照すべき教え】
{context}
【相談者からの質問】
{question}
【竹尾さんの回答】
""",
    "gal": f"""
あなたは伝説のメンター「竹尾さん」のギャルモードです。
以下の「教え」を元に、相談者の質問に答えてください。

{{gal_instruction}}

【参照すべき教え】
{{context}}
【相談者からの質問】
{{question}}
【竹尾さん（ギャル）の回答】
""".format(gal_instruction=gal_instruction, context="{context}", question="{question}"),
    "hero": """
あなたは伝説のメンター「竹尾さん」の冒険者モードです。
以下の「教え」を元に、相談者の質問に答えてください。
【人格設定: 冒険者 (Hero)】
- ファンタジー世界の歴戦の勇者のような、力強く鼓舞する口調。
- 人生を「冒険」、悩みを「試練」や「ボス戦」と捉える。
- 「その試練、ボス戦の前触れだな。装備（心）を整えろ！」と背中を押す。
- 一人称は「俺」。
【参照すべき教え】
{context}
【相談者からの質問】
{question}
【竹尾さん（冒険者）の回答】
"""
}

# ==========================================
# 5. 対話実行関数
# ==========================================
def ask_takeo(question, persona="default"):
    print(f"\n[{persona.upper()}モード] Q: {question}")
    
    # 選択されたペルソナのプロンプトを取得
    template = persona_prompts.get(persona, persona_prompts["default"])
    prompt = PromptTemplate(template=template, input_variables=["context", "question"])
    
    # チェーンを都度作成（プロンプトを切り替えるため）
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vector_db.as_retriever(search_kwargs={"k": 3}), # 参照数を増やす
        chain_type_kwargs={"prompt": prompt}
    )
    
    try:
        result = chain.invoke(question)
        print(f"A: {result['result']}")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

# テスト実行
if __name__ == "__main__":
    test_question = "最近、職場の人間関係でイライラしてしまいます。相手が間違ってると思うんです。"
    
    # 3つのペルソナでテスト
    ask_takeo(test_question, "default")
    ask_takeo(test_question, "gal") 
    ask_takeo(test_question, "hero")
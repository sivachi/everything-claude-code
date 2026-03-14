import os
import faiss
from sentence_transformers import SentenceTransformer

# Apple Silicon対応 (from rag.py)
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def test():
    print("Loading model...")
    model = SentenceTransformer(
        "cl-nagoya/ruri-v3-310m",
        device="mps",
        trust_remote_code=True,
    )
    print("Model loaded (device=mps).")
    
    sentences = ["これはテストです。", "This is a test."]
    print("Encoding...")
    embeddings = model.encode(sentences, normalize_embeddings=True)
    print(f"Encoded shape: {embeddings.shape}")
    print("Done.")

if __name__ == "__main__":
    test()

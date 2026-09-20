import os
import json
import numpy as np
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

RAW_DIR = "reports/hw03/raw"
OUTPUT_DIR = "reports/hw03/raw"

def load_sentence_chunks():
    path = os.path.join(RAW_DIR, "sentence_chunks.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_embedding_matrix(chunks):
    embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

    ids = []
    texts = []
    metadatas = []
    embeddings = []

    for ch in chunks:
        text = ch["text"]
        emb = embed_model.get_text_embedding(text)

        ids.append(ch["chunk_id"])
        texts.append(text)
        metadatas.append(ch.get("metadata", {}))
        embeddings.append(emb)

    embeddings = np.array(embeddings)
    return ids, texts, metadatas, embeddings

if __name__ == "__main__":
    chunks = load_sentence_chunks()
    print(f"Loaded {len(chunks)} sentence-window chunks...")

    ids, texts, metadatas, emb_matrix = build_embedding_matrix(chunks)

    print("\nEmbedding matrix shape:", emb_matrix.shape)
    print("Embedding dimension:", emb_matrix.shape[1])
    print("First 8 values of first embedding:", emb_matrix[0][:8])

    np.save(os.path.join(OUTPUT_DIR, "sentence_embeddings.npy"), emb_matrix)

    with open(os.path.join(OUTPUT_DIR, "sentence_index_ids.json"), "w", encoding="utf-8") as f:
        json.dump(ids, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "sentence_index_texts.json"), "w", encoding="utf-8") as f:
        json.dump(texts, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "sentence_index_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadatas, f, indent=2)

    print("\nSaved sentence_embeddings.npy, sentence_index_ids.json, sentence_index_texts.json, sentence_index_metadata.json")
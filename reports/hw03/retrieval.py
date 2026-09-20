# Information about this file
'''
Loads  question from questions.yaml
For each chunking technique:
loads embeddings
loads texts
computes cosine similarities
returns top‑k
records latency
prints results
saves results

'''
import os
import json
import time
import numpy as np
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

RAW_DIR = "reports/hw03/raw"

# ----------------------------
# Utility: cosine similarity
# ----------------------------
def cosine_sim(a, b):
    a = np.array(a); b = np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

# ----------------------------
# Load ID/text pairs
# ----------------------------
def load_chunks(prefix):
    embeddings = np.load(os.path.join(RAW_DIR, f"{prefix}_embeddings.npy"))
    with open(os.path.join(RAW_DIR, f"{prefix}_index_ids.json"), "r", encoding="utf-8") as f:
        ids = json.load(f)
    with open(os.path.join(RAW_DIR, f"{prefix}_index_texts.json"), "r", encoding="utf-8") as f:
        texts = json.load(f)
    return ids, texts, embeddings

# ----------------------------
# Retrieval function
# ----------------------------
def retrieve(prefix, query, k=5):
    ids, texts, embeddings = load_chunks(prefix)

    embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    q_emb = embed_model.get_query_embedding(query)

    print(f"\n=== {prefix.upper()} RETRIEVAL ===")
    print(f"Query embedding dimension: {len(q_emb)}")
    print(f"First 8 values: {q_emb[:8]}")

    start = time.time()

    scores = []
    for i, emb in enumerate(embeddings):
        sim = cosine_sim(q_emb, emb)
        scores.append((sim, ids[i], texts[i]))

    scores.sort(key=lambda x: x[0], reverse=True)
    results = scores[:k]

    latency = (time.time() - start) * 1000  # ms
    print(f"Retrieval latency: {latency:.2f} ms")

    out = []
    for rank, (sim, cid, text) in enumerate(results, start=1):
        out.append({
            "rank": rank,
            "chunk_id": cid,
            "cosine_similarity": sim,
            "chunk_length": len(text),
            "preview": text[:160]
        })

        print(f"\nRank {rank}:")
        print(f"  chunk_id: {cid}")
        print(f"  cosine_similarity: {sim:.4f}")
        print(f"  chunk_length: {len(text)}")
        print(f"  preview: {text[:160]}")

    # save results
    out_path = os.path.join(RAW_DIR, f"{prefix}_retrieval.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\nSaved results to {out_path}")
    return out, latency

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    # The main graded query in HW3
    query = "What are the required daily cleaning tasks for restaurant food preparation areas?"

    prefixes = ["token", "semantic", "sentence"]

    for p in prefixes:
        retrieve(p, query, k=5)
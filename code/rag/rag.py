import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from textwrap import dedent
from langchain_ollama import OllamaLLM

# ----------------------------
# 1. Load Corpus
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOC_PATH = os.path.join(BASE_DIR, "documents")
OUTPUT_RAW = os.path.join(BASE_DIR, "..", "..", "reports", "hw04", "raw")

os.makedirs(OUTPUT_RAW, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "embeddings"), exist_ok=True)

documents = []
for filename in sorted(os.listdir(DOC_PATH)):
    if filename.endswith(".txt"):
        with open(os.path.join(DOC_PATH, filename), "r", encoding="utf-8") as f:
            documents.append((filename, f.read()))

print(f"Loaded {len(documents)} documents: {[d[0] for d in documents]}")


# ----------------------------
# 2. Chunking (size 500, overlap 50)
# ----------------------------
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def chunk_document(text, source):
    chunks = []
    start = 0
    id_counter = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        chunks.append({
            "chunk_id": f"{source}_chunk_{id_counter}",
            "text": chunk_text,
            "source": source
        })
        start = end - CHUNK_OVERLAP
        id_counter += 1
    return chunks

all_chunks = []
for source, text in documents:
    all_chunks.extend(chunk_document(text, source))

print(f"Created {len(all_chunks)} chunks total.")

with open(os.path.join(BASE_DIR, "chunk_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(all_chunks, f, indent=2)


# ----------------------------
# 3. Embeddings & FAISS Index
# ----------------------------
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

texts = [c["text"] for c in all_chunks]
emb = embed_model.encode(texts, convert_to_numpy=True)
dimension = emb.shape[1]

index = faiss.IndexFlatL2(dimension)
index.add(emb)

np.save(os.path.join(BASE_DIR, "embeddings", "vectors.npy"), emb)
with open(os.path.join(BASE_DIR, "embeddings", "ids.json"), "w", encoding="utf-8") as f:
    json.dump([c["chunk_id"] for c in all_chunks], f, indent=2)


# ----------------------------
# 4. Retrieval Function
# ----------------------------
def retrieve_topk(question, k=3):
    q_emb = embed_model.encode([question], convert_to_numpy=True)
    scores, idx = index.search(q_emb, k)

    retrieved = []
    for rank, chunk_idx in enumerate(idx[0]):
        c = all_chunks[chunk_idx]
        retrieved.append({
            "rank": rank + 1,
            "chunk_id": c["chunk_id"],
            "source": c["source"],
            "text": c["text"],
            "score": float(scores[0][rank])  # L2 distance: lower = closer match
        })

    return retrieved


# ----------------------------
# 5. LLM Initialization
# ----------------------------
def get_llm_basic(model_name="qwen2.5:1.5b", temperature=0.0):
    try:
        return OllamaLLM(model=model_name, temperature=temperature)
    except Exception as e:
        raise RuntimeError(f"Failed to load model '{model_name}': {e}")

def get_llm(model_name="qwen2.5:1.5b", temperature=0.0):
    try:
        return OllamaLLM(
            model=model_name, 
            temperature=temperature,
            num_predict=150,      # Caps response length to 150 tokens max
            repeat_penalty=1.15   # Prevents infinite repetition loops
        )
    except Exception as e:
        raise RuntimeError(f"Failed to load model '{model_name}': {e}")

_llm_instance = get_llm()

def llm(prompt: str):
    try:
        return _llm_instance.invoke(prompt)
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}")


# ----------------------------
# 6. Three LLM Configurations
# ----------------------------
def config_A_no_rag(question):
    prompt = f"Answer the question: {question}"
    return llm(prompt)


def config_B_basic_rag(question, retrieved):
    context = "\n\n".join([f"[CHUNK] {r['text']}" for r in retrieved])
    prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer using the above chunks."
    return llm(prompt)


def config_C_context_engineered_rag(question, retrieved):
    # Drop duplicate chunks
    seen = set()
    filtered = []
    for r in retrieved:
        if r["chunk_id"] not in seen:
            filtered.append(r)
            seen.add(r["chunk_id"])

    # Number and label sources clearly for citation
    context_blocks = []
    for idx, r in enumerate(filtered, start=1):
        context_blocks.append(f"[Source {idx}: {r['source']} (Chunk: {r['chunk_id']})]\n{r['text']}")
    
    context = "\n\n".join(context_blocks)

    grounding_rules = dedent("""
    - Answer the question using ONLY the evidence in the provided context.
    - Cite the source number (e.g., [Source 1]) for any factual claim made.
    - If the evidence is insufficient, missing, or unrelated to the context, output exactly:
      "I cannot answer this question from the provided documents".
    """)

    prompt = f"Context:\n{context}\n\nGrounding Rules:\n{grounding_rules}\n\nQuestion: {question}\nAnswer:"
    return llm(prompt)


# ----------------------------
# 7. Six Test Questions Evaluation
# ----------------------------
questions = [
    {"id": "Q1", "type": "Single Chunk", "q": "What are the required daily cleaning tasks for restaurant food preparation areas?"},
    {"id": "Q2", "type": "Two Chunks", "q": "Why did the display case cooling failure at Rangoli Sweets violate county temperature standards?"},
    {"id": "Q3", "type": "Multi-Doc", "q": "What signs of pest activity have been identified in restaurant inspections?"},
    {"id": "Q4", "type": "Ambiguous", "q": "Under what conditions should a restaurant be temporarily closed?"},
    {"id": "Q5", "type": "Not in Docs", "q": "What are the minimum wage and overtime pay requirements for kitchen staff?"},
    {"id": "Q6", "type": "Unrelated", "q": "How do I assess the value of a single family home in Santa Clara County?"}
]

six_results = []

print("\n=== RUNNING 6-QUESTION COMPARISON ===")
for q_info in questions:
    q_id = q_info["id"]
    q_text = q_info["q"]
    print(f"\nProcessing {q_id}: {q_text}")
    
    retrieved = retrieve_topk(q_text, k=3)
    
    # Print top-k retrievals to console prior to LLM calls
    print(f"--- Top-{len(retrieved)} Retrieved Chunks ---")
    for r in retrieved:
        print(f"  Rank {r['rank']} | Source: {r['source']} | Score (L2): {r['score']:.4f} | ID: {r['chunk_id']}")

    A_ans = config_A_no_rag(q_text)
    B_ans = config_B_basic_rag(q_text, retrieved)
    C_ans = config_C_context_engineered_rag(q_text, retrieved)

    six_results.append({
        "id": q_id,
        "type": q_info["type"],
        "question": q_text,
        "retrieved_chunks": retrieved,
        "config_A_no_rag": A_ans,
        "config_B_basic_rag": B_ans,
        "config_C_context_engineered": C_ans
    })

# Save 6-question results
with open(os.path.join(OUTPUT_RAW, "six_question_results.json"), "w", encoding="utf-8") as f:
    json.dump(six_results, f, indent=2)


# ----------------------------
# 8. Top-k Sweep (k = 1, 3, 5)
# ----------------------------
sweep_question = "What are the required daily cleaning tasks for restaurant food preparation areas?"
ksweep_results = []

print("\n=== RUNNING K-SWEEP (k = 1, 3, 5) ===")
for k in [1, 3, 5]:
    print(f"Running k-sweep for k={k}...")
    ret = retrieve_topk(sweep_question, k=k)
    answer = config_C_context_engineered_rag(sweep_question, ret)
    ksweep_results.append({
        "k": k,
        "question": sweep_question,
        "retrieved_chunks": ret,
        "generated_answer": answer
    })

# Save k-sweep results
with open(os.path.join(OUTPUT_RAW, "k_sweep.json"), "w", encoding="utf-8") as f:
    json.dump(ksweep_results, f, indent=2)

print("\nRAG pipeline run complete. All raw results successfully written to:", OUTPUT_RAW)
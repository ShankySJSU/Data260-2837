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
DOC_PATH = os.path.join(os.path.dirname(__file__), "documents")
OUTPUT_RAW = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "hw04", "raw")

os.makedirs(OUTPUT_RAW, exist_ok=True)

documents = []
for filename in os.listdir(DOC_PATH):
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

with open(os.path.join(os.path.dirname(__file__), "chunk_manifest.json"), "w") as f:
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

# Persist embeddings (matches your existing embeddings/ folder structure)
np.save(os.path.join(os.path.dirname(__file__), "embeddings", "vectors.npy"), emb)
with open(os.path.join(os.path.dirname(__file__), "embeddings", "ids.json"), "w") as f:
    json.dump([c["chunk_id"] for c in all_chunks], f, indent=2)


# ----------------------------
# 4. Retrieval Function
# ----------------------------
# NOTE: IndexFlatL2 returns squared Euclidean DISTANCE, not similarity.
# LOWER score = better/closer match. Keep this in mind when writing your analysis.
def retrieve_topk(question, k=3):
    q_emb = embed_model.encode([question], convert_to_numpy=True)
    scores, idx = index.search(q_emb, k)

    retrieved = []
    for rank, chunk_idx in enumerate(idx[0]):
        c = all_chunks[chunk_idx]
        retrieved.append({
            "rank": rank,
            "chunk_id": c["chunk_id"],
            "source": c["source"],
            "text": c["text"],
            "score": float(scores[0][rank])  # lower = better match
        })

    return retrieved


# ----------------------------
# 5. Real LLM via Ollama (reusing HW2's model choice for consistency)
# ----------------------------
def get_llm(model_name="qwen2.5:1.5b", temperature=0.0):
    """
    Returns an LLM adapter for RAG generation.
    temperature=0.0 (not HW2's 0.7) so refusal behavior on Q5/Q6
    is deterministic rather than creatively hallucinating an answer.
    """
    try:
        return OllamaLLM(model=model_name, temperature=temperature)
    except Exception as e:
        raise RuntimeError(f"Failed to load model '{model_name}': {e}")

_llm_instance = get_llm()

def llm(prompt: str):
    """Unified call, same pattern as HW2's call_llm."""
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
    # drop duplicate chunks (same chunk_id retrieved more than once)
    seen = set()
    filtered = []
    for r in retrieved:
        if r["chunk_id"] not in seen:
            filtered.append(r)
            seen.add(r["chunk_id"])

    context = "\n\n".join([
        f"[Source: {r['source']}]\n{r['text']}"
        for r in filtered
    ])

    grounding_rules = dedent("""
    - Use only the provided context.
    - Cite the source for any claim you make.
    - If the evidence is insufficient or missing, answer exactly:
      "I cannot answer this question from the provided documents".
    """)

    prompt = f"Context:\n{context}\n\nGrounding Rules:\n{grounding_rules}\n\nQuestion: {question}\nAnswer:"
    return llm(prompt)


# ----------------------------
# 7. Six Homework Questions
# ----------------------------
# TODO: verify against your actual documents/ content before final run:
#   - Q4 should be genuinely AMBIGUOUS (multiple valid interpretations in your corpus)
#   - Q5 must be UNANSWERABLE from your corpus (pick a topic your docs don't cover)
old_questions = [
    "Q1: What is the daily cleaning requirement?",
    "Q2: Which two procedures must be combined for sanitization?",
    "Q3: What are two similar pest-control indicators across documents?",
    "Q4: Under what conditions should a restaurant be closed?",
    "Q5: What is the recommended cooking temperature for poultry?",
    "Q6: How do I repair a crashed Linux kernel?"
]

questions = [
    "Q1: What are the required daily cleaning tasks for restaurant food preparation areas?",
    "Q2: Why did the display case cooling failure at Rangoli Sweets violate county temperature standards?",
    "Q3: What signs of pest activity have been identified in restaurant inspections?",
    "Q4: Under what conditions should a restaurant be temporarily closed?",
    "Q5: What are the minimum wage and overtime pay requirements for kitchen staff?",
    "Q6: How do I repair a crashed Linux kernel?"
]
six_results = []

for q in questions:
    print(f"Processing: {q}")
    retrieved = retrieve_topk(q, k=3)

    A = config_A_no_rag(q)
    B = config_B_basic_rag(q, retrieved)
    C = config_C_context_engineered_rag(q, retrieved)

    six_results.append({
        "question": q,
        "retrieved": retrieved,
        "config_A_no_rag": A,
        "config_B_basic_rag": B,
        "config_C_context_engineered": C
    })

with open(os.path.join(OUTPUT_RAW, "six_question_results.json"), "w") as f:
    json.dump(six_results, f, indent=2)


# ----------------------------
# 8. Top-k sweep (k = 1, 3, 5) — now captures the actual generated answer too
# ----------------------------
sweep_question = "What is the cleaning requirement?"
ksweep_results = []

for k in [1, 3, 5]:
    print(f"Running k-sweep for k={k}")
    ret = retrieve_topk(sweep_question, k=k)
    answer = config_C_context_engineered_rag(sweep_question, ret)
    ksweep_results.append({
        "k": k,
        "question": sweep_question,
        "chunks": ret,
        "answer": answer
    })

with open(os.path.join(OUTPUT_RAW, "k_sweep.json"), "w") as f:
    json.dump(ksweep_results, f, indent=2)

print("RAG pipeline run complete. Results saved to:", OUTPUT_RAW)
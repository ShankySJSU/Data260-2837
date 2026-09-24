import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from textwrap import dedent

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


with open(os.path.join(os.path.dirname(__file__), "chunk_manifest.json"), "w") as f:
    json.dump(all_chunks, f, indent=2)


# ----------------------------
# 3. Embeddings & FAISS Index
# ----------------------------
model = SentenceTransformer("all-MiniLM-L6-v2")

texts = [c["text"] for c in all_chunks]
emb = model.encode(texts, convert_to_numpy=True)
dimension = emb.shape[1]

index = faiss.IndexFlatL2(dimension)
index.add(emb)


# ----------------------------
# 4. Retrieval Function
# ----------------------------
def retrieve_topk(question, k=3):
    q_emb = model.encode([question], convert_to_numpy=True)
    scores, idx = index.search(q_emb, k)

    retrieved = []
    for rank, chunk_idx in enumerate(idx[0]):
        c = all_chunks[chunk_idx]
        retrieved.append({
            "rank": rank,
            "chunk_id": c["chunk_id"],
            "source": c["source"],
            "text": c["text"],
            "score": float(scores[0][rank])
        })

    return retrieved


# ----------------------------
# 5. Three LLM Configurations
# ----------------------------

def llm(prompt):
    """Simulated LLM call via a stub.
    Replace with OpenAI / llama3 API if desired.
    """
    return f"[LLM OUTPUT SIMULATED]\n{prompt}"


def config_A_no_rag(question):
    prompt = f"Answer the question: {question}"
    return llm(prompt)


def config_B_basic_rag(question, retrieved):
    context = "\n\n".join([f"[CHUNK] {r['text']}" for r in retrieved])
    prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer using the above chunks."
    return llm(prompt)


def config_C_context_engineered_rag(question, retrieved):
    # drop duplicates or irrelevant chunks
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
    - Cite the chunk using its source.
    - If insufficient evidence: answer "I cannot answer this question from the provided documents".
    """)

    prompt = f"Context:\n{context}\n\nGrounding Rules:\n{grounding_rules}\n\nQuestion: {question}\nAnswer:"
    return llm(prompt)


# ----------------------------
# 6. Six Homework Questions
# ----------------------------
questions = [
    "Q1: What is the daily cleaning requirement?",
    "Q2: Which two procedures must be combined for sanitization?",
    "Q3: What are two similar pest-control indicators across documents?",
    "Q4: Under what conditions should a restaurant be closed?",
    "Q5: What is the recommended cooking temperature for poultry?",
    "Q6: How do I repair a crashed Linux kernel?"
]

# evaluation storage
six_results = []


# ----------------------------
# 7. Run evaluation
# ----------------------------
for q in questions:
    retrieved = retrieve_topk(q, k=3)

    A = config_A_no_rag(q)
    B = config_B_basic_rag(q, retrieved)
    C = config_C_context_engineered_rag(q, retrieved)

    six_results.append({
        "question": q,
        "retrieved": retrieved,
        "config_A": A,
        "config_B": B,
        "config_C": C
    })


with open(os.path.join(OUTPUT_RAW, "six_question_results.json"), "w") as f:
    json.dump(six_results, f, indent=2)


# ----------------------------
# 8. Top-k sweep (k = 1,3,5)
# ----------------------------
ksweep_results = []

for k in [1, 3, 5]:
    ret = retrieve_topk("Sweep: What is the cleaning requirement?", k=k)
    ksweep_results.append({
        "k": k,
        "chunks": ret
    })

with open(os.path.join(OUTPUT_RAW, "k_sweep.json"), "w") as f:
    json.dump(ksweep_results, f, indent=2)


print("RAG pipeline run complete.")
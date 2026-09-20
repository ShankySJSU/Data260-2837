# METRICS.md – Homework 3
SID4: 2837  
Student: Shashank Ranjan  

# DATA260 – HW3 Retrieval Metrics
Domain: Restaurant Inspection

## Query Used
"What are the required daily cleaning tasks for restaurant food preparation areas?"

---

# 1. Retrieval Quality Comparison

## Summary Table

| Technique          | #Chunks | Avg Chunk Length | Top‑1 Cosine | Mean@5 Cosine | Recall@5 | Latency (ms) |
|-------------------|---------|------------------|--------------|---------------|----------|--------------|
| Token             | 30      | ~2000 chars      | 0.6995       | 0.6380        | 5/5      | 0.92         |
| Semantic          | 32      | ~1600 chars      | 0.6995       | 0.6551        | 5/5      | 0.98         |
| Sentence-window   | 415     | ~200 chars       | **0.7179**   | **0.6762**    | 5/5      | 10.83        |

---

# 2. Observations

1. **Sentence-window chunking produced the highest Top‑1 and Mean@5 cosine similarity.**  
   This is expected because smaller chunks with neighbor context preserve high semantic relevance without dilution from unrelated text.

2. **Semantic chunking outperformed token chunking.**  
   SemanticSplitterNodeParser creates coherent boundaries aligned with meaning, producing more conceptually focused chunks.

3. **Token chunking performed worst among the three**, though still acceptable.  
   Because tokens are split purely by size, chunks contain mixed topics which lowers cosine similarity.

4. **Sentence-window has highest latency**, because it creates 415 chunks (far more comparisons).  
   Despite this, its accuracy is best.

---

# 3. Example of Incorrect High-Scoring Retrieval (Required by HW3)

The following sentence-window chunk scored **0.6612**, even though it does *not* contain the answer:

Preview:

SECTION 3 — FOOD PREPARATION AREA
The primary kitchen was significantly cleaner than previous visits, showing evidence of improved compliance.

This chunk does NOT describe daily cleaning tasks, yet similarity is high.  
This happened because the query includes “cleaning” and “preparation areas,” and the embedding model finds the chunk semantically close — even without containing the correct answer.

---

# 4. Conclusion

**Sentence-window chunking is the best technique for this restaurant inspection corpus.**

Reasons:
- Highest top‑1 retrieval score  
- Highest mean@k score  
- Best alignment with precise regulatory content  
- Smaller chunks allow more accurate cosine comparison  
- Context window preserves meaning without dilution  

Token chunking is least effective because chunk boundaries do not follow semantic structure.

Semantic chunking performs well but still produces larger chunks than optimal for fine-grained regulatory queries.

---

# 5. AI_USE Required Reflections

1. **What AI assistant was used?**  
   LLM was used to help generate corpus files, chunkers, vector indexing, retrieval pipeline, and metrics interpretation.

2. **One wrong AI-produced output I corrected:**  
   LlamaIndex vector store code required refactoring due to API changes (SimpleVectorStore, FAISS import).  
   I corrected chunk indexing by using embedding matrices and manual cosine similarity.

3. **How I detected the problem:**  
   The SimpleVectorStore.add() error indicated that the API changed and no longer accepted (id, embedding, node).  
   Also FAISS imports were unavailable in this environment.

4. **What I changed & why it works now:**  
   I migrated to a stable approach using HuggingFace embeddings + NumPy cosine similarity.  
   This is version-agnostic and works consistently across LlamaIndex releases.

---

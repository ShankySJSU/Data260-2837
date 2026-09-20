# DATA 260 – Homework Repository  
SID4: 2837  
Student: Shashank Ranjan  
Domain: Restaurant Inspection

This repository contains all completed work for DATA260 (Homework 1, Homework 2, and Homework 3).  
Each homework builds on the previous one, eventually producing a full FastAPI authentication app and a complete RAG retrieval pipeline using three chunking techniques from LlamaIndex.

---

# 📁 Repository Structure


Data260-2837/
│
├── code/
│   ├── web_application/
│   │   ├── hw2_main.py
│   │   ├── hw3_main.py
│   │   ├── auth.py
│   │   └── templates/
│   │        ├── index.html
│   │        ├── login.html
│   │        └── dashboard.html
│   └── (HW1/HW2 agent files, JS, and support code)
│
├── reports/
│   ├── hw01/
│   ├── hw02/
│   └── hw03/
│        ├── corpus/
│        ├── raw/
│        ├── token_chunker.py
│        ├── semantic_chunker.py
│        ├── sentence_window_chunker.py
│        ├── token_index.py
│        ├── semantic_index.py
│        ├── sentence_window_index.py
│        ├── retrieval.py
│        ├── METRICS.md
│        ├── RUN_LOG.txt
│        ├── verification.json
│        ├── SOURCES.md
│        ├── CORPUS_MANIFEST.json
│        └── questions.yaml
│
└── README.md  ← this file

---

# 🔧 Installation

### 1. Clone the Repository

git clone https://github.com/ShankySJSU/Data260-2837.git
cd Data260-2837

### 2. Install Requirements
You must have Python ≥ 3.10.


pip install -r requirements.txt

OR manually install:


pip install fastapi uvicorn python-dotenv
pip install llama-index
pip install llama-index-embeddings-huggingface
pip install sentence-transformers
pip install numpy
pip install faiss-cpu   # optional; not required for HW3 final indexing approach

---

# 🚀 Running Homework 3 (Authentication App)

From the project root:


uvicorn code.web_application.hw3_main:app --reload --port 8137

SID4 = 2837 → PORT_BASE = 8137.

### URLs:
- Home: http://127.0.0.1:8137/
- Login: http://127.0.0.1:8137/login
- Dashboard (protected): http://127.0.0.1:8137/dashboard
- Logout: http://127.0.0.1:8137/logout

### Test credentials:

Username: admin
Password: password

---

# 🔐 HW3 Authentication Features
- FastAPI + SessionMiddleware  
- Secure cookie  
- Idle timeout (120 seconds)  
- Bootstrap-styled pages  
- Login error alerts  
- Session expired alerts  
- Protected dashboard  
- Templates stored under /code/web_application/templates/

---

# 📚 HW3 RAG Pipeline (Chunking + Retrieval)

### 1. Build all chunkers

python reports/hw03/token_chunker.py
python reports/hw03/semantic_chunker.py
python reports/hw03/sentence_window_chunker.py

### 2. Build embedding matrices / vector indexes

python reports/hw03/token_index.py
python reports/hw03/semantic_index.py
python reports/hw03/sentence_window_index.py

### 3. Run retrieval for the main graded query

python reports/hw03/retrieval.py

### Outputs saved under:

reports/hw03/raw/

This includes:

- token_embeddings.npy  
- semantic_embeddings.npy  
- sentence_embeddings.npy  
- token_retrieval.json  
- semantic_retrieval.json  
- sentence_retrieval.json  
- token_chunks.json / semantic_chunks.json / sentence_chunks.json

---

# 📝 Required HW3 Supporting Files

| File | Description |
|------|-------------|
| METRICS.md | Retrieval metrics table + conclusion |
| RUN_LOG.txt | Full execution logs |
| verification.json | HW3 verification checks |
| CORPUS_MANIFEST.json | Byte size + SHA256 hash for corpus |
| SOURCES.md | Source descriptions |
| questions.yaml | Five domain‑specific retrieval questions |
| corpus/ | All ≥ 200KB text files used for chunking |

---

# 📘 HW1 + HW2 Summary (for TA review)

### HW1  
- Agent pipeline (planner + reviewer)  
- Non-determinism study  
- Output stored in reports/hw01/

### HW2  
- FastAPI CRUD app  
- Restaurant inspection JSON store  
- Frontend + JS validation  
- Output stored in reports/hw02/

### HW3  
- Authentication  
- Bootstrap styling  
- Session timeout  
- Three chunking techniques  
- LlamaIndex retrieval  
- Metrics and analysis  
- Full 200KB+ corpus  
- Output stored in reports/hw03/

---

# 🧠 AI_USE Reflection (Short Summary)

- Used AI to generate chunkers, corpus, retrieval scripts, and METRICS.md.
- Corrected model-version errors involving SimpleVectorStore and FAISS by switching to stable embedding-matrix + cosine similarity approach.
- Verified pipeline using RUN_LOG.txt and verification.json.

---

# ✔ Final Notes

This repository satisfies all requirements for Homework 1, Homework 2, and Homework 3, including:

- Authentication app  
- Bootstrap styling  
- Session management  
- Three chunking strategies  
- Retrieval-only comparison  
- Full RAG evaluation  
- Required metadata files  
- Verified reproducibility  
- Organized directory structure  

Please refer to `reports/hw03/` for complete HW3 artifacts and `Ranjan_HW3.pdf` for the final written submission.

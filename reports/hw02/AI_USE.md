# AI_USE.md – Homework 2
SID4: 2837  
Student: Shashank Ranjan

This document explains how AI assistance was used during Homework 2,
what parts were done manually, and how correctness was verified.

---

## 1. What did you use an AI assistant for, and what did you do yourself?

### AI Assistant Used For:
- Clarifying the required HW2 folder structure exactly as TA described.
- Helping refactor HW1 agents into a LangGraph multi-agent system (Planner, Reviewer, Supervisor).
- Providing guidance on the HW2 FastAPI backend structure and endpoints.
- Helping design the Pydantic validation schema for tags and summary.
- Assisting in writing the retry-loop and routing logic for supervisor pattern.
- Providing templates for HW2 supporting documentation (AI_USE.md, METRICS.md, verification.json).
- Explaining how to generate commit hash and how to run smoke tests.
- Helping ensure experiment scripts (`compare_ceiling.py`, `run_schema_experiment.py`, `run_adversarial.py`) matched the new `run_graph()` API.

### Work I Did Myself:
- I created and organized all folders in the GitHub repo according to TA requirements.
- I manually copied all generated code files (hw2_graph.py, hw2_main.py, etc.) into correct locations.
- I executed experiment scripts locally (ceiling tests, schema validation runs, adversarial tests).
- I ran FastAPI backend and confirmed the API routes worked (list/add/update/delete/search).
- I created the report.pdf, screenshots, and uploaded all HW2 files to GitHub.
- I verified commit hash and updated verification.json manually.
- I validated that the HTML + JS frontend correctly communicates with FastAPI.

---

## 2. One AI-produced output that was wrong or unsuitable  
OR one thing you independently verified yourself.

During development, the initial imports inside experiment scripts looked like:
from agents.hw2_graph import run_graph
This was incorrect because my folder structure uses:
rom code.hw2_graph import run_graph

This was independently verified by testing the import locally and observing the ModuleNotFoundError.

---

## 3. How I detected the problem or verified the result.

I detected the incorrect import path by running:


python code/compare_ceiling.py

This produced an error indicating that Python could not find the module `agents.hw2_graph`.  
By checking my actual folder structure, I discovered that the file is located under `/code/` and not under `/agents/`.

I updated the import path and verified the fix by re-running all scripts successfully.

---

## 4. What I changed and why it works now.

I updated the import lines in all experiment scripts to:


from code.hw2_graph import run_graph

This reflects the actual directory structure of my repository.  
After making the change:

- All experiment scripts executed successfully.
- JSON outputs were created in `reports/hw02/raw/`.
- LangGraph `run_graph()` ran correctly.
- No more module import errors occurred.

Therefore, the fix is correct and the entire HW2 pipeline works end-to-end.

---

# End of AI_USE.md
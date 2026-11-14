"""HW10 configuration. Section 0 values are unchanged (PREFIX s2837, PORT_BASE 8137, SEED 2837).

HW10 adds no new identifiers: the HW8 correlation_id is the trace_id everywhere.
"""

import os
from pathlib import Path

from .. import hw09_config as h9

STUDENT_NAME = h9.STUDENT_NAME
SID4 = h9.SID4
PREFIX = h9.PREFIX  # s2837
PORT_BASE = h9.PORT_BASE  # 8137
SEED = h9.SEED  # 2837
DASHBOARD_PORT = PORT_BASE + 2  # 8139 (8137 = HW8 API, 8138 = HW9 API)

# ---------------- paths ----------------
REPO_ROOT = h9.REPO_ROOT
REPORT_DIR = Path(os.getenv("HW10_REPORT_DIR", REPO_ROOT / "reports" / "hw10"))
RAW_DIR = REPORT_DIR / "raw"
RUN_LOG = REPORT_DIR / "RUN_LOG.txt"
SPAN_FILE = Path(os.getenv("HW10_SPAN_FILE", RAW_DIR / "spans.jsonl"))  # one JSON span per line
DIRECT_MESSAGES = RAW_DIR / "direct_messages.jsonl"  # only written by the no-Kafka debug mode

# Part 3 frozen files (committed BEFORE any judge score exists)
EVAL_CASES = REPORT_DIR / "eval_cases.json"
HUMAN_LABELS = REPORT_DIR / "human_labels.csv"
JUDGE_SCORES = REPORT_DIR / "judge_scores.csv"

# raw result files
EVAL_RESULTS = "eval_results.json"  # Part 2 (+ evaluations done in Part 4)
PART3_FILE = "part3_validation.json"
TRACES_FILE = "part4_traces.json"
LATENCY_FILE = "part4_latency.json"

# ---------------- request path ----------------
# kafka  = HW8 pipeline over Kafka (planner.py, writer.py, reviewer.py must be running)
# direct = same plan/write/review functions in this process - DEBUG / SMOKE TEST ONLY
PIPELINE_MODE = os.getenv("HW10_PIPELINE", "kafka")
PIPELINE_TIMEOUT_S = float(os.getenv("HW10_PIPELINE_TIMEOUT", "300"))

# ---------------- judge (GEval / DeepEval, local model) ----------------
JUDGE_BACKEND = os.getenv("HW10_JUDGE", "ollama")  # "mock" = offline smoke test only
JUDGE_MODEL = os.getenv("HW10_JUDGE_MODEL", "qwen3:4b")
JUDGE_URL = os.getenv("HW10_JUDGE_URL", "http://localhost:11434/api/chat")
JUDGE_TEMPERATURE = 0
JUDGE_SEED = SEED
JUDGE_CALL_TIMEOUT_S = float(os.getenv("HW10_JUDGE_TIMEOUT", "180"))  # one HTTP call to Ollama
JUDGE_HARD_TIMEOUT_S = float(os.getenv("HW10_JUDGE_HARD_TIMEOUT", "240"))  # one GEval measure()
JUDGE_MAX_CONSECUTIVE_FAILURES = 3  # then the judge is treated as unavailable for the run
JUDGE_MAX_CHARS = 6000  # longer inputs are truncated before judging
EVAL_COLLECT_TIMEOUT_S = float(os.getenv("HW10_EVAL_COLLECT_TIMEOUT", "30"))  # Kafka read bound

# 1-5 scale used for the judge AND the human labels
SCALE = {1: "very poor", 2: "poor", 3: "acceptable", 4: "good", 5: "excellent"}

# ---------------- Part 4.3 ----------------
LATENCY_RUNS = 50

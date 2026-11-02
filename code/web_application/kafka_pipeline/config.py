"""HW8 personal configuration and topic names (Section 0).

SID4 = 2837 -> PORT_BASE = 8000 + (2837 mod 900) = 8137, PREFIX = s2837,
SEED = 2837, VERIFY_SEED = 262837, DOMAIN_ID = 2837 mod 8 = 5 (restaurant inspections).
"""

import os
from pathlib import Path

STUDENT_NAME = "Shashank Ranjan"
SID4 = 2837
PORT_BASE = 8000 + (SID4 % 900)  # 8137
PREFIX = f"s{SID4}"  # s2837
SEED = SID4
VERIFY_SEED = 260000 + SID4  # 262837
DOMAIN_ID = SID4 % 8  # 5
DOMAIN = "Local restaurant inspections"
ENTITY = "inspection"  # primary domain entity

# Inside docker-compose the services talk to kafka:29092; from the host use localhost:9092.
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

# ---------------- Part 1: request/response service (exactly two topics) ----------------
REQUEST_TOPIC = f"{PREFIX}_{ENTITY}_requests"  # s2837_inspection_requests
RESPONSE_TOPIC = f"{PREFIX}_{ENTITY}_responses"  # s2837_inspection_responses
OP_CREATE = "CREATE_INSPECTION"
OP_GET = "GET_INSPECTION"
ID_FIELD = "inspection_id"
WORKER_GROUP = f"{PREFIX}_inspection_workers"

# ---------------- Part 2/3: agent pipeline ----------------
INBOX_TOPIC = f"{PREFIX}_inbox"
TASKS_TOPIC = f"{PREFIX}_tasks"  # 2 partitions
DRAFTS_TOPIC = f"{PREFIX}_drafts"
FINAL_TOPIC = f"{PREFIX}_final"
DEAD_LETTER_TOPIC = f"{PREFIX}_dead_letter"

PLANNER_GROUP = f"{PREFIX}_planners"
WRITER_GROUP = f"{PREFIX}_writers"
REVIEWER_GROUP = f"{PREFIX}_reviewers"

# topic -> partitions
TOPICS = {
    REQUEST_TOPIC: 1,
    RESPONSE_TOPIC: 1,
    INBOX_TOPIC: 1,
    TASKS_TOPIC: 2,
    DRAFTS_TOPIC: 1,
    FINAL_TOPIC: 1,
    DEAD_LETTER_TOPIC: 1,
}

MAX_RETRIES = int(os.getenv("HW8_MAX_RETRIES", "3"))

# ---------------- paths ----------------
# .../code/web_application/kafka_pipeline/config.py -> parents[3] is the repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = Path(os.getenv("HW8_REPORT_DIR", REPO_ROOT / "reports" / "hw08"))
RAW_DIR = REPORT_DIR / "raw"
RUN_LOG = REPORT_DIR / "RUN_LOG.txt"
TRACE_FILE = RAW_DIR / "trace_events.jsonl"
STATE_DIR = Path(os.getenv("HW8_STATE_DIR", Path(__file__).resolve().parent / "state"))

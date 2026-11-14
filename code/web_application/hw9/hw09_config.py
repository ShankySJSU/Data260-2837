"""HW9 configuration (Section 0 values are the same as HW8).

Every Redis key starts with PREFIX (s2837).
"""

import os
from pathlib import Path

STUDENT_NAME = "Shashank Ranjan"
SID4 = 2837
PREFIX = f"s{SID4}"  # s2837
PORT_BASE = 8000 + (SID4 % 900)  # 8137
SEED = SID4
VERIFY_SEED = 260000 + SID4  # 262837
ENTITY = "inspection"

# ---------------- Redis ----------------
# docker compose starts redis-stack-server as s2837-redis on localhost:6379 (RediSearch included)
REDIS_HOST = os.getenv("HW9_REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("HW9_REDIS_PORT", "6379"))

# Part 1 keys
VIEWS_KEY = PREFIX + ":views:" + ENTITY + ":{id}"  # s2837:views:inspection:<id>
SYNC_EVERY = 10

# Part 2/3 keys
CACHE_ENTRY_PREFIX = f"{PREFIX}:semcache:entry:"  # one HASH per cached query
CACHE_INDEX = f"{PREFIX}:semcache:idx"  # RediSearch vector index over those hashes
CACHE_STATS_KEY = f"{PREFIX}:semcache:stats"
DATA_VERSION_KEY = PREFIX + ":dv:" + ENTITY + ":{code}"  # data-version marker per record
CACHE_TTL_SECONDS = int(os.getenv("HW9_CACHE_TTL", str(24 * 3600)))
DEFAULT_THRESHOLD = 0.85
SWEEP_THRESHOLDS = [0.75, 0.80, 0.85, 0.90, 0.95]

# Embeddings (same model as HW4 RAG)
EMBED_MODEL = os.getenv("HW9_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_DIM = 384

# Miss path: "kafka" = full HW8 pipeline (planner.py, writer.py, reviewer.py must be running)
#            "direct" = the same HW8 plan/write/review functions called in-process (no Kafka)
AGENT_MODE = os.getenv("HW9_AGENT_MODE", "kafka")

# ---------------- MySQL s2837_rel (same database as HW4-HW7) ----------------
DB_HOST = os.getenv("HW9_DB_HOST", "localhost")
DB_PORT = int(os.getenv("HW9_DB_PORT", "3306"))
DB_USER = os.getenv("HW9_DB_USER", "root")
DB_PASSWORD = os.getenv("HW9_DB_PASSWORD", "sjsu2026")
DB_NAME = os.getenv("HW9_DB_NAME", f"{PREFIX}_rel")  # s2837_rel
# Only for offline smoke tests: HW9_SQLITE=path makes db.py use SQLite instead of MySQL
SQLITE_PATH = os.getenv("HW9_SQLITE")

# ---------------- paths ----------------
HW9_DIR = Path(__file__).resolve().parent
REPO_ROOT = HW9_DIR.parents[1]
REPORT_DIR = Path(os.getenv("HW9_REPORT_DIR", REPO_ROOT / "reports" / "hw09"))
RAW_DIR = REPORT_DIR / "raw"
RUN_LOG = REPORT_DIR / "RUN_LOG.txt"
CACHE_CASES = HW9_DIR / "cache_cases.yaml"
AGENT_DATA_DIR = HW9_DIR / "agent" / "data"
REFERENCE_FILE = AGENT_DATA_DIR / "reference_data.json"
LESSONS_FILE = Path(os.getenv("HW9_LESSONS_FILE", AGENT_DATA_DIR / "lessons.json"))

# County policy text that the HW8 writer gets with every cache-miss question
POLICY_TEXT = ("County policy: score 85-100 = PASS (no re-inspection); 70-84 = WARNING "
               "(re-inspection within 30 days of the inspection date); 0-69 = FAIL "
               "(re-inspection within 10 days).")

"""HW6 smoke test; run while the local backend is running."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = os.getenv("HW6_BASE_URL", "http://localhost:8137")
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "hw06"
OUTPUT = REPORT_DIR / "verification.json"

SID4 = 2837
SEED = SID4
VERIFY_SEED = 260000 + SID4

checks = []


def check(name, fn):
    try:
        passed = bool(fn())
        checks.append({"check": name, "status": "PASS" if passed else "FAIL"})
        return passed
    except Exception as exc:
        checks.append({"check": name, "status": "FAIL", "error": str(exc)})
        return False


def main():
    check("backend_running", lambda: requests.get(f"{BASE_URL}/", timeout=5).status_code == 200)
    check(
        "mongodb_schema_endpoint",
        lambda: requests.get(f"{BASE_URL}/api/documents/schema/status", timeout=5).status_code == 200,
    )
    check(
        "mongodb_document_list",
        lambda: isinstance(requests.get(f"{BASE_URL}/api/documents", timeout=5).json(), list),
    )
    check(
        "memory_aggregate_endpoint",
        lambda: requests.get(f"{BASE_URL}/api/aggregate/smoke-user", timeout=5).status_code == 200,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "homework": "HW6",
                "sid4": SID4,
                "commit_hash": os.getenv("HW6_COMMIT_HASH", "run-before-tagging"),
                "model": os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"),
                "seed": SEED,
                "verify_seed": VERIFY_SEED,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

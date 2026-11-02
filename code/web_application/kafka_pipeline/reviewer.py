"""HW8 Part 2 - Reviewer agent.   s2837_drafts -> s2837_final

    python reviewer.py

Objective, rule-based review (no second model call): the draft must be non-empty, 40-400
words, on-domain (mentions inspection/restaurant) and must not contain error text.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.agent_base import AgentRunner, build_parser, require  # noqa: E402
from web_application.kafka_pipeline.kafka_io import log, now_iso  # noqa: E402


def review(draft):
    words = len(draft.split())
    checks = {
        "non_empty": bool(draft.strip()),
        "length_40_400_words": 40 <= words <= 400,
        "on_domain": bool(re.search(r"inspect|restaurant|food", draft, re.I)),
        "no_error_text": not re.search(r"traceback|exception|error:", draft, re.I),
    }
    return all(checks.values()), checks, words


def handle(message, record, runner):
    if message.get("kind") != "answer_draft":
        log(runner.component, f"IGNORED kind={message.get('kind')} (not an answer draft)")
        return []
    draft = require(message, "draft")
    approved, checks, words = review(draft)
    final = {
        "correlation_id": message["correlation_id"],
        "test_run": message.get("test_run"),
        "status": "approved" if approved else "rejected",
        "answer": draft,
        "question": message.get("question"),
        "review": {"checks": checks, "word_count": words, "reviewer": runner.args.instance,
                   "reviewed_at": now_iso()},
        "plan_steps": (message.get("plan") or {}).get("steps"),
        "writer": message.get("writer"),
    }
    log(runner.component, f"REVIEW status={final['status']} checks={checks}")
    return [(cfg.FINAL_TOPIC, final, message["correlation_id"])]


if __name__ == "__main__":
    args = build_parser("reviewer-1", cfg.REVIEWER_GROUP).parse_args()
    AgentRunner("reviewer", cfg.DRAFTS_TOPIC, handle, args).start()

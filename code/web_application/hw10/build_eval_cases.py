"""HW10 Part 3.1 - freeze 20 Writer drafts from my domain system.

    cd code
    python -m web_application.hw10.build_eval_cases

Sends 20 restaurant-inspection questions through the real pipeline (cache bypassed), reads
each Writer draft back from s2837_drafts by correlation_id and writes

    reports/hw10/eval_cases.json     20 drafts (+ question, facts, plan, trace_id)
    reports/hw10/human_labels.csv    case_id,human_label,note   <- labels EMPTY

No judge is involved. Next steps (in this order):
    1. label every draft by hand:  python -m web_application.hw10.label_cases
    2. git add reports/hw10/eval_cases.json reports/hw10/human_labels.csv && git commit
    3. only then:                  python -m web_application.hw10.run_part3
The file is frozen: an existing eval_cases.json is never overwritten (use --force only
before any label exists).
"""

import argparse
import csv
import json
import sys

from . import config as cfg
from . import tracing
from .common import banner, log
from .pipeline import make_source
from .traced_qa import TracedQAService

COMPONENT = "CASES"

# 20 domain questions of mixed difficulty: direct look-ups, date arithmetic, policy
# boundaries, comparisons, advice, and questions the database facts cannot answer.
QUESTIONS = [
    "What score and status did Taj Grill get in its latest inspection?",
    "By what date must Taj Grill be re-inspected?",
    "What violations were found at Golden Dragon Bistro?",
    "Golden Dragon Bistro failed its inspection. What should the owner fix first, and why?",
    "Does Bayside Sushi Bar need a re-inspection?",
    "When is the re-inspection deadline for Spicy Pho House?",
    "Which violations at Spicy Pho House are the most serious food-safety risks?",
    "Is Golden Crust Bakery's score of 83 a PASS?",
    "How many more points would Rustic Garden Deli need to reach a PASS?",
    "What did the inspector find at Urban Taco Cafe, and is any follow-up required?",
    "Which scored higher in the latest inspection, Cafe Milano or Rangoli Indian Cuisine?",
    "Compare the inspection results of Taj Grill and Grill & Barrel Bar.",
    "What must Grill & Barrel Bar do before its re-inspection?",
    "How many days does a restaurant with a FAIL status have before re-inspection?",
    "What score range counts as a WARNING, and what happens after a WARNING?",
    "Is a score of 85 a PASS or a WARNING?",
    "What was the latest inspection result for Blue Lotus Cafe?",
    "Why is cooling cooked rice improperly a health hazard?",
    "Is it safe to eat at Rustic Garden Deli given its latest inspection?",
    "Summarize the latest inspection of Rangoli Indian Cuisine for a customer.",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline", default=cfg.PIPELINE_MODE, choices=["kafka", "direct"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    labels_exist = False
    if cfg.HUMAN_LABELS.exists():
        with open(cfg.HUMAN_LABELS, newline="", encoding="utf-8") as handle:
            labels_exist = any((row.get("human_label") or "").strip()
                               for row in csv.DictReader(handle))
    if cfg.EVAL_CASES.exists() and (not args.force or labels_exist):
        log(COMPONENT, f"{cfg.EVAL_CASES} already exists and is frozen"
                       f"{' (labels already assigned)' if labels_exist else ''} - nothing done")
        return 1
    if cfg.JUDGE_SCORES.exists():
        log(COMPONENT, "judge scores already exist - the cases cannot be rebuilt")
        return 1

    svc = TracedQAService(pipeline_mode=args.pipeline)
    source = make_source(args.pipeline)
    banner(COMPONENT, f"HW10 Part 3.1 - {cfg.STUDENT_NAME} - collecting {len(QUESTIONS)} "
                      f"Writer drafts ({svc.mode})")
    cases = []
    for n, question in enumerate(QUESTIONS, 1):
        case_id = f"C{n:02d}"
        res = svc.handle(question, bypass_cache=True)
        if res["status"] != "ok":
            log(COMPONENT, f"{case_id} request FAILED at {res['failed_stage']}: {res['error']}")
            return 1
        found, _stats = source.fetch([res["trace_id"]], start_offsets=res.get("start_offsets"))
        draft_rec = found[res["trace_id"]].get("draft")
        if not draft_rec or not isinstance(draft_rec["value"].get("draft"), str):
            log(COMPONENT, f"{case_id} no Writer draft found for trace_id={res['trace_id']}")
            return 1
        value = draft_rec["value"]
        cases.append({
            "case_id": case_id,
            "trace_id": res["trace_id"],
            "question": question,
            "judge_input": value.get("question"),  # question + s2837_rel facts + county policy
            "plan_steps": (value.get("plan") or {}).get("steps"),
            "draft": value["draft"],
            "writer": value.get("writer"),
            "source": {k: draft_rec.get(k) for k in ("topic", "partition", "offset",
                                                     "timestamp_ms")},
        })
        log(COMPONENT, f"{case_id} trace_id={res['trace_id']} draft "
                       f"{len(value['draft'].split())} words")
    svc.close()

    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"description": "HW10 Part 3.1 - 20 frozen Writer drafts (s2837 restaurant "
                              "inspections). Do not edit after labeling.",
               "created_at": tracing.iso(__import__("time").time()),
               "pipeline_mode": svc.mode, "prefix": cfg.PREFIX, "cases": cases}
    cfg.EVAL_CASES.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with open(cfg.HUMAN_LABELS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "human_label", "note"])
        for case in cases:
            writer.writerow([case["case_id"], "", ""])
    log(COMPONENT, f"wrote {cfg.EVAL_CASES} and {cfg.HUMAN_LABELS} (labels empty)")
    log(COMPONENT, "NEXT: label by hand (label_cases), commit both files, THEN run_part3")
    return 0


if __name__ == "__main__":
    sys.exit(main())

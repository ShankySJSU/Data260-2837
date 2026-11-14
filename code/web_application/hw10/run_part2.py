"""HW10 Part 2 - send end-to-end test questions through the pipeline and evaluate them.

    cd code
    python -m web_application.hw10.run_part2                 # 3 default questions
    python -m web_application.hw10.run_part2 --question "..."   (repeatable)

Start planner.py, writer.py and reviewer.py first (HW8) plus Redis, MySQL and Ollama.
Each question skips the semantic cache (bypass) so the agents really run, then the evaluator
loads plan / draft / final from Kafka by correlation_id. Results: raw/eval_results.json.
"""

import argparse
import sys

from . import config as cfg
from .common import banner, log
from .evaluator import Evaluator, save_evaluation
from .traced_qa import TracedQAService

COMPONENT = "PART2"

DEFAULT_QUESTIONS = [
    "Taj Grill received a WARNING. What exactly must the owner fix, and by what date is the "
    "re-inspection due?",
    "What violations were found at Golden Dragon Bistro, and what does its FAIL status mean "
    "for re-inspection?",
    "Did Cafe Milano pass its latest inspection, and does it need a re-inspection?",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", action="append")
    parser.add_argument("--pipeline", default=cfg.PIPELINE_MODE, choices=["kafka", "direct"])
    args = parser.parse_args()
    questions = args.question or DEFAULT_QUESTIONS

    svc = TracedQAService(pipeline_mode=args.pipeline)
    evaluator = Evaluator(pipeline_mode=args.pipeline)
    banner(COMPONENT, f"HW10 Part 2 - {cfg.STUDENT_NAME} - evaluator on the {cfg.PREFIX} "
                      f"Planner/Writer/Reviewer pipeline ({svc.mode})")
    ok, detail = evaluator.judge.health()
    log(COMPONENT, f"judge: {evaluator.judge.describe().get('model')} - "
                   f"{'OK' if ok else 'UNAVAILABLE'} - {detail}")
    if not ok:
        log(COMPONENT, "the judge is not reachable; start Ollama / install deepeval and rerun")
        return 1
    failures = 0
    for n, question in enumerate(questions, 1):
        log(COMPONENT, f"--- test question {n}: {question!r}")
        res = svc.handle(question, bypass_cache=True)
        if res["status"] != "ok":
            failures += 1
            log(COMPONENT, f"request FAILED at {res['failed_stage']}: {res['error']}")
            continue
        log(COMPONENT, f"trace_id={res['trace_id']} answered in {res['latency_ms']} ms; "
                       "evaluating ...")
        record = evaluator.evaluate(res["trace_id"], start_offsets=res.get("start_offsets"),
                                    batch="part2", query=question)
        save_evaluation(record)
        c = record["criteria"]
        print(f"\n  trace_id                  {record['trace_id']}")
        print(f"  Plan Quality              {c['plan_quality']['score']}  "
              f"{c['plan_quality']['reason'][:150]}")
        print(f"  Writer Helpfulness        {c['writer_helpfulness']['score']}  "
              f"{c['writer_helpfulness']['reason'][:150]}")
        print(f"  Final Answer Helpfulness  {c['final_helpfulness']['score']}  "
              f"{c['final_helpfulness']['reason'][:150]}")
        print(f"  Final vs Draft            draft {c['improvement']['draft_score']} -> final "
              f"{c['improvement']['final_score']} (difference "
              f"{c['improvement']['difference']})")
        print(f"  {c['improvement']['interpretation']}\n")
        if record["status"] == "error":
            failures += 1
    log(COMPONENT, f"saved {cfg.RAW_DIR / cfg.EVAL_RESULTS}")
    svc.close()
    evaluator.close()
    return 1 if failures == len(questions) else 0


if __name__ == "__main__":
    sys.exit(main())

"""HW10 Part 2 - evaluator for the s2837 Planner -> Writer -> Reviewer Kafka pipeline.

For one trace_id (= HW8 correlation_id) the evaluator
  1. loads the Planner plan (s2837_tasks), the Writer draft (s2837_drafts) and the Reviewer
     final answer (s2837_final) and joins them on correlation_id,
  2. keeps the original messages + topic/partition/offset so the run can be reproduced,
  3. scores four criteria with the local GEval judge on the 1-5 scale:
        Plan Quality                 plan steps          -> score + brief reason
        Writer Helpfulness           draft               -> score + trace_id
        Final Answer Helpfulness     final answer        -> score + final answer
        Final-vs-Draft Improvement   draft and final scored with the SAME Final Answer
                                     Helpfulness metric  -> both scores, difference, reading
  4. writes an "evaluation" span for the trace.

Bounded: the Kafka read stops at the end offsets or after EVAL_COLLECT_TIMEOUT_S; a missing
or malformed message gives status "missing_input" for the criteria that need it; judge calls
are bounded in judge.py. Nothing here can wait forever.

    cd code
    python -m web_application.hw10.evaluator --trace-id <correlation_id>
"""

import argparse
import sys
import time

from . import config as cfg
from . import tracing
from .common import load_raw, log, save_raw
from .judge import Judge
from .pipeline import make_source

COMPONENT = "EVALUATOR"


def plan_text(steps):
    return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))


def extract(messages):
    """Pull question / plan / draft / final out of the joined messages, validating shapes."""
    problems = []
    plan_msg = (messages.get("plan") or {}).get("value") or {}
    draft_msg = (messages.get("draft") or {}).get("value") or {}
    final_msg = (messages.get("final") or {}).get("value") or {}
    for role in ("plan", "draft", "final"):
        if role not in messages:
            problems.append(f"{role} message not found for this correlation_id")
    question = next((m.get("question") for m in (plan_msg, draft_msg, final_msg)
                     if isinstance(m.get("question"), str) and m.get("question").strip()), None)
    if question is None:
        problems.append("no question text in any message")
    plan = plan_msg.get("plan") if isinstance(plan_msg.get("plan"), dict) else {}
    steps = plan.get("steps")
    if not (isinstance(steps, list) and steps and all(isinstance(s, str) for s in steps)):
        if "plan" in messages:
            problems.append("plan.steps is not a non-empty list of strings (malformed)")
        steps = None
    draft = draft_msg.get("draft")
    if not (isinstance(draft, str) and draft.strip()):
        if "draft" in messages:
            problems.append("draft text missing or not a string (malformed)")
        draft = None
    answer = final_msg.get("answer")
    if not (isinstance(answer, str) and answer.strip()):
        if "final" in messages:
            problems.append("final answer missing or not a string (malformed)")
        answer = None
    return {"question": question, "steps": steps, "draft": draft, "final": answer,
            "final_status": final_msg.get("status"),
            "review_checks": (final_msg.get("review") or {}).get("checks"),
            "writer_model": (draft_msg.get("writer") or {}).get("model"),
            "planner_model": plan.get("model"), "problems": problems}


def read_improvement(draft_score, final_score, identical):
    """Plain-language reading of the draft -> final comparison (no forced positive result)."""
    if draft_score is None or final_score is None:
        return "Not available: at least one of the two scores could not be produced."
    diff = final_score - draft_score
    if identical:
        base = ("The final answer is byte-identical to the Writer draft: the HW8 Reviewer is a "
                "rule-based gate (length, on-domain, no error text) that approves or rejects a "
                "draft but never rewrites it, so it cannot improve the text.")
        if diff == 0:
            return base + " Both texts received the same score, so there is no improvement."
        return (base + f" The scores still differ by {diff:+d}; because the text is the same, "
                "that difference is judge noise, not a real quality change.")
    if diff > 0:
        return f"The final answer scored {diff:+d} above the draft: the review step improved it."
    if diff < 0:
        return f"The final answer scored {diff:+d} below the draft: the review step made it worse."
    return "The final answer differs from the draft but received the same score: no improvement."


class Evaluator:
    def __init__(self, judge=None, source=None, pipeline_mode=None):
        self.judge = judge or Judge()
        self.source = source or make_source(pipeline_mode)

    def evaluate(self, trace_id, start_offsets=None, batch="part2", query=None):
        """Evaluate one trace. Always returns a record; never raises for bad data."""
        started = time.time()
        record = {"trace_id": trace_id, "correlation_id": trace_id, "batch": batch,
                  "query": query, "evaluated_at": tracing.iso(started), "status": "ok",
                  "errors": [], "judge": self.judge.describe()}
        try:
            found, stats = self.source.fetch([trace_id], start_offsets=start_offsets)
        except Exception as exc:  # noqa: BLE001 - broker down, topic missing, ...
            found, stats = {trace_id: {}}, {"source": self.source.name,
                                            "error": f"{type(exc).__name__}: {exc}"}
            record["errors"].append(f"could not load messages: {type(exc).__name__}: {exc}")
        messages = found.get(trace_id, {})
        record["collection"] = stats
        record["inputs"] = messages  # original messages + topic/partition/offset
        data = extract(messages)
        record["errors"].extend(data["problems"])
        record.update(question=data["question"], final_status=data["final_status"],
                      review_checks=data["review_checks"], writer_model=data["writer_model"],
                      planner_model=data["planner_model"])
        question = data["question"]

        def judge(criterion, text):
            if question is None or text is None:
                return {"criterion": criterion, "score": None, "geval_score": None,
                        "reason": "", "status": "missing_input",
                        "error": "required message missing or malformed", "ms": 0.0}
            return self.judge.score(criterion, question, text)

        plan = judge("plan_quality", plan_text(data["steps"]) if data["steps"] else None)
        writer = judge("writer_helpfulness", data["draft"])
        final = judge("final_helpfulness", data["final"])
        draft_same_metric = judge("final_helpfulness", data["draft"])  # baseline for 2.2 (4)
        identical = (data["draft"] is not None and data["draft"] == data["final"])
        d_score, f_score = draft_same_metric["score"], final["score"]
        record["criteria"] = {
            "plan_quality": {**plan, "plan_steps": data["steps"]},
            "writer_helpfulness": {**writer, "trace_id": trace_id, "draft": data["draft"]},
            "final_helpfulness": {**final, "final_answer": data["final"]},
            "improvement": {
                "metric": "Final Answer Helpfulness applied to both texts",
                "draft_score": d_score, "final_score": f_score,
                "difference": (f_score - d_score) if None not in (d_score, f_score) else None,
                "draft_reason": draft_same_metric["reason"], "final_reason": final["reason"],
                "draft_status": draft_same_metric["status"],
                "texts_identical": identical,
                "interpretation": read_improvement(d_score, f_score, identical),
            },
        }
        statuses = [plan["status"], writer["status"], final["status"],
                    draft_same_metric["status"]]
        if all(s != "ok" for s in statuses):
            record["status"] = "error"
        elif any(s != "ok" for s in statuses) or record["errors"]:
            record["status"] = "partial"
        ended = time.time()
        record["evaluation_ms"] = round((ended - started) * 1000, 1)
        tracing.write_span(
            trace_id, "evaluation", started, ended,
            "ok" if record["status"] != "error" else "error",
            None if record["status"] != "error" else "; ".join(
                record["errors"] or sorted({s for s in statuses if s != "ok"})),
            batch=batch, judge=record["judge"].get("model"),
            plan_quality=plan["score"], writer_helpfulness=writer["score"],
            final_helpfulness=final["score"], eval_status=record["status"],
            judge_calls_ms=round(sum(x["ms"] for x in (plan, writer, final,
                                                       draft_same_metric)), 1))
        log(COMPONENT, f"trace_id={trace_id} status={record['status']} plan={plan['score']} "
                       f"writer={writer['score']} final={final['score']} "
                       f"draft(same metric)={d_score} diff="
                       f"{record['criteria']['improvement']['difference']} "
                       f"in {record['evaluation_ms']} ms")
        return record

    def close(self):
        self.judge.close()


def save_evaluation(record):
    """Upsert into raw/eval_results.json (one record per trace_id)."""
    data = load_raw(cfg.EVAL_RESULTS, {"records": []})
    if isinstance(record.get("judge"), dict):  # full settings once, model name per record
        data["judge"] = record["judge"]
        record = {**record, "judge": record["judge"].get("model")}
    data["records"] = [r for r in data["records"] if r["trace_id"] != record["trace_id"]]
    data["records"].append(record)
    return save_raw(cfg.EVAL_RESULTS, data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", required=True, help="the correlation_id of a request")
    parser.add_argument("--pipeline", default=cfg.PIPELINE_MODE, choices=["kafka", "direct"])
    parser.add_argument("--batch", default="manual")
    args = parser.parse_args()
    evaluator = Evaluator(pipeline_mode=args.pipeline)
    ok, detail = evaluator.judge.health()
    log(COMPONENT, f"judge health: {'OK' if ok else 'UNAVAILABLE'} - {detail}")
    record = evaluator.evaluate(args.trace_id, batch=args.batch)
    path = save_evaluation(record)
    log(COMPONENT, f"saved {path}")
    evaluator.close()
    return 0 if record["status"] != "error" else 1


if __name__ == "__main__":
    sys.exit(main())

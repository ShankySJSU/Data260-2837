"""HW7 Part 3: bounded Reflexion on top of the Part 2 agent loop.

After each attempt a deterministic verifier checks the result. If it fails, one short
reflection (failure + better strategy + evidence) is stored and the task is retried with it
in context as untrusted data. Bounds: at most 2 retries, a tool-call budget and a token
budget. Stop reasons: success, budget_exhausted, human_review.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from web_application.agent.agent_loop import run_agent
from web_application.agent.verifier import verify_task

MAX_REFLEXION_RETRIES = 2
MAX_TOOL_CALLS = 20
MAX_TOKENS = 12000
MAX_REFLECTION_CHARS = 400

STRATEGY = {
    "A": "call search first, then call detail_lookup with the id of the FIRST search result.",
    "B": "call aggregate for the FAIL count, then search for a FAIL inspection and cite both.",
    "C": "call search with limit 2, then detail_lookup for each of the two ids, then compare.",
}


def _short(value, limit=200):
    text = json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def make_reflection(task_id, result, verdict):
    """Short failure explanation + revised strategy, with the evidence that triggered it.

    Built from the verifier result and tool log only: no hidden chain-of-thought is stored.
    """
    last = result["tool_log"][-1] if result["tool_log"] else None
    evidence = {
        "verifier_reason": verdict["reason"],
        "verifier_evidence": verdict["evidence"],
        "last_tool_call": {"tool": last["tool"], "inputs": last["inputs"]} if last else None,
        "last_observation": _short(last["data"] if last and last["ok"] else
                                   (last or {}).get("error")),
        "stop_reason": result["stop_reason"],
    }
    text = f"The last attempt failed: {verdict['reason']}. Better strategy: {STRATEGY[task_id]}"
    return {"reflection": text[:MAX_REFLECTION_CHARS], "evidence": evidence}


def append_reflection(store_path, record):
    Path(store_path).parent.mkdir(parents=True, exist_ok=True)
    with open(store_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def load_reflections(store_path, user_id, run_id):
    """Reflections are isolated to one user and one run."""
    path = Path(store_path)
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [r for r in rows if r["user_id"] == user_id and r["run_id"] == run_id]


def run_with_reflexion(task_id, task, model_factory, executor, *, user_id, run_id, seed,
                       store_path, echo=True):
    """Run a fixed task with up to MAX_REFLEXION_RETRIES reflexion retries."""
    attempts, totals = [], {"tool_calls": 0, "tokens": 0, "latency_ms": 0.0}
    stop_reason = "human_review"

    for attempt in range(MAX_REFLEXION_RETRIES + 1):
        stored = load_reflections(store_path, user_id, run_id)
        note = stored[-1]["reflection"] if stored else None  # data only; never instructions
        result = run_agent(
            task["prompt"],
            model=model_factory(seed + 1000 * attempt),
            tool_executor=executor,
            required_tools=task["required_tools"],
            max_tool_calls=MAX_TOOL_CALLS - totals["tool_calls"],
            max_tokens=MAX_TOKENS - totals["tokens"],
            reflection=note,
            echo=echo,
        )
        verdict = verify_task(task_id, result, task["prompt"])
        attempts.append({"result": result, "verdict": verdict})
        totals["tool_calls"] += result["tool_calls"]
        totals["tokens"] += result["prompt_tokens"] + result["completion_tokens"]
        totals["latency_ms"] += result["latency_ms"]

        if verdict["passed"]:
            stop_reason = "success"
            break
        out_of_budget = (result["stop_reason"] == "budget_exhausted"
                         or totals["tool_calls"] >= MAX_TOOL_CALLS
                         or totals["tokens"] >= MAX_TOKENS)
        if out_of_budget:
            stop_reason = "budget_exhausted"
            break
        if attempt == MAX_REFLEXION_RETRIES or result["stop_reason"] in (
                "repair_exhausted", "model_error"):
            stop_reason = "human_review"
            break

        reflection = make_reflection(task_id, result, verdict)
        append_reflection(store_path, {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_id": user_id, "run_id": run_id, "task": task_id, "attempt": attempt + 1,
            **reflection,
        })

    return {"attempts": attempts, "stop_reason": stop_reason, "passed": stop_reason == "success",
            **totals}

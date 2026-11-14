"""HW7 Part 3 runner: original loop vs Reflexion loop on the same three fixed tasks.

The first Reflexion attempt IS the original-loop run (same task, model and seed), so the
two columns compare identical starting points. Run from the code folder:
    python -m web_application.run_hw07_part3
Writes raw/reflexion_raw.csv and raw/reflexion_reflections.jsonl; appends to RUN_LOG.txt.
"""

import sys

from web_application.agent.reflexion import run_with_reflexion
from web_application.run_hw07_part2 import (
    RAW_DIR,
    RUN_LOG,
    SID4,
    TASKS,
    Tee,
    default_executor,
    default_model_factory,
    required_ok,
    stamp,
    write_csv,
)

REPEATS = 3  # runs per task -> 9 runs per loop


def tokens(result):
    return result["prompt_tokens"] + result["completion_tokens"]


def run_all(model_factory=default_model_factory, executor=None, repeats=REPEATS, store=None):
    executor = executor or default_executor()
    store = store or RAW_DIR / "reflexion_reflections.jsonl"
    rows = []
    for repeat in range(repeats):
        for index, task_id in enumerate("ABC"):
            seed = SID4 + repeat * 3 + index
            run_id = f"hw7-{task_id}-{seed}"
            stamp(f"=== Reflexion run {run_id}")
            run = run_with_reflexion(task_id, TASKS[task_id], model_factory, executor,
                                     user_id="shashank-2837", run_id=run_id, seed=seed,
                                     store_path=store)
            first, last = run["attempts"][0], run["attempts"][-1]
            orig, final = first["result"], last["result"]
            # Candidate false rejection: the tool use was correct and every number is
            # supported, but the verifier rejected the wording of the answer. Review by hand.
            candidate = [i + 1 for i, a in enumerate(run["attempts"])
                         if not a["verdict"]["passed"]
                         and a["verdict"]["evidence"].get("answer_text_check")
                         and required_ok(TASKS[task_id], a["result"])
                         and not a["verdict"]["unsupported_numbers"]]
            rows.append({
                "run_id": run_id, "task": task_id, "seed": seed,
                "orig_pass": first["verdict"]["passed"],
                "orig_unsupported": len(first["verdict"]["unsupported_numbers"]),
                "orig_tool_calls": orig["tool_calls"], "orig_tokens": tokens(orig),
                "orig_latency_ms": orig["latency_ms"],
                "reflex_pass": run["passed"], "reflex_stop_reason": run["stop_reason"],
                "reflex_attempts": len(run["attempts"]), "reflex_retries": len(run["attempts"]) - 1,
                "reflex_unsupported": len(last["verdict"]["unsupported_numbers"]),
                "reflex_tool_calls": run["tool_calls"], "reflex_tokens": run["tokens"],
                "reflex_latency_ms": round(run["latency_ms"], 1),
                "candidate_false_rejection_attempts": ";".join(map(str, candidate)),
                "orig_verifier_reason": first["verdict"]["reason"],
                "final_answer": (final["answer"] or "")[:300],
            })
            stamp(f"{run_id}: orig_pass={rows[-1]['orig_pass']} reflex={run['stop_reason']} "
                  f"attempts={len(run['attempts'])}")
    write_csv(rows, RAW_DIR / "reflexion_raw.csv")
    stamp("Saved reports/hw07/raw/reflexion_raw.csv")
    print("\n" + summarize(rows))
    return rows


def summarize(rows):
    n = len(rows)

    def mean(key):
        return sum(r[key] for r in rows) / n

    def count(key):
        return sum(1 for r in rows if r[key])

    false_rej = sum(1 for r in rows if r["candidate_false_rejection_attempts"])
    return "\n".join([
        "| Metric | Original loop | Reflexion loop |",
        "| --- | --- | --- |",
        f"| Task success | {count('orig_pass')}/{n} | {count('reflex_pass')}/{n} |",
        f"| Unsupported claims (runs with any) | {count('orig_unsupported')} "
        f"| {count('reflex_unsupported')} |",
        f"| Retry rate | N/A | {count('reflex_retries')}/{n} runs retried |",
        f"| Tool calls (mean) | {mean('orig_tool_calls'):.1f} | {mean('reflex_tool_calls'):.1f} |",
        f"| Tokens (mean) | {mean('orig_tokens'):.0f} | {mean('reflex_tokens'):.0f} |",
        f"| Latency ms (mean) | {mean('orig_latency_ms'):.0f} | {mean('reflex_latency_ms'):.0f} |",
        f"| Verifier false rejections (candidates, confirm by hand) | N/A | {false_rej} |",
    ])


if __name__ == "__main__":
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(sys.__stdout__, RUN_LOG)
    stamp(f"HW7 Part 3 run: SID4={SID4}, {REPEATS} runs per task")
    run_all()

"""HW7 Part 2 runner: three fixed tasks, error recovery, and the 20-attempt reliability run.

Run from the code folder (PYTHONPATH must include the repo root):
    python -m web_application.run_hw07_part2 demo
    python -m web_application.run_hw07_part2 reliability
Console output (with timestamps) is appended to reports/hw07/RUN_LOG.txt.
"""

import csv
import sys
from collections import Counter
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "hw07"
RAW_DIR = REPORT_DIR / "raw"
RUN_LOG = REPORT_DIR / "RUN_LOG.txt"

SID4 = 2837
RELIABILITY_TEMPERATURE = 0.7  # same for every attempt; only the seed changes per attempt

# The three fixed verification tasks (saved as fixed cases).
TASKS = {
    "A": {
        "prompt": "Search for inspections matching 'Rangoli', then look up the details "
                  "of the first result.",
        "required_tools": ("search", "detail_lookup"),
        "min_calls": {"search": 1, "detail_lookup": 1},
    },
    "B": {
        "prompt": "How many inspections have status FAIL? Then find one example "
                  "inspection with status FAIL.",
        "required_tools": ("aggregate", "search"),
        "min_calls": {"aggregate": 1, "search": 1},
    },
    "C": {
        "prompt": "Search for inspections with status PASS (limit 2), then look up the "
                  "details of both results and compare their scores.",
        "required_tools": ("search", "detail_lookup"),
        "min_calls": {"search": 1, "detail_lookup": 2},
    },
}

ERROR_CASE = "Get the details of inspection 999999 and tell me what you find."


class Tee:
    """Write console output to the screen and to RUN_LOG.txt, with a timestamp per line."""

    def __init__(self, stream, path):
        self.stream, self.path, self.buffer = stream, path, ""

    def write(self, text):
        self.stream.write(text)
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def flush(self):
        self.stream.flush()


def stamp(message):
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {message}")


def required_ok(task, result):
    """The task needs its required tools and the minimum number of calls to each."""
    counts = Counter(entry["tool"] for entry in result["tool_log"] if entry["ok"])
    return all(counts[tool] >= n for tool, n in task["min_calls"].items())


def run_attempt(task_id, attempt, model_factory, executor):
    from web_application.agent.agent_loop import run_agent

    task = TASKS[task_id]
    seed = SID4 + attempt
    result = run_agent(
        task["prompt"],
        model=model_factory(seed),
        tool_executor=executor,
        required_tools=task["required_tools"],
        echo=True,
    )
    classes = [event["error_class"] for event in result["events"]]
    unrepaired = [event for event in result["events"] if not event["repaired"]]
    ok = result["stop_reason"] == "success" and required_ok(task, result)
    return {
        "attempt": attempt,
        "task": task_id,
        "seed": seed,
        "temperature": RELIABILITY_TEMPERATURE,
        "stop_reason": result["stop_reason"],
        "tool_calls": result["tool_calls"],
        "model_outputs": result["steps"],
        "invalid_outputs": len(classes),
        "error_classes": ";".join(classes),
        "repairs": result["repairs"],
        "failed_repairs": result["failed_repairs"],
        "well_formed_before_repair": len(classes) == 0,
        "well_formed_after_repair": ok and not unrepaired,
        "task_success": ok,
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "latency_ms": result["latency_ms"],
    }


def summarize(rows):
    total = len(rows)
    before = sum(r["well_formed_before_repair"] for r in rows)
    after = sum(r["well_formed_after_repair"] for r in rows)
    outputs = sum(r["model_outputs"] for r in rows)
    invalid = sum(r["invalid_outputs"] for r in rows)
    classes = Counter(c for r in rows for c in r["error_classes"].split(";") if c)
    lines = [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Total attempts | {total} |",
        f"| Well-formed before repair (attempt level) | {before}/{total} = {before / total:.0%} |",
        f"| Well-formed after repair (attempt level) | {after}/{total} = {after / total:.0%} |",
        f"| Model outputs / invalid outputs (call level) | {outputs} / {invalid} "
        f"({1 - invalid / outputs:.0%} well-formed on first try) |",
    ]
    for name in ("malformed_arguments", "unknown_tool", "text_instead_of_tool", "lost_chain"):
        lines.append(f"| Failures: {name} | {classes.get(name, 0)} |")
    success = sum(r["task_success"] for r in rows)
    lines.append(f"| Task success (after repair) | {success}/{total} |")
    return "\n".join(lines)


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def default_model_factory(seed):
    from web_application.agent import adapter

    return partial(adapter.chat, temperature=RELIABILITY_TEMPERATURE, seed=seed)


def default_executor():
    from web_application.mcp.execute_tool import execute_tool

    return execute_tool


def run_demo(model_factory=default_model_factory, executor=None):
    from web_application.agent.agent_loop import run_agent

    executor = executor or default_executor()
    for task_id in ("A", "B", "C"):
        stamp(f"=== Task {task_id}: {TASKS[task_id]['prompt']}")
        row = run_attempt(task_id, "ABC".index(task_id), model_factory, executor)
        stamp(f"Task {task_id}: success={row['task_success']} tool_calls={row['tool_calls']} "
              f"stop={row['stop_reason']}")
    stamp(f"=== Error recovery: {ERROR_CASE}")
    result = run_agent(ERROR_CASE, model=model_factory(SID4), tool_executor=executor, echo=True)
    stamp(f"Error recovery: stop={result['stop_reason']} tool_calls={result['tool_calls']}")
    stamp(f"Final answer: {result['answer']}")


def run_reliability(model_factory=default_model_factory, executor=None, attempts=20):
    executor = executor or default_executor()
    rows = []
    for attempt in range(attempts):
        task_id = "ABC"[attempt % 3]
        stamp(f"=== Reliability attempt {attempt + 1}/{attempts} (task {task_id})")
        rows.append(run_attempt(task_id, attempt, model_factory, executor))
    write_csv(rows, RAW_DIR / "tool_reliability_20.csv")
    stamp("Saved reports/hw07/raw/tool_reliability_20.csv")
    print("\n" + summarize(rows))
    return rows


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(sys.__stdout__, RUN_LOG)
    stamp(f"HW7 Part 2 run: mode={mode} SID4={SID4} temperature={RELIABILITY_TEMPERATURE}")
    {"demo": run_demo, "reliability": run_reliability}[mode]()

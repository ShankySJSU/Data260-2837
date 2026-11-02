"""HW8 Part 2 - Writer agent.   s2837_tasks (2 partitions) -> s2837_drafts

    python writer.py                        # normal
    python writer.py --instance writer-2    # second member of the same consumer group

Message kinds on s2837_tasks:
  answer_task     {question, plan.steps}         -> LLM draft
  ordering_event  {entity_id, seq, work_ms}      -> Part 3 ordering test (no LLM)
A task may carry "simulate_slow_seconds" so the Part 3 crash test can kill the Writer
while it is mid-processing.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

from web_application.kafka_pipeline import config as cfg, llm  # noqa: E402
from web_application.kafka_pipeline.agent_base import (  # noqa: E402
    AgentRunner, PermanentError, build_parser, require,
)
from web_application.kafka_pipeline.kafka_io import log, now_iso  # noqa: E402


def handle(message, record, runner):
    kind = message.get("kind", "answer_task")
    correlation_id = message["correlation_id"]

    if kind == "ordering_event":
        entity_id = require(message, "entity_id")
        seq = message.get("seq")
        if not isinstance(seq, int):
            raise PermanentError("ordering_event needs integer seq")
        time.sleep(max(0, int(message.get("work_ms", 0))) / 1000)
        log(runner.component, f"ORDER entity={entity_id} seq={seq} partition={record.partition}"
                              f" offset={record.offset}")
        draft = {"correlation_id": correlation_id, "test_run": message.get("test_run"),
                 "kind": "ordering_result",
                 "run": message.get("run"), "entity_id": entity_id, "seq": seq,
                 "event": message.get("event"), "global_index": message.get("global_index"),
                 "partition": record.partition, "offset": record.offset,
                 "writer": runner.args.instance, "processed_at": now_iso()}
        return [(cfg.DRAFTS_TOPIC, draft, entity_id)]

    if kind != "answer_task":
        raise PermanentError(f"unknown task kind '{kind}'")
    question = require(message, "question")
    plan = message.get("plan")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps or not all(isinstance(s, str) for s in steps):
        raise PermanentError("plan.steps must be a non-empty list of strings")

    slow = float(message.get("simulate_slow_seconds") or 0)
    if slow:
        log(runner.component, f"WORKING slowly for {slow:.0f}s on correlation_id="
                              f"{correlation_id} (offset not committed yet - kill me now)")
        time.sleep(slow)
    text, model = llm.write(question, steps, runner.component)
    log(runner.component, f"DRAFT ({model}) {len(text.split())} words")
    draft = {"correlation_id": correlation_id, "test_run": message.get("test_run"),
             "kind": "answer_draft", "question": question,
             "plan": plan, "draft": text,
             "writer": {"instance": runner.args.instance, "model": model,
                        "written_at": now_iso()}}
    return [(cfg.DRAFTS_TOPIC, draft, correlation_id)]


if __name__ == "__main__":
    args = build_parser("writer-1", cfg.WRITER_GROUP).parse_args()
    AgentRunner("writer", cfg.TASKS_TOPIC, handle, args).start()

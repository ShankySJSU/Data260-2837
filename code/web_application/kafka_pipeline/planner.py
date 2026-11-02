"""HW8 Part 2 - Planner agent.   s2837_inbox -> s2837_tasks

    python planner.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

from web_application.kafka_pipeline import config as cfg, llm  # noqa: E402
from web_application.kafka_pipeline.agent_base import AgentRunner, build_parser, require  # noqa: E402
from web_application.kafka_pipeline.kafka_io import log, now_iso  # noqa: E402


def handle(message, record, runner):
    question = require(message, "question")
    steps, model = llm.plan(question, runner.component)
    log(runner.component, f"PLAN ({model}) steps={steps}")
    task = {
        "correlation_id": message["correlation_id"],
        "test_run": message.get("test_run"),
        "kind": "answer_task",
        "question": question,
        "plan": {"steps": steps, "model": model, "planned_at": now_iso()},
    }
    # key = correlation_id -> every task of one question lands in the same tasks partition
    return [(cfg.TASKS_TOPIC, task, message["correlation_id"])]


if __name__ == "__main__":
    args = build_parser("planner-1", cfg.PLANNER_GROUP).parse_args()
    AgentRunner("planner", cfg.INBOX_TOPIC, handle, args).start()

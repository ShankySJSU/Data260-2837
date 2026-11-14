"""The cache-miss path: the HW8 agent pipeline (Planner -> Writer -> Reviewer, local Ollama
qwen2.5:1.5b through the HW1 adapter).

Before calling the agents the question is grounded with the s2837_rel rows it mentions, and
the inspection codes used become the answer's dependencies (data-version marker, Part 3.5).

Modes (HW9_AGENT_MODE or --agent):
    kafka   send_question.ask(): s2837_inbox -> planner.py -> writer.py -> reviewer.py -> s2837_final
            (start the three HW8 agents first)
    direct  the same llm.plan / llm.write / reviewer.review functions, in this process
    mock    deterministic text from the facts - OFFLINE SMOKE TEST ONLY, never for the report
"""

import time

from . import hw09_config as cfg
from .util import log, ms_since

COMPONENT = "AGENT"


def find_records(db, query):
    """Rows of s2837_rel (HW9 records) whose restaurant name appears in the query."""
    text = query.lower()
    return [r for r in db.hw9_records() if r["restaurant"].lower() in text]


def facts_text(records):
    if not records:
        return "No specific restaurant record matched this question."
    lines = []
    for r in records:
        viol = "; ".join(r["violations"]) if r["violations"] else "none recorded"
        lines.append(f"- {r['restaurant']}: inspection {r['inspection_code']} on "
                     f"{r['inspection_date']}, status {r['status']}, score {r['score']}; "
                     f"violations: {viol}")
    return "\n".join(lines)


def grounded_question(query, records):
    return (f"{query}\n\nFacts from s2837_rel (use them exactly):\n{facts_text(records)}\n"
            f"{cfg.POLICY_TEXT}")


def run_agent(db, query, mode=None):
    """Run the HW8 pipeline for one question. Returns answer, status, deps, timings."""
    mode = mode or cfg.AGENT_MODE
    records = find_records(db, query)
    question = grounded_question(query, records)
    deps = [r["inspection_code"] for r in records]
    start = time.perf_counter()
    if mode == "kafka":
        from web_application.kafka_pipeline.send_question import ask
        _, final = ask(question, timeout=300)
        if final is None:
            raise RuntimeError("no answer on s2837_final - are planner.py, writer.py and "
                               "reviewer.py running?")
        answer, status, model = final["answer"], final["status"], final.get("writer", {}).get("model")
    elif mode == "direct":
        from web_application.kafka_pipeline import llm
        from web_application.kafka_pipeline.reviewer import review
        steps, _ = llm.plan(question, "PLANNER")
        answer, model = llm.write(question, steps, "WRITER")
        approved, _, _ = review(answer)
        status = "approved" if approved else "rejected"
    elif mode == "mock":
        answer = f"[mock agent] {query} -> " + facts_text(records).replace("\n", " ")
        status, model = "approved", "mock"
        time.sleep(0.05)
    else:
        raise ValueError(f"unknown agent mode {mode}")
    agent_ms = ms_since(start)
    log(COMPONENT, f"agent ({mode}) answered in {agent_ms} ms status={status} deps={deps}")
    return {"answer": answer, "status": status, "deps": deps, "agent_ms": agent_ms,
            "mode": mode, "model": model}

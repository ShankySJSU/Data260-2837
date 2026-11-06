"""HW9 Part 4 - Answering Agent (local Ollama qwen2.5:1.5b via the HW1 adapter,
temperature 0, seed 2837).

Before answering it (1) calls its lookup tool (the s2837_rel row of the restaurant named) and
(2) loads the lessons relevant to the question type. On a revision it also receives its
previous answer and the Evaluator's feedback.

HW9_LLM=mock is a deterministic stand-in used ONLY by the offline smoke test.
"""

import os
import re
import time
from datetime import date, timedelta

from ..util import log
from .domain_kb import classify, lookup_tool

COMPONENT = "ANSWERER"
MODE = os.getenv("HW9_LLM", "ollama")

SYSTEM = ("You answer questions about local restaurant health inspections. Use the lookup "
          "result below as your source. Answer in 1-3 sentences, plain text.")


def build_messages(question, lookup_text, lessons, previous=None, feedback=None):
    system = SYSTEM
    if lessons:
        system += "\n\nLessons from earlier mistakes (follow them):\n" + "\n".join(
            f"- [{x['lesson_id']}] {x['correction']}" for x in lessons)
    user = f"Question: {question}\n\n{lookup_text}"
    if feedback:
        user += (f"\n\nYour previous answer was:\n{previous}\n\nA reviewer checked it against "
                 f"the official records and asked for a revision:\n{feedback}\n"
                 "Write the corrected answer.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class AnsweringAgent:
    name = "answerer"

    def answer(self, question, lessons=(), previous=None, feedback=None, controlled_bad=False):
        start = time.perf_counter()
        qtype = classify(question)
        row, lookup_text = lookup_tool(question)
        messages = build_messages(question, lookup_text, list(lessons), previous, feedback)
        if controlled_bad:
            # 4.1 controlled test case: a deliberately incomplete first answer
            text = (f"{row['restaurant']} had a routine health inspection recently."
                    if row else "I think it was inspected recently.")
            model = "controlled-incomplete (no model call)"
        elif MODE == "mock":
            text, model = _mock(question, qtype, row, messages), "mock"
        else:
            from web_application.agent.adapter import MODEL_NAME, chat
            text = chat(messages, json_mode=False, timeout=180)["content"].strip()
            model = f"ollama:{MODEL_NAME}"
        latency = round((time.perf_counter() - start) * 1000, 1)
        log(COMPONENT, f"{'REVISED' if feedback else 'ANSWER'} ({model}, {latency} ms, lessons="
                       f"{[x['lesson_id'] for x in lessons]}): {text[:140]!r}")
        return {"answer": text, "latency_ms": latency, "model": model, "question_type": qtype,
                "lessons_used": [x["lesson_id"] for x in lessons], "lookup": lookup_text,
                "prompt": messages}


def _mock(question, qtype, row, messages):  # smoke-test stand-in only
    prompt = " ".join(m["content"] for m in messages).lower()
    if qtype == "unknown":
        return ("There is no inspection record for that restaurant." if "no inspection record"
                in prompt else "It scored 88 and passed its last inspection.")
    if qtype == "rule":
        return ("PASS is 85-100, WARNING is 70-84 and FAIL is 0-69." if "85-100" in prompt
                else "A WARNING is usually a score around 60 to 80.")
    name, st, sc = row["restaurant"], row["status"], row["score"]
    if qtype == "reinspection":
        m = re.search(r"due by (\d{4}-\d{2}-\d{2})", prompt)
        if m:
            return f"{name} must be re-inspected by {m.group(1)}."
        if "within 30 days" in prompt:
            days = {"WARNING": 30, "FAIL": 10}.get(st)
            if days is None:
                return f"{name} passed, so no re-inspection is required."
            due = date.fromisoformat(row["inspection_date"]) + timedelta(days=days)
            return f"{name} ({st}) must be re-inspected by {due.isoformat()}."
        return f"{name} was inspected on {row['inspection_date']} with status {st}."
    if qtype == "violations":
        v = "; ".join(row["violations"]) or "no violations were recorded"
        return f"At {name}: {v}."
    if qtype == "score":
        return f"{name} scored {sc} ({st})."
    return (f"{name} received {st} with a score of {sc}." if "numeric score" in prompt
            or "score:" in prompt else f"{name} received a {st}.")

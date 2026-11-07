"""HW9 Part 4 - the two-agent loop and the four system variants.

Agent communication: the orchestrator passes JSON-like messages
    question  -> Answering Agent -> {answer}
    {question, answer} -> Evaluator Agent -> {result, explanation, feedback, failure_codes}
    REVISE -> Answering Agent gets {previous answer, feedback} -> revised answer -> Evaluator
Stopping condition: PASS, or after MAX_ATTEMPTS (2) answers - whichever comes first.
"""

import time

from ..util import log
from .answering_agent import AnsweringAgent
from .domain_kb import classify
from .evaluator_agent import EvaluatorAgent

COMPONENT = "SYSTEM"
MAX_ATTEMPTS = 2

# lessons: None = no lessons, "all" = every saved lesson, "kept" = only validated lessons
VARIANTS = {
    "baseline": {"label": "Baseline", "max_attempts": 1, "lessons": None},
    "repair": {"label": "Evaluator Repair", "max_attempts": 2, "lessons": None},
    "lesson_memory": {"label": "Lesson Memory", "max_attempts": 2, "lessons": "all"},
    "validated": {"label": "Validated Improvement", "max_attempts": 2, "lessons": "kept"},
}


class TwoAgentSystem:
    def __init__(self, store=None):
        self.answerer = AnsweringAgent()
        self.evaluator = EvaluatorAgent()
        self.store = store

    def run(self, qid, question, max_attempts=MAX_ATTEMPTS, allowed_lessons=None,
            use_lessons=False, controlled_bad=False):
        start = time.perf_counter()
        qtype = classify(question)
        lessons = []
        if use_lessons and self.store is not None:
            lessons = self.store.relevant(qtype, allowed_lessons)
            for x in lessons:
                log(COMPONENT, f"LESSON LOADED {x['lesson_id']} ({x['failure_code']}) for {qid} "
                               f"- use_count now {x['use_count']}")
        attempts, previous, feedback = [], None, None
        for n in range(1, max_attempts + 1):
            ans = self.answerer.answer(question, lessons, previous, feedback,
                                       controlled_bad=controlled_bad and n == 1)
            ev = self.evaluator.evaluate(question, ans["answer"])
            attempts.append({"attempt": n, "answer": ans["answer"], "model": ans["model"],
                             "answer_ms": ans["latency_ms"], "evaluation": ev,
                             "feedback_given": feedback})
            log(COMPONENT, f"{qid} attempt {n}: {ev['result']} - {ev['explanation']}"
                           + (f" | feedback: {ev['feedback']}" if ev["feedback"] else ""))
            if ev["result"] == "PASS":
                break
            previous, feedback = ans["answer"], ev["feedback"]
        final = attempts[-1]
        return {"id": qid, "question": question, "question_type": qtype,
                "lessons_loaded": [x["lesson_id"] for x in lessons], "attempts": attempts,
                "n_attempts": len(attempts), "final_answer": final["answer"],
                "final_result": final["evaluation"]["result"],
                "first_failure_codes": attempts[0]["evaluation"]["failure_codes"],
                "latency_ms": round((time.perf_counter() - start) * 1000, 1)}


def summarize(rows):
    n = len(rows)
    correct = sum(r["final_result"] == "PASS" for r in rows)
    return {"questions": n, "correct": correct, "incorrect": n - correct,
            "accuracy_pct": round(100 * correct / n, 1) if n else 0,
            "avg_attempts": round(sum(r["n_attempts"] for r in rows) / n, 2) if n else 0,
            "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / n, 1) if n else 0,
            "unsupported_answers": sum("UNSUPPORTED_CLAIM" in r["attempts"][-1]["evaluation"]
                                       ["failure_codes"] for r in rows)}

"""HW9 Part 4.2 - reusable lessons stored in lessons.json.

A lesson is created when the Evaluator reports the SAME failure code on at least
MIN_OCCURRENCES training answers (a repeated failure pattern). Each lesson has the required
fields lesson_id, failure_pattern, correction, created_at, use_count plus bookkeeping:
failure_code, applies_to (question types it is loaded for), source_question, status
(candidate | kept | rejected) and validation (4.3 result).
"""

import json
from datetime import date

from .. import config as cfg
from ..util import log
from .domain_kb import reference

MIN_OCCURRENCES = 2
COMPONENT = "LESSONS"


def _templates():
    rules = reference()["rules"]
    return {
        "MISSING_REINSPECTION": (
            "Answers about re-inspection omit the due date (or imply one for a PASS).",
            "Compute it from the record: WARNING -> re-inspect within 30 days of the inspection "
            "date, FAIL -> within 10 days, PASS -> no re-inspection is required. State the exact "
            "due date as YYYY-MM-DD.",
            ["reinspection"]),
        "MISSING_RULE": (
            "Answers about score bands omit the numeric thresholds.",
            "Quote the county bands with numbers: " + rules["text"],
            ["rule"]),
        "UNSUPPORTED_CLAIM": (
            "The answer invents a score/status for a restaurant that has no record.",
            "If the lookup finds no record, say there is no inspection record for that "
            "restaurant and do not give any score, status or date.",
            ["unknown"]),
        "MISSING_SCORE": (
            "The answer omits the numeric inspection score.",
            "Always state the numeric score from the record together with the status.",
            ["score", "status"]),
        "MISSING_STATUS": (
            "The answer omits the inspection status.",
            "State the status exactly as recorded (PASS, WARNING or FAIL) and the score.",
            ["status"]),
        "WRONG_STATUS": (
            "The answer reports a status different from the record.",
            "Copy the status word from the record; never infer it from the score yourself.",
            ["status"]),
        "MISSING_VIOLATION": (
            "The answer leaves out recorded violations.",
            "List every violation in the record; if the list is empty say no violations "
            "were recorded.",
            ["violations"]),
    }


class LessonStore:
    def __init__(self, path=cfg.LESSONS_FILE):
        self.path = path
        self.lessons = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        self.counts = {}

    def save(self):
        self.path.write_text(json.dumps(self.lessons, indent=2), encoding="utf-8")

    def reset(self):
        self.lessons, self.counts = [], {}
        self.save()

    def by_code(self, code):
        return next((x for x in self.lessons if x["failure_code"] == code), None)

    def observe(self, codes, question_id, split="training"):
        """Count failure codes; create a lesson when a code repeats. Returns new lessons."""
        assert split != "test", "the test split must never create lessons"
        created = []
        templates = _templates()
        for code in codes:
            self.counts[code] = self.counts.get(code, 0) + 1
            if self.counts[code] >= MIN_OCCURRENCES and not self.by_code(code) and code in templates:
                pattern, correction, applies = templates[code]
                lesson = {"lesson_id": f"lesson_{len(self.lessons) + 1:03d}",
                          "failure_pattern": pattern, "correction": correction,
                          "created_at": date.today().isoformat(), "use_count": 0,
                          "failure_code": code, "applies_to": applies,
                          "source_question": question_id,
                          "occurrences_seen": self.counts[code], "status": "candidate",
                          "validation": None}
                self.lessons.append(lesson)
                created.append(lesson)
                log(COMPONENT, f"LESSON CREATED {lesson['lesson_id']} code={code} after "
                               f"{self.counts[code]} failures (latest {question_id}): "
                               f"{correction[:90]}")
        if created:
            self.save()
        return created

    def relevant(self, qtype, allowed_ids=None):
        """Lessons for this question type; allowed_ids limits which lessons may be used."""
        out = [x for x in self.lessons if qtype in x["applies_to"]
               and (allowed_ids is None or x["lesson_id"] in allowed_ids)]
        for x in out:
            x["use_count"] += 1
        if out:
            self.save()
        return out

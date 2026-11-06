"""HW9 Part 4 - Evaluator Agent.

Checks an answer against reference_data.json (the ground truth) and returns
    {"result": "PASS" | "REVISE", "explanation": str, "feedback": str | None,
     "failure_codes": [...], "checks": {...}}

The check is grounded and deterministic (no second LLM call), so the same answer always gets
the same verdict and the validation/test numbers are reproducible.

Failure codes: MISSING_SCORE, MISSING_STATUS, WRONG_STATUS, MISSING_REINSPECTION,
MISSING_VIOLATION, MISSING_RULE, UNSUPPORTED_CLAIM
"""

import re

from .domain_kb import STATUSES, classify, date_variants, find_restaurant, reference

NO_REINSPECTION = ("no re-inspection", "no reinspection", "not required", "not need",
                   "doesn't need", "does not need", "no follow-up", "no follow up",
                   "not necessary", "none required", "no further inspection")
NO_RECORD = ("no record", "no inspection record", "not found", "don't have", "do not have",
             "no information", "not in our", "not in the", "unable to find", "cannot find",
             "can't find", "couldn't find", "could not find", "no data", "not available")
NO_VIOLATIONS = ("no violation", "none", "zero violation", "0 violation", "clean")


def _has(text, phrases):
    return any(p in text for p in phrases)


def _num(text, n):
    return re.search(rf"(?<![\d.]){n}(?![\d])", text) is not None


class EvaluatorAgent:
    name = "evaluator"

    def __init__(self):
        self.ref = reference()

    def evaluate(self, question, answer):
        text = (answer or "").lower()
        qtype = classify(question, self.ref)
        rec = find_restaurant(question, self.ref)
        codes, checks, fixes = [], {}, []

        if qtype in ("score", "status"):
            checks["score"] = _num(text, rec["score"])
            if not checks["score"]:
                codes.append("MISSING_SCORE")
                fixes.append(f"state the score: {rec['score']}")
        if qtype == "status":
            right = rec["status"].lower() in text
            wrong = [s for s in STATUSES if s != rec["status"] and s.lower() in text]
            checks["status"] = right
            if not right:
                codes.append("WRONG_STATUS" if wrong else "MISSING_STATUS")
                fixes.append(f"the status is {rec['status']}")
        if qtype == "reinspection":
            if rec["reinspection_due"]:
                ok = any(v in text for v in date_variants(rec["reinspection_due"]))
                checks["due_date"] = ok
                if not ok:
                    days = self.ref["rules"]["reinspection_days"][rec["status"]]
                    codes.append("MISSING_REINSPECTION")
                    fixes.append(f"{rec['restaurant']} is {rec['status']} (inspected "
                                 f"{rec['inspection_date']}); {rec['status']} requires "
                                 f"re-inspection within {days} days, so it is due by "
                                 f"{rec['reinspection_due']}")
            else:
                ok = _has(text, NO_REINSPECTION)
                checks["no_reinspection_needed"] = ok
                if not ok:
                    codes.append("MISSING_REINSPECTION")
                    fixes.append(f"{rec['restaurant']} PASSED (score {rec['score']}); a PASS "
                                 "needs no re-inspection - say so and give no due date")
        if qtype == "violations":
            if rec["violations"]:
                missing = [v["text"] for v in rec["violations"]
                           if not _has(text, [k.lower() for k in v["keywords"]])]
                checks["violations_listed"] = not missing
                if missing:
                    codes.append("MISSING_VIOLATION")
                    fixes.append("list every recorded violation; missing: " + "; ".join(missing))
            else:
                ok = _has(text, NO_VIOLATIONS)
                checks["no_violations_stated"] = ok
                if not ok:
                    codes.append("MISSING_VIOLATION")
                    fixes.append("the record has no violations - say none were recorded")
        if qtype == "rule":
            bands = self.ref["rules"]["status_bands"]
            asked = [s for s in STATUSES if s.lower() in question.lower()] or list(STATUSES)
            need = []
            for s in asked:
                lo, hi = bands[s]["min"], bands[s]["max"]
                if s == "PASS":
                    need.append((s, [lo]))
                elif s == "FAIL":
                    need.append((s, [hi, hi + 1]))  # "0-69" or "below 70"
                else:
                    need.append((s, [lo, hi]))
            ok = all(any(_num(text, n) for n in nums) if s == "FAIL" else
                     all(_num(text, n) for n in nums) for s, nums in need)
            checks["rule_numbers"] = ok
            if not ok:
                codes.append("MISSING_RULE")
                fixes.append("use the county bands: " + self.ref["rules"]["text"])
        if qtype == "unknown":
            refused = _has(text, NO_RECORD)
            invented = bool(re.search(r"\b(score[ds]?|scored)\b[^.]{0,25}\b\d{2,3}\b", text)) or \
                (not refused and any(s in text for s in ("passed", "failed", "warning")))
            checks["says_no_record"] = refused
            checks["no_invented_facts"] = not invented
            if not refused or invented:
                codes.append("UNSUPPORTED_CLAIM")
                fixes.append("this restaurant has no inspection record - say so and do not "
                             "give a score, status or date")

        result = "PASS" if not codes else "REVISE"
        explanation = (f"{qtype} question; all required facts present and supported"
                       if result == "PASS" else f"{qtype} question; failed: {', '.join(codes)}")
        return {"result": result, "question_type": qtype, "explanation": explanation,
                "feedback": ("Fix: " + " | ".join(fixes)) if fixes else None,
                "failure_codes": codes, "checks": checks}

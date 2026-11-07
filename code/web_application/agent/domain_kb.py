"""Shared domain helpers for Part 4.

* The Evaluator Agent reads the FULL reference dataset (derived due dates + county rules).
* The Answering Agent only gets a lookup tool that returns the raw record (the same columns
  that are stored in s2837_rel: restaurant, code, date, status, score, violations). It is not
  given the rules or the derived re-inspection date - those are what lessons can teach.
"""

import re

from .. import config as cfg
from ..util import load_json

STATUSES = ("PASS", "WARNING", "FAIL")


def reference():
    return load_json(cfg.REFERENCE_FILE)


def load_split(name):
    return load_json(cfg.AGENT_DATA_DIR / f"{name}_data.json")["questions"]


def find_restaurant(question, ref=None):
    ref = ref or reference()
    text = question.lower()
    for rec in ref["restaurants"]:
        if rec["restaurant"].lower() in text:
            return rec
    return None


def classify(question, ref=None):
    """Question type: reinspection | violations | rule | score | status | unknown."""
    q = question.lower()
    rec = find_restaurant(question, ref)
    if rec is None:
        if re.search(r"range|minimum|lowest score|which score|scores lead|counts as", q):
            return "rule"
        return "unknown"  # names a restaurant that has no record
    if re.search(r"re-?inspect|follow-up|follow up", q):
        return "reinspection"
    if "violation" in q:
        return "violations"
    if "score" in q:
        return "score"
    return "status"


def lookup_tool(question):
    """What the Answering Agent can see: the s2837_rel row(s) for the restaurant named."""
    rec = find_restaurant(question)
    if rec is None:
        if classify(question) == "rule":
            return None, "LOOKUP: the question names no restaurant (general question)."
        return None, "LOOKUP: no inspection record found in s2837_rel for the restaurant named."
    row = {k: rec[k] for k in ("restaurant", "inspection_code", "inspection_date", "status",
                               "score")}
    row["violations"] = [v["text"] for v in rec["violations"]]
    return row, f"LOOKUP (s2837_rel row): {row}"


def date_variants(iso):
    """2026-11-19 -> ['2026-11-19', 'november 19', 'nov 19', 'nov. 19', '11/19']"""
    y, m, d = iso.split("-")
    months = ["january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december"]
    full = months[int(m) - 1]
    day = str(int(d))
    return [iso, f"{full} {day}", f"{full[:3]} {day}", f"{full[:3]}. {day}",
            f"{int(m)}/{day}", f"{m}/{d}"]

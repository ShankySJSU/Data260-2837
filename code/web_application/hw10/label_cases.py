"""HW10 Part 3.1 - hand-labeling helper for human_labels.csv (no model is called).

    cd code
    python -m web_application.hw10.label_cases            # label the unlabeled drafts
    python -m web_application.hw10.label_cases --show     # print the drafts only

Shows each frozen Writer draft with its question and facts and asks ME for a 1-5 helpfulness
label. It refuses to run once judge scores exist, so labels cannot be changed after seeing
the judge.

Scale (same as the judge):
    1 very poor   wrong / contradicts the facts / does not answer the question
    2 poor        partly answers but has a significant error or omission
    3 acceptable  answers with minor inaccuracies, gaps or padding
    4 good        accurate and useful, small omissions or wordiness
    5 excellent   fully accurate, direct, complete and useful
"""

import argparse
import csv
import json
import sys
import textwrap

from . import config as cfg
from .common import load_raw


def read_labels():
    with open(cfg.HUMAN_LABELS, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_labels(rows):
    with open(cfg.HUMAN_LABELS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "human_label", "note"])
        writer.writeheader()
        writer.writerows(rows)


def show(case):
    print("=" * 78)
    print(f"{case['case_id']}   trace_id {case['trace_id']}")
    print("-" * 78)
    print("QUESTION + FACTS GIVEN TO THE WRITER:")
    print(case["judge_input"])
    print("-" * 78)
    print("WRITER DRAFT:")
    for paragraph in case["draft"].splitlines():
        print(textwrap.fill(paragraph, 78) if paragraph.strip() else "")
    print("-" * 78)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not cfg.EVAL_CASES.exists():
        print("run build_eval_cases first")
        return 1
    cases = json.loads(cfg.EVAL_CASES.read_text(encoding="utf-8"))["cases"]
    if args.show:
        for case in cases:
            show(case)
        return 0
    if cfg.JUDGE_SCORES.exists() or load_raw(cfg.PART3_FILE):
        print("Judge scores already exist - human labels are frozen and cannot be edited.")
        return 1
    rows = {r["case_id"]: r for r in read_labels()}
    print(__doc__.split("Scale (same as the judge):")[1])
    for case in cases:
        row = rows.setdefault(case["case_id"], {"case_id": case["case_id"], "human_label": "",
                                                "note": ""})
        if (row.get("human_label") or "").strip():
            continue
        show(case)
        while True:
            answer = input("Your helpfulness label 1-5 (q = save and quit): ").strip().lower()
            if answer == "q":
                write_labels([rows[c["case_id"]] for c in cases])
                return 0
            if answer in {"1", "2", "3", "4", "5"}:
                row["human_label"] = answer
                row["note"] = input("Optional one-line note (Enter to skip): ").strip()
                write_labels([rows[c["case_id"]] for c in cases])  # saved after every label
                break
            print("Please type 1, 2, 3, 4 or 5.")
    print(f"All {len(cases)} drafts are labeled -> {cfg.HUMAN_LABELS}")
    print("Now commit eval_cases.json and human_labels.csv BEFORE running run_part3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

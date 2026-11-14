"""HW10 Part 3 - validate the judge against my human labels.

    cd code
    python -m web_application.hw10.run_part3

Pre-conditions (checked, the script stops otherwise):
  * reports/hw10/eval_cases.json has 20 Writer drafts
  * reports/hw10/human_labels.csv has one hand-assigned 1-5 label per draft
  * both files are committed in git and unmodified (3.1: frozen BEFORE judge scores exist)

It then runs the Writer Helpfulness GEval judge three times on the same 20 drafts with the
same inputs and settings and reports
  3.2  Spearman rank correlation and mean absolute difference, human vs judge (run 1)
  3.3  how often scores change between the three runs and by how much
Outputs: reports/hw10/judge_scores.csv (raw per-case data) and raw/part3_validation.json.
Human labels are only read here - never written.
"""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time

from . import config as cfg
from . import stats, tracing
from .common import banner, log, save_raw
from .judge import Judge

COMPONENT = "PART3"
RUNS = 3


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    out = subprocess.run(["git", "-C", str(cfg.REPO_ROOT), *args], capture_output=True,
                         text=True, timeout=30)
    return out.returncode, out.stdout.strip()


def frozen_state():
    """Commit that froze the two files, or the reason they are not frozen yet."""
    state = {}
    for path in (cfg.EVAL_CASES, cfg.HUMAN_LABELS):
        try:
            rel = path.resolve().relative_to(cfg.REPO_ROOT.resolve()).as_posix()
            code, commit = git("log", "-1", "--format=%H %cI", "--", rel)
            _code2, dirty = git("status", "--porcelain", "--", rel)
        except (ValueError, OSError, subprocess.SubprocessError):  # outside the repo / no git
            code, commit, dirty = 1, "", "?"
        state[path.name] = {"sha256": sha256(path), "commit": commit.split(" ")[0] or None,
                            "committed_at": commit.split(" ")[1] if " " in commit else None,
                            "uncommitted_changes": bool(dirty) or code != 0 or not commit}
    return state


def load_inputs():
    cases = json.loads(cfg.EVAL_CASES.read_text(encoding="utf-8"))["cases"]
    with open(cfg.HUMAN_LABELS, newline="", encoding="utf-8") as handle:
        rows = {r["case_id"]: r for r in csv.DictReader(handle)}
    problems = []
    if len(cases) != 20:
        problems.append(f"eval_cases.json has {len(cases)} cases, expected 20")
    labels = {}
    for case in cases:
        raw = (rows.get(case["case_id"], {}).get("human_label") or "").strip()
        if raw not in {"1", "2", "3", "4", "5"}:
            problems.append(f"{case['case_id']}: human_label is {raw!r} (need 1-5)")
        else:
            labels[case["case_id"]] = int(raw)
    return cases, labels, problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-uncommitted", action="store_true",
                        help="smoke test only: skip the git frozen-file check")
    args = parser.parse_args()
    if not cfg.EVAL_CASES.exists() or not cfg.HUMAN_LABELS.exists():
        print("eval_cases.json / human_labels.csv missing - run build_eval_cases, then label")
        return 1
    cases, labels, problems = load_inputs()
    if problems:
        print("Cannot run the judge yet:\n  " + "\n  ".join(problems))
        return 1
    frozen = frozen_state()
    not_frozen = [name for name, s in frozen.items() if s["uncommitted_changes"]]
    if not_frozen and not args.allow_uncommitted:
        print(f"Not committed yet: {not_frozen}. Commit eval_cases.json and human_labels.csv "
              "BEFORE running the judge (assignment 3.1):\n"
              "  git add reports/hw10/eval_cases.json reports/hw10/human_labels.csv\n"
              '  git commit -m "HW10 3.1: freeze eval cases and human labels"')
        return 1

    judge = Judge()
    banner(COMPONENT, f"HW10 Part 3 - {cfg.STUDENT_NAME} - judge validation on "
                      f"{len(cases)} frozen Writer drafts, {RUNS} runs")
    ok, detail = judge.health()
    

    status = "OK" if ok else "UNAVAILABLE"
    log(COMPONENT, f"judge: {judge.describe().get('model')} - {status} - {detail}")

    frozen_desc = ", ".join(
        f"{n} commit {str(s['commit'])[:10]} sha256 {s['sha256'][:12]}"
        for n, s in frozen.items()
    )
    log(COMPONENT, f"frozen files: {frozen_desc}")
    
    if not ok:
        return 1

    runs, details = [], []
    for run in range(1, RUNS + 1):
        scores, started = [], time.time()
        for case in cases:
            res = judge.score("writer_helpfulness", case["judge_input"], case["draft"])
            scores.append(res["score"])
            details.append({"run": run, "case_id": case["case_id"], "score": res["score"],
                            "geval_score": res["geval_score"], "status": res["status"],
                            "error": res["error"], "ms": res["ms"], "reason": res["reason"]})
            log(COMPONENT, f"run {run} {case['case_id']} human={labels[case['case_id']]} "
                           f"judge={res['score']} ({res['status']}, {res['ms']:.0f} ms)")
        runs.append(scores)
        log(COMPONENT, f"run {run} finished in {time.time() - started:.0f}s")
    judge.close()

    human = [labels[c["case_id"]] for c in cases]
    comparison = []
    for i, scores in enumerate(runs, 1):
        rho = stats.spearman(human, scores)
        mad = stats.mean_abs_diff(human, scores)
        comparison.append({"run": i, "n_scored": sum(s is not None for s in scores),
                           "spearman": round(rho, 4) if rho is not None else None,
                           "mean_abs_difference": round(mad, 4) if mad is not None else None})
    rep = stats.repeatability(runs)
    per_case = [{"case_id": c["case_id"], "trace_id": c["trace_id"], "question": c["question"],
                 "human_label": human[i], **{f"judge_run{r + 1}": runs[r][i]
                                             for r in range(RUNS)},
                 "abs_diff_run1": (abs(human[i] - runs[0][i])
                                   if runs[0][i] is not None else None),
                 "range_across_runs": rep["per_case_range"][i]}
                for i, c in enumerate(cases)]
    result = {
        "generated_at": tracing.iso(time.time()),
        "judge": judge.describe(),
        "criterion": "writer_helpfulness",
        "frozen_files": frozen,
        "frozen_check_skipped": bool(not_frozen),
        "n_cases": len(cases),
        "comparison_primary_run": 1,
        "spearman": comparison[0]["spearman"],
        "mean_abs_difference": comparison[0]["mean_abs_difference"],
        "comparison_by_run": comparison,
        "repeatability": rep,
        "judge_failures": sum(1 for d in details if d["status"] != "ok"),
        "human_distribution": {str(k): human.count(k) for k in range(1, 6)},
        "judge_distribution_run1": {str(k): runs[0].count(k) for k in range(1, 6)},
        "per_case": per_case,
        "calls": details,
    }
    if comparison[0]["spearman"] is None:
        result["spearman_note"] = ("Spearman is undefined because the human labels or the "
                                   "judge scores are all the same value (no ranking).")
    save_raw(cfg.PART3_FILE, result)
    with open(cfg.JUDGE_SCORES, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "trace_id", "human_label", "judge_run1", "judge_run2",
                         "judge_run3", "abs_diff_run1", "range_across_runs"])
        for row in per_case:
            writer.writerow([row["case_id"], row["trace_id"], row["human_label"],
                             row["judge_run1"], row["judge_run2"], row["judge_run3"],
                             row["abs_diff_run1"], row["range_across_runs"]])

    banner(COMPONENT, "RESULTS")
    print(f"{'case':<5} {'human':>5} {'run1':>5} {'run2':>5} {'run3':>5}")
    for row in per_case:
        print(f"{row['case_id']:<5} {row['human_label']:>5} {str(row['judge_run1']):>5} "
              f"{str(row['judge_run2']):>5} {str(row['judge_run3']):>5}")
    log(COMPONENT, f"3.2 Spearman (human vs judge run 1) = {result['spearman']}; "
                   f"mean absolute difference = {result['mean_abs_difference']}")
    log(COMPONENT, f"3.3 repeatability: {rep['cases_with_any_change']}/{rep['cases_comparable']}"
                   f" drafts changed score across {RUNS} runs ({rep['change_rate_pct']}%); "
                   f"mean abs change {rep['mean_abs_change']}, max {rep['max_abs_change']}")
    log(COMPONENT, f"saved {cfg.JUDGE_SCORES} and {cfg.RAW_DIR / cfg.PART3_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

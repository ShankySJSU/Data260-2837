"""HW9 Part 4 - train (create lessons) -> validate (keep/reject) -> test (4 variants) + demos.

    cd code
    python -m web_application.hw9.agents.run_part4 all
    python -m web_application.hw9.agents.run_part4 train|validate|test|demo

Splits: training_data.json creates lessons, validation_data.json decides which lessons are
kept, test_data.json is used ONLY for the final 4-variant evaluation (never creates lessons).
"""

import argparse
import sys

from .. import config as cfg
from ..util import banner, load_raw, log, save_raw
from .domain_kb import load_split
from .lessons import LessonStore
from .system import VARIANTS, TwoAgentSystem, summarize

COMPONENT = "PART4"


def train():
    store = LessonStore()
    store.reset()
    system = TwoAgentSystem(store)
    banner(COMPONENT, f"HW9 Part 4 TRAINING - {cfg.STUDENT_NAME} - repair loop + lessons "
                      "created from repeated failure patterns")
    rows, events = [], []
    for q in load_split("training"):
        res = system.run(q["id"], q["question"], use_lessons=True)
        created = store.observe(res["first_failure_codes"], q["id"], "training")
        res["lessons_created"] = [x["lesson_id"] for x in created]
        rows.append(res)
        for lid in res["lessons_loaded"]:
            events.append({"event": "loaded", "lesson_id": lid, "question_id": q["id"]})
        for lid in res["lessons_created"]:
            events.append({"event": "created", "lesson_id": lid, "question_id": q["id"]})
    save_raw("part4_training.json", {"rows": rows, "lesson_events": events,
                                     "summary": summarize(rows), "lessons": store.lessons})
    log(COMPONENT, f"training done: {summarize(rows)}; lessons created: "
                   f"{[x['lesson_id'] + ':' + x['failure_code'] for x in store.lessons]}")


def _run_split(split, allowed, use_lessons=True, max_attempts=2):
    store = LessonStore()
    system = TwoAgentSystem(store)
    rows = [system.run(q["id"], q["question"], max_attempts=max_attempts,
                       allowed_lessons=allowed, use_lessons=use_lessons)
            for q in load_split(split)]
    return rows


def validate():
    store = LessonStore()
    candidates = [x["lesson_id"] for x in store.lessons]
    banner(COMPONENT, f"HW9 Part 4.3 VALIDATION - candidates {candidates}")
    kept = []
    reference_rows = _run_split("validation", allowed=set(kept), use_lessons=True)
    history = [{"lessons": [], "summary": summarize(reference_rows),
                "per_question": {r["id"]: r["final_result"] for r in reference_rows}}]
    log(COMPONENT, f"validation without lessons: {summarize(reference_rows)}")
    for lid in candidates:
        trial = _run_split("validation", allowed=set(kept + [lid]), use_lessons=True)
        before = {r["id"]: r for r in reference_rows}
        prev_fail = [i for i, r in before.items() if r["final_result"] != "PASS"]
        prev_ok = [i for i, r in before.items() if r["final_result"] == "PASS"]
        after = {r["id"]: r for r in trial}
        fail_after = [i for i in prev_fail if after[i]["final_result"] != "PASS"]
        regressions = [i for i in prev_ok if after[i]["final_result"] != "PASS"]
        unsupported = [r["id"] for r in trial if r["question_type"] == "unknown"
                       and r["final_result"] != "PASS"]
        first_try_before = sum(r["n_attempts"] == 1 and r["final_result"] == "PASS"
                               for r in reference_rows)
        first_try_after = sum(r["n_attempts"] == 1 and r["final_result"] == "PASS" for r in trial)
        checks = {
            "failure_cases_improve_or_unchanged": len(fail_after) <= len(prev_fail),
            "previously_correct_stay_correct": not regressions,
            "unrelated_no_unsupported_answers": not unsupported,
        }
        keep = all(checks.values())
        verdict = {"kept": keep, "checks": checks, "failures_before": prev_fail,
                   "failures_after": fail_after, "regressions": regressions,
                   "unsupported": unsupported, "first_try_pass_before": first_try_before,
                   "first_try_pass_after": first_try_after,
                   "summary_before": summarize(reference_rows), "summary_after": summarize(trial)}
        store = LessonStore()  # reload (use_count changed during the runs)
        lesson = next(x for x in store.lessons if x["lesson_id"] == lid)
        lesson["status"] = "kept" if keep else "rejected"
        lesson["validation"] = verdict
        store.save()
        log(COMPONENT, f"{lid} ({lesson['failure_code']}): {'KEEP' if keep else 'REJECT'} "
                       f"checks={checks} first-try passes {first_try_before}->{first_try_after}")
        history.append({"lessons": kept + [lid], "summary": summarize(trial),
                        "per_question": {r["id"]: r["final_result"] for r in trial},
                        "decision": "kept" if keep else "rejected"})
        if keep:
            kept.append(lid)
            reference_rows = trial
    save_raw("part4_validation.json", {"kept": kept, "candidates": candidates,
                                       "history": history})
    log(COMPONENT, f"validated lessons kept: {kept}")


def test():
    store = LessonStore()
    all_ids = {x["lesson_id"] for x in store.lessons}
    kept_ids = {x["lesson_id"] for x in store.lessons if x["status"] == "kept"}
    banner(COMPONENT, f"HW9 Part 4.4 TEST - 4 variants on test_data.json (all lessons "
                      f"{sorted(all_ids)}, kept {sorted(kept_ids)})")
    results, table = {}, []
    for key, v in VARIANTS.items():
        allowed = {"all": all_ids, "kept": kept_ids}.get(v["lessons"])
        log(COMPONENT, f"--- variant {v['label']}")
        rows = _run_split("test", allowed=allowed, use_lessons=v["lessons"] is not None,
                          max_attempts=v["max_attempts"])
        s = summarize(rows)
        results[key] = {"label": v["label"], "config": v, "summary": s, "rows": rows}
        table.append({"variant": v["label"], **s})
        log(COMPONENT, f"{v['label']}: correct {s['correct']}/{s['questions']}, avg attempts "
                       f"{s['avg_attempts']}, avg latency {s['avg_latency_ms']} ms")
    banner(COMPONENT, "RESULTS (test_data.json)")
    print(f"{'Variant':<24}{'Correct':>8}{'Incorrect':>10}{'Avg attempts':>14}{'Avg ms':>10}")
    for t in table:
        print(f"{t['variant']:<24}{t['correct']:>8}{t['incorrect']:>10}{t['avg_attempts']:>14}"
              f"{t['avg_latency_ms']:>10}")
    save_raw("part4_test.json", {"table": table, "variants": results,
                                 "lessons_all": sorted(all_ids), "lessons_kept": sorted(kept_ids)})


def demo():
    """4.1 controlled revision sequence + 4.2 lesson reuse evidence."""
    banner(COMPONENT, "HW9 Part 4.1 CONTROLLED REVISION DEMO (first answer intentionally "
                      "incomplete)")
    system = TwoAgentSystem(None)
    q = "What score did Rangoli Indian Cuisine receive in its latest inspection?"
    res = system.run("demo_controlled", q, max_attempts=2, controlled_bad=True)
    log(COMPONENT, f"final: {res['final_result']} after {res['n_attempts']} attempts -> "
                   f"{res['final_answer']!r}")
    training = load_raw("part4_training.json", {}) or {}
    events = training.get("lesson_events", [])
    created = {e["lesson_id"]: e["question_id"] for e in events if e["event"] == "created"}
    order = [r["id"] for r in training.get("rows", [])]
    reuse = next((e for e in events if e["event"] == "loaded" and e["lesson_id"] in created
                  and order.index(e["question_id"]) > order.index(created[e["lesson_id"]])),
                 None)
    reuse_row = None
    if reuse:
        reuse_row = next(r for r in training["rows"] if r["id"] == reuse["question_id"])
        src = next(r for r in training["rows"] if r["id"] == created[reuse["lesson_id"]])
        log(COMPONENT, f"4.2 lesson {reuse['lesson_id']} created after failed {src['id']} "
                       f"({src['question']!r}) and LOADED for later {reuse_row['id']} "
                       f"({reuse_row['question']!r}) -> {reuse_row['final_result']} in "
                       f"{reuse_row['n_attempts']} attempt(s)")
    else:
        log(COMPONENT, "4.2 no lesson reuse in training yet - run 'train' first")
    save_raw("part4_demo.json", {"controlled_revision": res, "lesson_reuse": reuse,
                                 "lesson_reuse_row": reuse_row})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["train", "validate", "test", "demo", "all"])
    args = parser.parse_args()
    steps = {"train": [train], "validate": [validate], "test": [test], "demo": [demo],
             "all": [train, validate, test, demo]}[args.what]
    for fn in steps:
        fn()
    return 0


if __name__ == "__main__":
    sys.exit(main())

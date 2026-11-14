"""HW9 self-check -> reports/hw09/verification.json
    cd code
    python -m web_application.verify_hw09

Reads the raw files written by the Part 1-4 scripts (and Redis, if reachable).
"""

import json
import sys

import yaml

from . import hw09_config as cfg
from .util import load_json, load_raw, log, now_iso

COMPONENT = "VERIFY"
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    log(COMPONENT, f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main():
    # ---- Redis ----
    try:
        from .util import redis_client
        r = redis_client(decode=True)
        mods = str(r.execute_command("MODULE", "LIST")).lower()
        check("redis_reachable_with_search_module", "search" in mods, "")
        ours = [k for pat in ("*views*", "*semcache*", "*:dv:*") for k in r.scan_iter(match=pat)]
        bad = [k for k in ours if not k.startswith(cfg.PREFIX + ":")]
        check("all_hw9_redis_keys_start_with_prefix", not bad, f"{len(ours)} keys, bad={bad[:3]}")
    except Exception as exc:  # noqa: BLE001
        check("redis_reachable_with_search_module", False, f"{type(exc).__name__}: {exc}")

    # ---- Part 1 ----
    p1 = load_raw("part1_counter.json") or {}
    totals = [a["total"] for a in p1.get("accesses", [])]
    check("part1_counter_counts_1_to_25", totals == list(range(1, 26)), f"{totals[-1:] }")
    check("part1_synced_every_10", [s["count"] for s in p1.get("syncs", [])] == [10, 20]
          and all(s["db_value"] == s["count"] for s in p1.get("syncs", [])),
          f"syncs={p1.get('syncs')}")
    check("part1_key_has_prefix", str(p1.get("key", "")).startswith(cfg.PREFIX + ":views:"),
          p1.get("key", ""))

    # ---- Part 2 ----
    p2 = load_raw("part2_results.json") or {}
    rows = p2.get("rows", [])
    kinds = " ".join(r["kind"] for r in rows)
    check("part2_at_least_10_queries_mixed", len(rows) >= 10 and "exact" in kinds
          and "paraphrase" in kinds and "new" in kinds, f"{len(rows)} queries")
    check("part2_rows_have_flag_similarity_latency",
          bool(rows) and all({"is_cached", "similarity", "latency_ms"} <= set(r) for r in rows))
    check("part2_exact_duplicates_hit",
          bool(rows) and all(r["is_cached"] for r in rows if r["kind"].startswith("exact")))
    check("part2_summary_reported", {"hit_rate_pct", "avg_latency_cached_ms",
                                     "avg_latency_uncached_ms"} <= set(p2.get("summary", {})),
          str(p2.get("summary")))

    # ---- Part 3 ----
    cases = yaml.safe_load(cfg.CACHE_CASES.read_text(encoding="utf-8"))["cases"]
    cats = {}
    for c in cases:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    check("cache_cases_40_labeled_10_per_category", len(cases) == 40
          and sorted(cats.values()) == [10, 10, 10, 10], str(cats))
    sw = load_raw("part3_sweep.json") or {}
    ths = [t["threshold"] for t in sw.get("table", [])]
    check("sweep_five_thresholds", ths == cfg.SWEEP_THRESHOLDS, str(ths))
    check("sweep_table_complete", all({"hit_rate_pct", "false_hit_rate_pct", "mean_latency_ms",
                                       "total_cost_usd"} <= set(t) for t in sw.get("table", []))
          and bool(sw.get("table")))
    fh = sw.get("false_hit_example") or {}
    check("false_hit_example_complete", all(fh.get(k) for k in (
        "cached_query", "incoming_query", "similarity", "cached_answer_returned",
        "correct_answer")), fh.get("case_id", "none"))
    check("threshold_chosen_by_cost", sw.get("chosen_threshold") in cfg.SWEEP_THRESHOLDS,
          str(sw.get("chosen_threshold")))
    st = load_raw("part3_stale.json") or {}
    s = st.get("steps", [])
    check("stale_hit_demonstrated", len(s) == 5 and s[2]["is_cached"]
          and s[2]["db_score"] != s[0]["db_score"], "")
    check("invalidation_by_data_version", len(s) == 5 and s[3]["stale_detected"]
          and not s[3]["is_cached"] and s[4]["is_cached"], "")

    # ---- Part 4 ----
    no_answers = True
    for split in ("training", "validation", "test"):
        data = load_json(cfg.AGENT_DATA_DIR / f"{split}_data.json")
        for q in data["questions"]:
            if set(q) - {"id", "question"}:
                no_answers = False
    check("input_datasets_contain_questions_only", no_answers)
    lessons = load_json(cfg.LESSONS_FILE)
    req = {"lesson_id", "failure_pattern", "correction", "created_at", "use_count"}
    check("lessons_json_required_fields", bool(lessons) and all(req <= set(x) for x in lessons),
          f"{len(lessons)} lessons")
    check("no_lesson_from_test_split", all(not str(x.get("source_question", "")).startswith("test")
                                           for x in lessons))
    check("lessons_validated", bool(lessons) and all(x.get("status") in ("kept", "rejected")
                                                     for x in lessons),
          str({x["lesson_id"]: x.get("status") for x in lessons}))
    t = load_raw("part4_test.json") or {}
    check("four_variants_on_test", [r["variant"] for r in t.get("table", [])] ==
          ["Baseline", "Evaluator Repair", "Lesson Memory", "Validated Improvement"])
    allrows = [r for v in t.get("variants", {}).values() for r in v["rows"]]
    check("max_two_attempts", bool(allrows) and max(r["n_attempts"] for r in allrows) <= 2)
    d = load_raw("part4_demo.json") or {}
    cr = d.get("controlled_revision") or {}
    check("controlled_revision_sequence", cr.get("n_attempts") == 2
          and cr["attempts"][0]["evaluation"]["result"] == "REVISE", cr.get("final_result", ""))
    check("lesson_reused_on_later_question", bool(d.get("lesson_reuse")),
          str(d.get("lesson_reuse")))

    passed = sum(c["status"] == "PASS" for c in CHECKS)
    out = {"student": cfg.STUDENT_NAME, "prefix": cfg.PREFIX, "generated_at": now_iso(),
           "checks": CHECKS, "summary": {"passed": passed, "total": len(CHECKS)}}
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (cfg.REPORT_DIR / "verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(COMPONENT, f"{passed}/{len(CHECKS)} checks passed -> {cfg.REPORT_DIR / 'verification.json'}")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())

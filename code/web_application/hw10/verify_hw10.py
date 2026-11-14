"""HW10 self-check -> reports/hw10/verification.json

    cd code
    python -m web_application.hw10.verify_hw10

Reads the raw evidence written by the Part 2-4 scripts and recomputes the reported statistics.
"""

import csv
import hashlib
import json
import sys
import time

from . import config as cfg
from . import stats, tracing
from .common import load_raw, log

COMPONENT = "VERIFY"
CHECKS = []
MISS_STAGES = ["cache_lookup", "inbox", "planner", "tasks", "writer", "drafts", "reviewer",
               "final"]


def check(name, ok, detail=""):
    CHECKS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    log(COMPONENT, f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main():
    spans = tracing.read_spans()
    groups = tracing.by_trace(spans)

    # ---- Part 4.1 spans ----
    check("spans_file_has_structured_json_spans", len(spans) > 0, f"{len(spans)} spans")
    check("every_span_has_trace_id_stage_start_end_status",
          bool(spans) and all(s["status"] in ("ok", "error") and s["_end"] >= s["_start"]
                              for s in spans))
    check("error_spans_carry_an_error_message",
          all(s["error"] for s in spans if s["status"] == "error"))

    # ---- Part 4.2 trace examples ----
    ex = load_raw(cfg.TRACES_FILE) or {}
    ids = {k: (ex.get(k) or {}).get("trace_id") for k in ("cache_hit", "cache_miss", "failed")}
    check("three_example_trace_ids_available", all(ids.values())
          and len(set(ids.values())) == 3, str(ids))
    hit = groups.get(ids["cache_hit"], [])
    hit_stages = [s["stage"] for s in tracing.journey(hit)]
    check("cache_hit_trace_has_lookup_hit_and_no_agent_spans",
          hit_stages == ["cache_lookup"] and hit[0]["trace_id"] == ids["cache_hit"]
          and any(s["attrs"].get("cache_hit") is True for s in hit), str(hit_stages))
    miss = groups.get(ids["cache_miss"], [])
    miss_journey = tracing.journey(miss)
    miss_stages = [s["stage"] for s in miss_journey]
    check("cache_miss_trace_completes_agent_path_in_order",
          [s for s in miss_stages if s in MISS_STAGES] == MISS_STAGES
          and all(s["status"] == "ok" for s in miss_journey)
          and any(s["attrs"].get("cache_hit") is False for s in miss), str(miss_stages))
    check("cache_miss_trace_reaches_the_evaluator", "evaluation" in miss_stages)
    failed = groups.get(ids["failed"], [])
    bad = [s for s in tracing.journey(failed) if s["status"] == "error"]
    check("failed_trace_identifies_stage_and_error", bool(bad) and bool(bad[0]["error"]),
          f"{bad[0]['stage']}: {bad[0]['error']}" if bad else "no error span")
    check("examples_ran_on_kafka_pipeline", ex.get("pipeline_mode") == "kafka",
          ex.get("pipeline_mode"))

    # ---- Part 2 evaluation ----
    ev = load_raw(cfg.EVAL_RESULTS) or {}
    records = ev.get("records", [])
    part2 = [r for r in records if r.get("batch") == "part2"]
    check("part2_at_least_one_end_to_end_question_evaluated", len(part2) >= 1,
          f"{len(part2)} records")
    need = {"plan_quality", "writer_helpfulness", "final_helpfulness", "improvement"}
    check("part2_four_criteria_saved", bool(part2)
          and all(need <= set(r.get("criteria", {})) for r in part2))
    scores = [r["criteria"][k]["score"] for r in records
              for k in ("plan_quality", "writer_helpfulness", "final_helpfulness")]
    check("scores_on_1_to_5_scale", bool(scores)
          and all(s is None or s in (1, 2, 3, 4, 5) for s in scores))
    check("plan_quality_has_reason_writer_has_trace_id_final_has_answer", bool(part2) and all(
        (r["criteria"]["plan_quality"]["reason"] or r["criteria"]["plan_quality"]["score"] is None)
        and r["criteria"]["writer_helpfulness"]["trace_id"] == r["trace_id"]
        and "final_answer" in r["criteria"]["final_helpfulness"] for r in part2))
    check("improvement_has_both_scores_difference_interpretation", bool(part2) and all(
        {"draft_score", "final_score", "difference", "interpretation"}
        <= set(r["criteria"]["improvement"]) for r in part2))
    joined = [m["value"].get("correlation_id") == r["trace_id"]
              for r in records for m in (r.get("inputs") or {}).values()]
    check("plan_draft_final_joined_on_correlation_id_equal_to_trace_id",
          bool(joined) and all(joined), f"{len(joined)} messages")
    check("original_messages_kept_with_topic_partition_offset", bool(part2) and all(
        {"topic", "partition", "offset", "value"} <= set(m)
        for r in part2 for m in (r.get("inputs") or {}).values()))
    judge = ev.get("judge") or {}
    check("judge_is_local_geval_and_documented", judge.get("backend") == "ollama"
          and "deepeval" in str(judge.get("framework", "")).lower()
          and judge.get("deepeval_version") not in (None, "NOT INSTALLED"),
          f"{judge.get('model')} deepeval {judge.get('deepeval_version')}")

    # ---- Part 3 judge validation ----
    cases = []
    if cfg.EVAL_CASES.exists():
        cases = json.loads(cfg.EVAL_CASES.read_text(encoding="utf-8")).get("cases", [])
    check("eval_cases_has_20_writer_drafts", len(cases) == 20
          and all(isinstance(c.get("draft"), str) and c["draft"].strip() for c in cases),
          f"{len(cases)} cases")
    labels = {}
    if cfg.HUMAN_LABELS.exists():
        with open(cfg.HUMAN_LABELS, newline="", encoding="utf-8") as handle:
            labels = {r["case_id"]: (r.get("human_label") or "").strip()
                      for r in csv.DictReader(handle)}
    check("human_labels_one_1_to_5_label_per_draft", len(cases) == 20
          and all(labels.get(c["case_id"]) in {"1", "2", "3", "4", "5"} for c in cases))
    p3 = load_raw(cfg.PART3_FILE) or {}
    frozen = p3.get("frozen_files") or {}
    check("eval_cases_and_labels_committed_before_judge_run",
          bool(frozen) and not p3.get("frozen_check_skipped")
          and all(f.get("commit") and not f.get("uncommitted_changes") for f in frozen.values()),
          {n: str(f.get("commit"))[:10] for n, f in frozen.items()})
    same = bool(frozen) and all(
        path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()
        == (frozen.get(path.name) or {}).get("sha256")
        for path in (cfg.EVAL_CASES, cfg.HUMAN_LABELS))
    check("frozen_files_unchanged_since_judge_run_no_relabeling", same)
    rows = []
    if cfg.JUDGE_SCORES.exists():
        with open(cfg.JUDGE_SCORES, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    num = lambda v: int(v) if v not in ("", "None", None) else None  # noqa: E731
    human = [num(r["human_label"]) for r in rows]
    runs = [[num(r[f"judge_run{i}"]) for r in rows] for i in (1, 2, 3)] if rows else []
    check("raw_per_case_data_for_20_drafts_and_3_runs", len(rows) == 20 and len(runs) == 3)
    if rows:
        rho, mad = stats.spearman(human, runs[0]), stats.mean_abs_diff(human, runs[0])
        close = lambda a, b: (a is None and b is None) or (  # noqa: E731
            a is not None and b is not None and abs(a - b) < 1e-3)
        check("spearman_recomputed_from_raw_matches_report", close(rho, p3.get("spearman")),
              f"recomputed {rho} reported {p3.get('spearman')}")
        check("mean_abs_difference_recomputed_matches_report",
              close(mad, p3.get("mean_abs_difference")),
              f"recomputed {mad} reported {p3.get('mean_abs_difference')}")
        rep = stats.repeatability(runs)
        check("repeatability_recomputed_matches_report",
              rep["cases_with_any_change"] == p3["repeatability"]["cases_with_any_change"]
              and rep["max_abs_change"] == p3["repeatability"]["max_abs_change"],
              f"changed {rep['cases_with_any_change']}/20 max {rep['max_abs_change']}")
    check("part3_judge_is_local_not_mock", (p3.get("judge") or {}).get("backend") == "ollama",
          (p3.get("judge") or {}).get("model"))

    # ---- Part 4.3 latency ----
    lat = load_raw(cfg.LATENCY_FILE) or {}
    ok_runs = [r for r in lat.get("runs", []) if r.get("confirmed_miss")]
    check("latency_50_confirmed_cache_misses", len(ok_runs) >= cfg.LATENCY_RUNS
          and all(r["is_cached"] is False for r in ok_runs), f"{len(ok_runs)} misses")
    lookups = [any(s["stage"] == "cache_lookup" and s["attrs"].get("cache_hit") is False
                   for s in groups.get(r["trace_id"], [])) for r in ok_runs]
    check("every_latency_trace_has_a_cache_miss_lookup_span", bool(lookups) and all(lookups))
    table = {r["stage"]: r for r in lat.get("table", [])}
    required = ["Cache lookup", "Planner", "Writer", "Reviewer", "Queue wait (total)",
                "Evaluation"]
    check("stage_table_has_p50_p95_share_for_required_stages",
          all(s in table and table[s]["p50_ms"] is not None and table[s]["p95_ms"] is not None
              for s in required), str([s for s in required if s not in table]))
    share = sum(table[s]["pct_of_end_to_end"] for s in required if s in table) + \
        (table.get("Other (cache store, client overhead)") or {}).get("pct_of_end_to_end", 0)
    check("stage_shares_sum_to_about_100_pct", 97.0 <= share <= 103.0, f"{share:.1f}%")
    check("dominant_contributor_identified", bool(lat.get("dominant")),
          (lat.get("dominant") or {}).get("stage"))
    check("cache_hit_latency_reported_separately",
          (lat.get("cache_hit_latency") or {}).get("n", 0) >= 1,
          str(lat.get("cache_hit_latency")))
    check("latency_ran_on_kafka_pipeline", lat.get("pipeline_mode") == "kafka",
          lat.get("pipeline_mode"))

    # ---- dashboard ----
    check("streamlit_dashboard_present", (cfg.REPO_ROOT / "code" / "web_application" / "hw10"
                                          / "dashboard.py").exists())

    passed = sum(1 for c in CHECKS if c["status"] == "PASS")
    out = {"student": cfg.STUDENT_NAME, "prefix": cfg.PREFIX,
           "generated_at": tracing.iso(time.time()), "passed": passed, "total": len(CHECKS),
           "checks": CHECKS}
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = cfg.REPORT_DIR / "verification.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(COMPONENT, f"{passed}/{len(CHECKS)} checks passed -> {path}")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())

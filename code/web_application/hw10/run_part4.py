"""HW10 Part 4 - trace examples (4.2) and the stage-latency experiment (4.3).

    cd code
    python -m web_application.hw10.run_part4 traces     # one hit, one miss, one failed trace
    python -m web_application.hw10.run_part4 latency    # 50 confirmed cache misses
    python -m web_application.hw10.run_part4 table      # recompute the table from the spans

Needs Redis, MySQL, Kafka, Ollama and the three HW8 agents (planner.py, writer.py,
reviewer.py) running. trace_id = HW8 correlation_id in every span and Kafka message.

4.3 protocol: each request does the real semantic-cache lookup and must come back with
is_cached=False. Experiment answers are NOT stored in the cache (store=False), so an earlier
experiment question can never serve a later one; a candidate that hits an older cache entry
is recorded as excluded and replaced by the next candidate until 50 misses are confirmed
(60 candidates; --flush-cache empties the semantic cache first if too many are excluded).
Every miss is evaluated right after its final answer, so the trace covers cache lookup ->
Kafka -> evaluation. The run is resumable: finished traces are kept in raw/part4_latency.json.
"""

import argparse
import sys
import time

from . import config as cfg
from . import stats, tracing
from .common import banner, load_raw, log, save_raw
from .evaluator import Evaluator, save_evaluation
from .traced_qa import TracedQAService

COMPONENT = "PART4"

RESTAURANTS = ["Rangoli Indian Cuisine", "Taj Grill", "Golden Dragon Bistro", "Urban Taco Cafe",
               "Rustic Garden Deli", "Bayside Sushi Bar", "Spicy Pho House",
               "Golden Crust Bakery", "Cafe Milano", "Grill & Barrel Bar"]
TEMPLATES = [
    "Tell me the exact number of points {r} earned at its most recent health inspection.",
    "List every problem the health inspector wrote up at {r} during the last visit.",
    "Explain why {r} is rated PASS, WARNING or FAIL right now.",
    "Does {r} have a follow-up inspection coming, and what is the deadline for it?",
    "Write a two-sentence notice for customers about the last health inspection at {r}.",
    "As the manager of {r}, what are my next steps after this inspection result?",
]
# 60 candidates (50 needed + 10 spares), template-major so restaurants alternate
CANDIDATES = [t.format(r=r) for t in TEMPLATES for r in RESTAURANTS]

TABLE_ROWS = [("Cache lookup", ["cache_lookup"]), ("Planner", ["planner"]),
              ("Writer", ["writer"]), ("Reviewer", ["reviewer"]),
              ("Queue wait (total)", tracing.QUEUE_STAGES), ("Evaluation", ["evaluation"])]


# ----------------------------------------------------------------------------
# 4.2 trace examples
# ----------------------------------------------------------------------------

def trace_row(trace_id):
    spans = tracing.by_trace(tracing.read_spans()).get(trace_id, [])
    if not spans:
        return {"trace_id": trace_id, "spans": []}
    summary = tracing.summarize(spans)
    summary.pop("_start", None)
    summary["spans"] = [{k: s[k] for k in ("stage", "start_time", "end_time", "duration_ms",
                                           "status", "error", "attrs")}
                        for s in tracing.journey(spans)]
    return summary


def run_traces(args):
    svc = TracedQAService(pipeline_mode=args.pipeline)
    evaluator = Evaluator(pipeline_mode=args.pipeline)
    banner(COMPONENT, f"HW10 Part 4.2 - {cfg.STUDENT_NAME} - cache-hit, cache-miss and failed "
                      f"trace ({svc.mode})")
    question = "What violations were recorded at Spicy Pho House, and when is it re-inspected?"
    removed = svc.ensure_uncached(question)
    if removed:
        log(COMPONENT, f"removed {len(removed)} cached entr(y/ies) so the first request is a "
                       "real miss")

    miss = svc.handle(question)
    log(COMPONENT, f"MISS  trace_id={miss['trace_id']} is_cached={miss['is_cached']} "
                   f"status={miss['status']} latency={miss.get('latency_ms')} ms")
    if miss["status"] == "ok" and not miss["is_cached"]:
        record = evaluator.evaluate(miss["trace_id"], start_offsets=miss.get("start_offsets"),
                                    batch="part4_trace", query=question)
        save_evaluation(record)

    hit = svc.handle(question)
    log(COMPONENT, f"HIT   trace_id={hit['trace_id']} is_cached={hit['is_cached']} "
                   f"similarity={hit.get('similarity')} latency={hit.get('latency_ms')} ms")

    fail_q = "Trace demo: explain the latest inspection result of Golden Crust Bakery."
    failed = svc.handle(fail_q, bypass_cache=False, store=False,
                        inject_failure=args.fail_stage, timeout=args.fail_timeout)
    log(COMPONENT, f"FAIL  trace_id={failed['trace_id']} status={failed['status']} "
                   f"failed_stage={failed['failed_stage']} error={failed['error']}")
    time.sleep(1.0)  # let the agent finish writing its error span

    out = {"generated_at": tracing.iso(time.time()), "pipeline_mode": svc.mode,
           "cache_hit": trace_row(hit["trace_id"]),
           "cache_miss": trace_row(miss["trace_id"]),
           "failed": trace_row(failed["trace_id"]),
           "question": question, "failed_question": fail_q,
           "injected_failure_stage": args.fail_stage,
           "expectations": {"hit_is_cached": bool(hit["is_cached"]),
                            "miss_is_cached": bool(miss["is_cached"]),
                            "miss_status": miss["status"], "failed_status": failed["status"],
                            "failed_stage": failed["failed_stage"],
                            "failed_error": failed["error"]}}
    save_raw(cfg.TRACES_FILE, out)
    banner(COMPONENT, "TRACE IDS (paste into the dashboard Trace lookup page)")
    for label in ("cache_hit", "cache_miss", "failed"):
        row = out[label]
        print(f"  {label:<10} {row['trace_id']}  path={row.get('path')} "
              f"status={row.get('status')} stages="
              f"{[s['stage'] for s in row.get('spans', [])]}")
    log(COMPONENT, f"saved {cfg.RAW_DIR / cfg.TRACES_FILE}")
    svc.close()
    evaluator.close()
    good = (hit["is_cached"] and not miss["is_cached"] and miss["status"] == "ok"
            and failed["status"] == "error")
    return 0 if good else 1


# ----------------------------------------------------------------------------
# 4.3 stage latency
# ----------------------------------------------------------------------------

def stage_table(trace_ids):
    """p50 / p95 per stage and share of cache-miss end-to-end latency for the given traces."""
    groups = tracing.by_trace(tracing.read_spans())
    rows, per_trace = [], []
    for tid in trace_ids:
        spans = groups.get(tid)
        if not spans:
            continue
        s = tracing.summarize(spans)
        d = s["stage_ms"]
        e2e = s["journey_ms"]  # cache_lookup start -> evaluation end
        accounted = sum(d.get(x, 0.0) for x in tracing.STAGE_ORDER)
        per_trace.append({"trace_id": tid, "end_to_end_ms": e2e,
                          "request_ms": s["request_ms"],
                          "stage_ms": {x: d.get(x) for x in tracing.STAGE_ORDER},
                          "queue_wait_ms": s["queue_wait_ms"],
                          "other_ms": round(max(0.0, e2e - accounted), 1)})
    total_e2e = sum(t["end_to_end_ms"] for t in per_trace) or 1.0

    def row(label, values):
        return {"stage": label, "n": len(values),
                "p50_ms": round(stats.percentile(values, 50), 1) if values else None,
                "p95_ms": round(stats.percentile(values, 95), 1) if values else None,
                "mean_ms": round(stats.mean(values), 1) if values else None,
                "pct_of_end_to_end": round(100.0 * sum(values) / total_e2e, 2)}

    for label, stages in TABLE_ROWS:
        values = [sum(t["stage_ms"].get(x) or 0.0 for x in stages) for t in per_trace
                  if all(t["stage_ms"].get(x) is not None for x in stages)]
        rows.append(row(label, values))
    rows.append(row("Other (cache store, client overhead)",
                    [t["other_ms"] + (t["stage_ms"].get("cache_store") or 0.0)
                     for t in per_trace]))
    rows.append(row("End-to-end (cache lookup -> evaluation end)",
                    [t["end_to_end_ms"] for t in per_trace]))
    rows.append(row("User-facing request (cache lookup -> answer)",
                    [t["request_ms"] for t in per_trace if t["request_ms"] is not None]))
    required = rows[:len(TABLE_ROWS)]
    dominant = max(required, key=lambda r: r["pct_of_end_to_end"]) if per_trace else None
    return rows, per_trace, dominant


def hit_latency():
    """Cache-hit latency is reported separately (all hit traces in the span file)."""
    rows = [r for r in tracing.summaries(tracing.read_spans())
            if r["path"] == "hit" and r["status"] == "ok" and r["request_ms"] is not None]
    values = [r["request_ms"] for r in rows]
    return {"n": len(values),
            "p50_ms": round(stats.percentile(values, 50), 1) if values else None,
            "p95_ms": round(stats.percentile(values, 95), 1) if values else None,
            "mean_ms": round(stats.mean(values), 1) if values else None}


def finish_latency(state):
    ok = [r for r in state["runs"] if r["confirmed_miss"]]
    rows, per_trace, dominant = stage_table([r["trace_id"] for r in ok])
    state.update(table=rows, per_trace=per_trace, dominant=dominant,
                 cache_hit_latency=hit_latency(), confirmed_misses=len(ok),
                 all_confirmed_cache_miss=all(not r["is_cached"] for r in ok),
                 max_nearest_similarity=max((r.get("similarity") or 0.0 for r in ok),
                                            default=None),
                 updated_at=tracing.iso(time.time()))
    save_raw(cfg.LATENCY_FILE, state)
    return state


def print_table(state):
    print(f"\n{'Stage':<46} {'p50 (ms)':>10} {'p95 (ms)':>10} {'% of e2e':>9} {'n':>4}")
    for r in state["table"]:
        print(f"{r['stage']:<46} {str(r['p50_ms']):>10} {str(r['p95_ms']):>10} "
              f"{r['pct_of_end_to_end']:>9} {r['n']:>4}")
    hit = state["cache_hit_latency"]
    print(f"\nCache-hit latency (separate metric): n={hit['n']} p50={hit['p50_ms']} ms "
          f"p95={hit['p95_ms']} ms")
    if state.get("dominant"):
        print(f"Dominant contributor: {state['dominant']['stage']} "
              f"({state['dominant']['pct_of_end_to_end']}% of cache-miss end-to-end)\n")


def run_latency(args):
    state = load_raw(cfg.LATENCY_FILE) if not args.restart else None
    state = state or {"runs": [], "excluded": [], "target": args.n,
                      "started_at": tracing.iso(time.time())}
    state["target"] = args.n
    done_q = {r["query"] for r in state["runs"]}  # excluded candidates are retried on resume
    svc = TracedQAService(pipeline_mode=args.pipeline)
    evaluator = Evaluator(pipeline_mode=args.pipeline)
    if args.flush_cache:
        removed = svc.cache.flush()
        state["cache_flushed_entries"] = removed
        log(COMPONENT, f"--flush-cache: removed {removed} semantic-cache entries first")
    state.update(pipeline_mode=svc.mode, threshold=svc.cache.threshold,
                 judge=evaluator.judge.describe().get("model"),
                 protocol="real cache lookup, store=False, hits excluded and replaced")
    banner(COMPONENT, f"HW10 Part 4.3 - {cfg.STUDENT_NAME} - {args.n} confirmed cache misses "
                      f"({svc.mode}); already done: "
                      f"{sum(1 for r in state['runs'] if r['confirmed_miss'])}")
    ok, detail = evaluator.judge.health()
    log(COMPONENT, f"judge health: {'OK' if ok else 'UNAVAILABLE'} - {detail}")
    if not ok:
        return 1
    failures_in_a_row = 0
    for question in CANDIDATES:
        confirmed = sum(1 for r in state["runs"] if r["confirmed_miss"])
        if confirmed >= args.n:
            break
        if failures_in_a_row >= 3:
            log(COMPONENT, "3 requests failed in a row - stopping. Check that Kafka, the "
                           "three agents, Redis and Ollama are running, then rerun (resumes).")
            break
        if question in done_q:
            continue
        state["excluded"] = [e for e in state["excluded"] if e["query"] != question]
        res = svc.handle(question, store=False)
        if res["status"] != "ok":
            state["excluded"].append({"query": question, "trace_id": res["trace_id"],
                                      "reason": f"failed at {res['failed_stage']}: "
                                                f"{res['error']}"})
            log(COMPONENT, f"EXCLUDED (failed) trace_id={res['trace_id']} {res['error']}")
            failures_in_a_row += 1
            finish_latency(state)
            continue
        failures_in_a_row = 0
        if res["is_cached"]:
            state["excluded"].append({"query": question, "trace_id": res["trace_id"],
                                      "reason": f"served from cache (similarity "
                                                f"{res.get('similarity')})"})
            log(COMPONENT, f"EXCLUDED (cache hit, not a miss) trace_id={res['trace_id']}")
            finish_latency(state)
            continue
        record = evaluator.evaluate(res["trace_id"], start_offsets=res.get("start_offsets"),
                                    batch="part4_latency", query=question)
        save_evaluation(record)
        state["runs"].append({"n": confirmed + 1, "trace_id": res["trace_id"],
                              "query": question, "is_cached": res["is_cached"],
                              "similarity": res.get("similarity"),
                              "confirmed_miss": res["is_cached"] is False,
                              "request_ms": res["latency_ms"],
                              "evaluation_status": record["status"]})
        log(COMPONENT, f"#{confirmed + 1}/{args.n} trace_id={res['trace_id']} is_cached=False "
                       f"similarity={res.get('similarity')} request={res['latency_ms']} ms "
                       f"evaluation={record['evaluation_ms']} ms")
        time.sleep(0.3)  # let the agents flush their spans
        finish_latency(state)
    state = finish_latency(state)
    svc.close()
    evaluator.close()
    if state["confirmed_misses"] < args.n:
        log(COMPONENT, f"only {state['confirmed_misses']} confirmed misses - the remaining "
                       "candidates hit the cache or failed. Rerun with --flush-cache to empty "
                       "the semantic cache first (the run resumes where it stopped).")
    banner(COMPONENT, f"STAGE LATENCY over {state['confirmed_misses']} confirmed cache misses "
                      f"(excluded: {len(state['excluded'])})")
    print_table(state)
    log(COMPONENT, f"saved {cfg.RAW_DIR / cfg.LATENCY_FILE}")
    return 0 if state["confirmed_misses"] >= args.n else 1


def run_table(_args):
    state = load_raw(cfg.LATENCY_FILE)
    if not state:
        print("no latency run yet")
        return 1
    print_table(finish_latency(state))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["traces", "latency", "table"])
    parser.add_argument("--pipeline", default=cfg.PIPELINE_MODE, choices=["kafka", "direct"])
    parser.add_argument("--n", type=int, default=cfg.LATENCY_RUNS)
    parser.add_argument("--restart", action="store_true", help="latency: discard earlier runs")
    parser.add_argument("--flush-cache", action="store_true",
                        help="latency: empty the semantic cache before the run")
    parser.add_argument("--fail-stage", default="writer",
                        choices=["planner", "writer", "reviewer"])
    parser.add_argument("--fail-timeout", type=float, default=90.0)
    args = parser.parse_args()
    return {"traces": run_traces, "latency": run_latency, "table": run_table}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

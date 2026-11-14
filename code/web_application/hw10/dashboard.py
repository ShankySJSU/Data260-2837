"""HW10 Part 1 - Streamlit operations dashboard for the s2837 restaurant-inspection Q&A system.

    cd code
    python -m streamlit run web_application/hw10/dashboard.py --server.port 8139

Pages (sidebar):
    Summary       request count, semantic-cache hit rate (hits vs misses), error rate,
                  end-to-end latency, stage-latency table - each with time window + data source
    Evaluation    Part 2 scores by pipeline stage and case, Part 3 judge validation
    Trace lookup  trace_id input -> the full request journey in stage order

The dashboard only READS evidence written by the system: reports/hw10/raw/spans.jsonl (spans),
raw/eval_results.json, raw/part3_validation.json, raw/part4_*.json and the Redis counters.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

from web_application.hw10 import config as cfg  # noqa: E402
from web_application.hw10 import insights, stats, tracing  # noqa: E402
from web_application.hw10.common import load_raw  # noqa: E402

WINDOWS = {"Last 15 minutes": 15 * 60, "Last hour": 3600, "Last 24 hours": 24 * 3600,
           "Last 7 days": 7 * 24 * 3600, "All time": None}
SPAN_SOURCE = f"reports/hw10/raw/{cfg.SPAN_FILE.name}"


# ----------------------------------------------------------------------------
# cached loaders
# ----------------------------------------------------------------------------

def _stamp(path):
    try:
        info = os.stat(path)
        return info.st_mtime, info.st_size
    except OSError:
        return 0.0, 0


@st.cache_data(show_spinner=False)
def load_spans(path, mtime, size):
    """Parse the span file. Cached on (mtime, size): re-parsed only when the file changes."""
    return tracing.read_spans(path)


@st.cache_data(show_spinner=False)
def load_json(name, mtime, size):
    return load_raw(name)


@st.cache_resource(show_spinner=False)
def redis_connection():
    """One reusable Redis connection for the lifetime counters (expensive to re-create)."""
    import redis
    from web_application import hw09_config as h9
    client = redis.Redis(host=h9.REDIS_HOST, port=h9.REDIS_PORT, decode_responses=True,
                         socket_connect_timeout=1.5, socket_timeout=1.5)
    client.ping()
    return client


def spans():
    return load_spans(str(cfg.SPAN_FILE), *_stamp(cfg.SPAN_FILE))


def raw(name):
    return load_json(name, *_stamp(cfg.RAW_DIR / name))


def fmt_ms(value):
    if value is None:
        return "-"
    return f"{value / 1000:.1f} s" if value >= 10000 else f"{value:.0f} ms"


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ----------------------------------------------------------------------------
# Summary page
# ----------------------------------------------------------------------------

def page_summary():
    st.header("Summary - system health")
    choice = st.selectbox("Time window", list(WINDOWS), index=2)
    seconds = WINDOWS[choice]
    now = time.time()
    rows_all = [r for r in tracing.summaries(spans()) if r["request_ms"] is not None]
    rows = [r for r in rows_all if seconds is None or r["_start"] >= now - seconds]
    if seconds is None:
        window = (f"all time ({utc(min(r['_start'] for r in rows))} to {utc(now)})"
                  if rows else "all time")
    else:
        window = f"{choice.lower()} ({utc(now - seconds)} to {utc(now)})"
    source = f"Window: {window} · Source: {SPAN_SOURCE}"

    hits = [r for r in rows if r["path"] == "hit"]
    misses = [r for r in rows if r["path"] == "miss"]
    bypass = [r for r in rows if r["path"] == "bypass"]
    errors = [r for r in rows if r["status"] != "ok"]
    looked_up = len(hits) + len(misses)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Recent requests", len(rows))
        st.caption(f"{source}, one root span (stage = request) per request.")
    with c2:
        st.metric("Semantic-cache hit rate",
                  f"{100 * len(hits) / looked_up:.1f}%" if looked_up else "-")
        st.caption(f"{len(hits)} cache hits / {len(misses)} cache misses. {source}, "
                   "cache_lookup spans (attrs.cache_hit). "
                   f"{len(bypass)} request(s) that skipped the cache on purpose (evaluation "
                   "runs) are not counted.")
    with c3:
        st.metric("Error rate", f"{100 * len(errors) / len(rows):.1f}%" if rows else "-")
        st.caption(f"{len(errors)} failed of {len(rows)} requests. {source}, "
                   "spans with status = error.")

    st.subheader("Cache hits vs cache misses")
    h1, h2 = st.columns(2)
    h1.metric("Cache hits", len(hits))
    h2.metric("Cache misses", len(misses))

    st.subheader("End-to-end latency (request received -> answer returned)")
    ok_miss = [r["request_ms"] for r in misses + bypass if r["status"] == "ok"]
    ok_hit = [r["request_ms"] for r in hits if r["status"] == "ok"]
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Cache-miss p50", fmt_ms(stats.percentile(ok_miss, 50)))
    l2.metric("Cache-miss p95", fmt_ms(stats.percentile(ok_miss, 95)))
    l3.metric("Cache-hit p50", fmt_ms(stats.percentile(ok_hit, 50)))
    l4.metric("Cache-hit p95", fmt_ms(stats.percentile(ok_hit, 95)))
    st.caption(f"{len(ok_miss)} successful agent-path requests and {len(ok_hit)} cache hits; "
               f"cache-hit latency is kept as a separate metric. {source}, duration of the "
               "root request span.")

    st.subheader("Semantic-cache lifetime counters")
    try:
        counters = redis_connection().hgetall(f"{cfg.PREFIX}:semcache:stats")
        r1, r2, r3 = st.columns(3)
        r1.metric("Hits (lifetime)", counters.get("hits", 0))
        r2.metric("Misses (lifetime)", counters.get("misses", 0))
        r3.metric("Stale invalidations", counters.get("stale_invalidations", 0))
        st.caption(f"Window: since the cache was last flushed (not time-windowed) · Source: "
                   f"Redis hash {cfg.PREFIX}:semcache:stats (HW9 counters).")
    except Exception as exc:  # noqa: BLE001
        st.info(f"Redis is not reachable ({type(exc).__name__}); lifetime counters hidden.")

    st.subheader("Stage latency over confirmed cache misses (Part 4.3)")
    latency = raw(cfg.LATENCY_FILE)
    if latency and latency.get("table"):
        table = pd.DataFrame(latency["table"]).rename(columns={
            "stage": "Stage", "p50_ms": "p50 (ms)", "p95_ms": "p95 (ms)",
            "pct_of_end_to_end": "% of cache-miss end-to-end", "n": "n", "mean_ms": "mean (ms)"})
        st.dataframe(table[["Stage", "p50 (ms)", "p95 (ms)", "% of cache-miss end-to-end", "n"]],
                     hide_index=True)
        hit = latency.get("cache_hit_latency") or {}
        st.caption(f"Window: the latency experiment, {latency.get('started_at')} to "
                   f"{latency.get('updated_at')} · {latency.get('confirmed_misses')} requests, "
                   f"all confirmed cache misses = {latency.get('all_confirmed_cache_miss')} · "
                   f"Source: reports/hw10/raw/{cfg.LATENCY_FILE} (computed from the spans). "
                   f"Cache-hit latency (separate): p50 {hit.get('p50_ms')} ms, p95 "
                   f"{hit.get('p95_ms')} ms, n = {hit.get('n')}.")
        for sentence in insights.latency_reading(latency):
            st.write(sentence)
    else:
        st.info("Run `python -m web_application.hw10.run_part4 latency` to fill this table.")

    st.subheader("Most recent requests")
    if rows:
        recent = pd.DataFrame([{
            "start (UTC)": r["start_time"], "trace_id": r["trace_id"], "cache": r["path"],
            "status": r["status"], "failed stage": r["failed_stage"] or "",
            "latency (ms)": r["request_ms"], "query": r["query"]} for r in rows[:25]])
        st.dataframe(recent, hide_index=True)
        st.caption(f"{source}. Copy a trace_id into the Trace lookup page.")
    else:
        st.info("No requests in this window.")


# ----------------------------------------------------------------------------
# Evaluation page
# ----------------------------------------------------------------------------

def page_evaluation():
    st.header("Evaluation - pipeline scores and judge validation")
    data = raw(cfg.EVAL_RESULTS) or {}
    records = data.get("records", [])
    judge = data.get("judge") or {}
    st.caption("All scores use one 1-5 scale: 1 very poor, 2 poor, 3 acceptable, 4 good, "
               f"5 excellent. Judge: GEval (DeepEval {judge.get('deepeval_version', '?')}) with "
               f"{judge.get('model', 'not run yet')}, temperature {judge.get('temperature')}, "
               f"seed {judge.get('seed')}. Source: reports/hw10/raw/{cfg.EVAL_RESULTS}.")

    st.subheader("Part 2 - scores by pipeline stage and case")
    if not records:
        st.info("Run `python -m web_application.hw10.run_part2` first.")
    else:
        batches = sorted({r.get("batch", "part2") for r in records})
        default = [b for b in batches if b in ("part2", "part4_trace")] or batches
        chosen = st.multiselect("Evaluation batches", batches, default=default)
        shown = [r for r in records if r.get("batch", "part2") in chosen]
        table = pd.DataFrame([{
            "case (trace_id)": r["trace_id"],
            "question": r.get("query") or (r.get("question") or "")[:90],
            "Planner: Plan Quality": r["criteria"]["plan_quality"]["score"],
            "Writer: Writer Helpfulness": r["criteria"]["writer_helpfulness"]["score"],
            "Reviewer: Final Answer Helpfulness": r["criteria"]["final_helpfulness"]["score"],
            "draft (final metric)": r["criteria"]["improvement"]["draft_score"],
            "final - draft": r["criteria"]["improvement"]["difference"],
            "review": r.get("final_status"), "eval status": r["status"],
        } for r in shown])
        st.dataframe(table, hide_index=True)
        means = insights.stage_means(shown)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Planner - mean Plan Quality", means["plan_quality"])
        m2.metric("Writer - mean Helpfulness", means["writer_helpfulness"])
        m3.metric("Reviewer - mean Final Helpfulness", means["final_helpfulness"])
        m4.metric("Mean final - draft", means["difference"])

        st.subheader("What the scores say about coordination")
        for sentence in insights.coordination_reading(shown):
            st.write(sentence)

        st.subheader("Case detail")
        ids = [r["trace_id"] for r in shown]
        if ids:
            picked = st.selectbox("Case (trace_id)", ids)
            rec = next(r for r in shown if r["trace_id"] == picked)
            c = rec["criteria"]
            st.write(f"**Question:** {rec.get('query') or rec.get('question')}")
            st.write(f"**Plan Quality {c['plan_quality']['score']}** - "
                     f"{c['plan_quality']['reason']}")
            st.write(f"**Writer Helpfulness {c['writer_helpfulness']['score']}** "
                     f"(trace_id {c['writer_helpfulness']['trace_id']}) - "
                     f"{c['writer_helpfulness']['reason']}")
            st.write(f"**Final Answer Helpfulness {c['final_helpfulness']['score']}** - "
                     f"{c['final_helpfulness']['reason']}")
            imp = c["improvement"]
            st.write(f"**Final vs draft:** draft {imp['draft_score']} -> final "
                     f"{imp['final_score']} (difference {imp['difference']}). "
                     f"{imp['interpretation']}")
            with st.expander("Plan, draft and final answer (original messages)"):
                st.write("Plan steps:", c["plan_quality"].get("plan_steps"))
                st.write("Writer draft:")
                st.write(c["writer_helpfulness"].get("draft"))
                st.write("Final answer:")
                st.write(c["final_helpfulness"].get("final_answer"))
                st.json({role: {k: m.get(k) for k in ("topic", "partition", "offset")}
                         for role, m in (rec.get("inputs") or {}).items()})
            if rec.get("errors"):
                st.warning("Evaluator notes: " + "; ".join(rec["errors"]))

    st.subheader("Part 3 - is the judge reliable?")
    p3 = raw(cfg.PART3_FILE)
    if not p3:
        st.info("Label the 20 drafts, commit them, then run "
                "`python -m web_application.hw10.run_part3`.")
        return
    rep = p3["repeatability"]
    a, b, c3, d = st.columns(4)
    a.metric("Spearman (human vs judge)", p3.get("spearman") if p3.get("spearman") is not None
             else "undefined")
    b.metric("Mean absolute difference", p3.get("mean_abs_difference"))
    c3.metric("Drafts whose score changed", f"{rep['cases_with_any_change']} / "
                                            f"{rep['cases_comparable']}")
    d.metric("Mean / max change", f"{rep['mean_abs_change']} / {rep['max_abs_change']}")
    st.caption(f"{p3['n_cases']} frozen Writer drafts, human labels vs judge run 1; "
               f"repeatability over {rep['n_runs']} identical runs "
               f"({rep['pairwise_changes']} of {rep['pairwise_comparisons']} pairwise "
               f"comparisons differ). Judge: {p3['judge'].get('model')}. Source: "
               f"reports/hw10/judge_scores.csv and raw/{cfg.PART3_FILE}.")
    if p3.get("spearman_note"):
        st.warning(p3["spearman_note"])
    per_case = pd.DataFrame(p3["per_case"])
    st.dataframe(per_case[["case_id", "human_label", "judge_run1", "judge_run2", "judge_run3",
                           "abs_diff_run1", "range_across_runs", "question"]], hide_index=True)
    chart = per_case.set_index("case_id")[["human_label", "judge_run1"]]
    st.bar_chart(chart)
    st.dataframe(pd.DataFrame(p3["comparison_by_run"]), hide_index=True)
    trust = insights.judge_trust_reading(p3)
    st.subheader("Would I trust this judge to gate a deployment?")
    st.write(trust["verdict"])
    st.dataframe(pd.DataFrame(trust["checks"]), hide_index=True)
    st.write("Additional evidence I would require first:")
    for item in trust["needed"]:
        st.write(f"- {item}")


# ----------------------------------------------------------------------------
# Trace lookup page
# ----------------------------------------------------------------------------

def page_trace():
    st.header("Trace lookup - one request, end to end")
    examples = raw(cfg.TRACES_FILE) or {}
    if examples:
        st.caption("Example traces from Part 4.2 (source: "
                   f"reports/hw10/raw/{cfg.TRACES_FILE}):")
        cols = st.columns(3)
        for col, (key, label) in zip(cols, [("cache_hit", "Cache hit"),
                                            ("cache_miss", "Cache miss (agent path)"),
                                            ("failed", "Failed request")]):
            tid = (examples.get(key) or {}).get("trace_id")
            if tid and col.button(f"{label}: {tid[:8]}...", key=key):
                st.session_state["trace_id"] = tid
    trace_id = st.text_input("trace_id (= Kafka correlation_id)", key="trace_id").strip()
    if not trace_id:
        st.info("Enter a trace_id, or pick one on the Summary page.")
        return
    found = tracing.by_trace(spans()).get(trace_id)
    if not found:
        st.error(f"No spans found for trace_id {trace_id} in {SPAN_SOURCE}.")
        return
    summary = tracing.summarize(found)
    if summary["path"] == "hit":
        st.success("CACHE HIT path - the answer came from the semantic cache; Planner, Writer "
                   "and Reviewer were not called.")
    elif summary["path"] == "miss":
        st.warning("CACHE MISS path - the request went through Kafka: inbox -> Planner -> tasks "
                   "-> Writer -> drafts -> Reviewer -> final.")
    elif summary["path"] == "bypass":
        st.warning("CACHE BYPASSED (evaluation run) - the request went through the agent path.")
    if summary["status"] != "ok":
        st.error(f"FAILED at stage **{summary['failed_stage']}**: {summary['error']}")
    a, b, c, d = st.columns(4)
    a.metric("Status", summary["status"])
    b.metric("Request latency", fmt_ms(summary["request_ms"]))
    c.metric("Queue wait (total)", fmt_ms(summary["queue_wait_ms"]))
    d.metric("Similarity", summary["similarity"] if summary["similarity"] is not None else "-")
    if summary.get("query"):
        st.write(f"**Query:** {summary['query']}")

    journey = tracing.journey(found)
    table = pd.DataFrame([{
        "#": i, "stage": s["stage"],
        "kind": ("queue wait" if s["stage"] in tracing.QUEUE_STAGES else
                 "agent" if s["stage"] in tracing.AGENT_STAGES else "service"),
        "start time": s["start_time"], "end time": s["end_time"],
        "duration (ms)": s["duration_ms"], "status": s["status"], "error": s["error"] or "",
        "detail": ", ".join(f"{k}={v}" for k, v in s["attrs"].items()
                            if k in ("cache_hit", "similarity", "agent", "topic", "partition",
                                     "offset", "attempts", "review_status", "bypassed",
                                     "eval_status")),
    } for i, s in enumerate(journey, 1)])
    st.subheader("Journey in stage order")
    st.dataframe(table, hide_index=True)
    st.caption(f"Source: {SPAN_SOURCE}; every span carries this trace_id, which is the HW8 "
               "correlation_id on every Kafka message of the request.")
    durations = table[["stage", "duration (ms)"]].copy()
    durations["stage"] = [f"{i:02d} {s}" for i, s in zip(table["#"], table["stage"])]
    st.bar_chart(durations.set_index("stage"))
    missing = [s for s in tracing.STAGE_ORDER if s not in set(table["stage"])]
    if summary["path"] != "hit" and missing:
        st.caption("Stages with no span for this trace: " + ", ".join(missing))
    with st.expander("Raw span JSON"):
        st.json([{k: v for k, v in s.items() if not k.startswith("_")} for s in found])


# ----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title=f"HW10 operations dashboard ({cfg.PREFIX})", layout="wide")
    st.sidebar.title("HW10 operations dashboard")
    st.sidebar.write(f"{cfg.STUDENT_NAME} · PREFIX {cfg.PREFIX}")
    st.sidebar.caption("Domain: local restaurant inspections")
    page = st.sidebar.radio("Page", ["Summary", "Evaluation", "Trace lookup"])
    if st.sidebar.button("Reload data"):
        st.cache_data.clear()
    st.sidebar.caption(f"Span file: {SPAN_SOURCE} ({len(spans())} spans)")
    {"Summary": page_summary, "Evaluation": page_evaluation, "Trace lookup": page_trace}[page]()


main()

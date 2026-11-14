"""HW10 Part 4 - structured JSON spans.

trace_id IS the HW8 correlation_id (no second identifier). Every stage appends one line to
reports/hw10/raw/spans.jsonl:

    {"trace_id": "...", "stage": "writer", "start_time": "...", "end_time": "...",
     "duration_ms": 1234.5, "status": "ok" | "error", "error": null | "...", "attrs": {...}}

Stages in journey order:
    cache_lookup  embedding + Redis KNN (+ data-version check); attrs.cache_hit tells hit/miss
    inbox         queue wait on s2837_inbox   (produced -> Planner received)
    planner       Planner work                (received -> s2837_tasks acked)
    tasks         queue wait on s2837_tasks
    writer        Writer work
    drafts        queue wait on s2837_drafts
    reviewer      Reviewer work
    final         queue wait on s2837_final   (produced -> request client received)
    cache_store   answer written to the semantic cache
    evaluation    GEval judge calls for this trace
    request       root span: what the caller waited for (cache lookup -> answer returned)

Only the standard library is used so the Kafka agents can import this module.
"""

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config as cfg

STAGE_ORDER = ["cache_lookup", "inbox", "planner", "tasks", "writer", "drafts", "reviewer",
               "final", "cache_store", "evaluation"]
QUEUE_STAGES = ["inbox", "tasks", "drafts", "final"]
AGENT_STAGES = ["planner", "writer", "reviewer"]
ROOT = "request"
TOPIC_STAGE = {f"{cfg.PREFIX}_inbox": "inbox", f"{cfg.PREFIX}_tasks": "tasks",
               f"{cfg.PREFIX}_drafts": "drafts", f"{cfg.PREFIX}_final": "final"}


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds")


def parse_iso(text):
    return datetime.fromisoformat(text).timestamp()


def write_span(trace_id, stage, start_ts, end_ts, status="ok", error=None, **attrs):
    """Append one span. start_ts / end_ts are epoch seconds (time.time())."""
    end_ts = max(end_ts, start_ts)
    record = {
        "trace_id": trace_id,
        "stage": stage,
        "start_time": iso(start_ts),
        "end_time": iso(end_ts),
        "duration_ms": round((end_ts - start_ts) * 1000, 1),
        "status": status,
        "error": error,
        "attrs": {k: v for k, v in attrs.items() if v is not None},
    }
    try:
        cfg.SPAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.SPAN_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")  # one write per span
    except OSError:
        pass  # tracing must never break the request path
    return record


@contextmanager
def span(trace_id, stage, **attrs):
    """with span(tid, "cache_lookup") as s: ...; s["cache_hit"] = True

    An exception inside the block is recorded as status=error and re-raised.
    """
    start = time.time()
    try:
        yield attrs
    except Exception as exc:
        write_span(trace_id, stage, start, time.time(), "error",
                   f"{type(exc).__name__}: {exc}", **attrs)
        raise
    else:
        write_span(trace_id, stage, start, time.time(), "ok", None, **attrs)


# ----------------------------------------------------------------------------
# reading / aggregating (dashboard, experiments, verification)
# ----------------------------------------------------------------------------

REQUIRED = ("trace_id", "stage", "start_time", "end_time", "status")


def read_spans(path=None):
    """All well-formed spans in the file; malformed lines are skipped, never fatal."""
    path = path or cfg.SPAN_FILE
    spans = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and all(rec.get(k) for k in REQUIRED):
                    rec.setdefault("attrs", {})
                    rec.setdefault("error", None)
                    try:
                        rec["_start"] = parse_iso(rec["start_time"])
                        rec["_end"] = parse_iso(rec["end_time"])
                    except (ValueError, TypeError):
                        continue
                    rec.setdefault("duration_ms", round((rec["_end"] - rec["_start"]) * 1000, 1))
                    spans.append(rec)
    except OSError:
        pass
    return spans


def by_trace(spans):
    out = {}
    for s in spans:
        out.setdefault(s["trace_id"], []).append(s)
    return out


def _order_key(s):
    idx = STAGE_ORDER.index(s["stage"]) if s["stage"] in STAGE_ORDER else len(STAGE_ORDER)
    return (idx, s["_start"])


def journey(spans):
    """Spans of ONE trace in stage order (root span excluded)."""
    return sorted((s for s in spans if s["stage"] != ROOT), key=_order_key)


def summarize(spans):
    """One row per trace: path, status, latencies and per-stage durations."""
    spans = list(spans)
    stages = {}
    for s in sorted(spans, key=lambda x: x["_end"]):
        stages[s["stage"]] = s  # the latest span of a stage wins (e.g. a re-run evaluation)
    lookup = stages.get("cache_lookup")
    root = stages.get(ROOT)
    attrs = (lookup or {}).get("attrs", {})
    if attrs.get("bypassed"):
        path = "bypass"
    elif attrs.get("cache_hit") is True:
        path = "hit"
    elif attrs.get("cache_hit") is False:
        path = "miss"
    else:
        path = "unknown"
    failed = [s for s in journey(spans) if s["status"] != "ok"]
    status = "error" if failed or (root and root["status"] != "ok") else "ok"
    first = min(s["_start"] for s in spans)
    dur = {name: s["duration_ms"] for name, s in stages.items()}
    queue = sum(dur.get(q, 0.0) for q in QUEUE_STAGES) if path != "hit" else 0.0
    end_all = max(s["_end"] for s in spans if s["stage"] != ROOT) if journey(spans) else None
    start_all = lookup["_start"] if lookup else first
    return {
        "trace_id": spans[0]["trace_id"],
        "start_time": iso(first),
        "_start": first,
        "path": path,
        "status": status,
        "failed_stage": failed[0]["stage"] if failed else (
            (root or {}).get("attrs", {}).get("failed_stage") if status == "error" else None),
        "error": failed[0]["error"] if failed else ((root or {}).get("error")),
        "similarity": attrs.get("similarity"),
        "query": (root or {}).get("attrs", {}).get("query") or attrs.get("query"),
        "request_ms": root["duration_ms"] if root else None,  # what the caller waited for
        "journey_ms": round((end_all - start_all) * 1000, 1) if end_all else None,
        "queue_wait_ms": round(queue, 1),
        "stage_ms": dur,
        "has_evaluation": "evaluation" in stages,
        "n_spans": len(spans),
    }


def summaries(spans):
    rows = [summarize(group) for group in by_trace(spans).values()]
    return sorted(rows, key=lambda r: r["_start"], reverse=True)

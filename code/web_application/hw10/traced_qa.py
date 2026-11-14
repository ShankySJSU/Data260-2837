"""HW10 Part 4.1 - the HW9 Q&A ingress with end-to-end tracing.

Same behaviour as HW9 qa_service.QAService (semantic cache in front of the HW8 agents), plus:

* one trace_id per request, created here and sent to Kafka as the HW8 correlation_id
* a cache_lookup span (attrs.cache_hit separates the hit path from the miss path)
* a cache_store span and a root "request" span
* failures are returned as status="error" with the failing stage, never raised to the caller
"""

import time
import uuid

from .. import hw09_config as h9
from hw_agents_archive.agent_backend import find_records, grounded_question
from ..embedder import embed
from hw9.hw09_db import Db
from ..semantic_cache import SemanticCache
from ..util import redis_client
from . import tracing
from .common import log
from .pipeline import PipelineError, make_pipeline

COMPONENT = "TRACEDQA"


def new_trace_id():
    return str(uuid.uuid4())  # same format as HW8 kafka_io.new_id()


class TracedQAService:
    def __init__(self, threshold=h9.DEFAULT_THRESHOLD, pipeline_mode=None, db=None,
                 redis_bin=None, pipeline=None):
        self.db = db or Db()
        self.db.ensure_schema()
        self.db.seed_hw9_records()
        self.cache = SemanticCache(redis_bin or redis_client(decode=False), threshold)
        self.pipeline = pipeline or make_pipeline(pipeline_mode)
        self.mode = self.pipeline.mode
        embed("warm-up")  # load MiniLM once so model loading is not timed as query latency

    def handle(self, query, trace_id=None, threshold=None, store=True, bypass_cache=False,
               validate_versions=True, inject_failure=None, timeout=None):
        """Answer one question. Returns a dict that always contains trace_id and status."""
        trace_id = trace_id or new_trace_id()
        threshold = self.cache.threshold if threshold is None else threshold
        started = time.time()
        result = {"trace_id": trace_id, "query": query, "threshold": threshold,
                  "started_at": tracing.iso(started), "pipeline_mode": self.mode,
                  "is_cached": False, "status": "ok", "error": None, "failed_stage": None}

        def finish(status="ok", error=None, **attrs):
            ended = time.time()
            tracing.write_span(trace_id, tracing.ROOT, started, ended, status, error,
                               query=query, cache_hit=result.get("is_cached"),
                               pipeline_mode=self.mode, **attrs)
            result.update(status=status, error=error, finished_at=tracing.iso(ended),
                          latency_ms=round((ended - started) * 1000, 1))
            return result

        # ---- cache lookup (always the first span of a trace) ----
        entry, sim, stale, hit = None, 0.0, False, False
        try:
            with tracing.span(trace_id, "cache_lookup", threshold=threshold) as sp:
                if bypass_cache:
                    sp.update(bypassed=True, cache_hit=False)
                else:
                    entry, sim, embed_ms, search_ms = self.cache.nearest(query)
                    hit = bool(entry) and sim >= threshold
                    if hit and validate_versions:
                        live = self.cache.current_versions(list(entry["deps"]))
                        if any(live.get(c) != v for c, v in entry["deps"].items()):
                            stale, hit = True, False
                            self.cache.delete(entry["key"])
                            self.cache.bump_stat("stale_invalidations")
                    sp.update(cache_hit=hit, similarity=sim, embed_ms=embed_ms,
                              search_ms=search_ms, stale_invalidated=stale or None,
                              matched_query=entry["query"] if entry else None)
                    result.update(similarity=sim, nearest_query=entry["query"] if entry else None)
                    self.cache.bump_stat("hits" if hit else "misses")
        except Exception as exc:  # Redis / embedding failure
            result["failed_stage"] = "cache_lookup"
            log(COMPONENT, f"trace_id={trace_id} cache_lookup FAILED {type(exc).__name__}: {exc}")
            return finish("error", f"{type(exc).__name__}: {exc}", failed_stage="cache_lookup")

        if hit:  # ---- HIT: agents are not called ----
            result.update(answer=entry["answer"], is_cached=True, matched_query=entry["query"],
                          cache_key=entry["key"])
            log(COMPONENT, f"trace_id={trace_id} CACHE HIT similarity={sim:.4f} >= {threshold} "
                           f"query={query!r}")
            return finish()

        # ---- MISS: HW8 agent path, trace_id is the correlation_id ----
        log(COMPONENT, f"trace_id={trace_id} CACHE MISS "
                       f"{'(bypassed)' if bypass_cache else f'best_similarity={sim:.4f}'} "
                       f"query={query!r}")
        try:
            records = find_records(self.db, query)
            versions = self.cache.current_versions([r["inspection_code"] for r in records])
            question = grounded_question(query, records)
            result["grounded_question"] = question
            out = self.pipeline.run(trace_id, question, inject_failure=inject_failure,
                                    timeout=timeout)
        except PipelineError as exc:
            result["failed_stage"] = exc.stage
            log(COMPONENT, f"trace_id={trace_id} FAILED at stage {exc.stage}: {exc.error}")
            return finish("error", exc.error, failed_stage=exc.stage)
        except Exception as exc:  # noqa: BLE001 - e.g. broker unreachable
            result["failed_stage"] = "inbox"
            log(COMPONENT, f"trace_id={trace_id} FAILED before the agents: "
                           f"{type(exc).__name__}: {exc}")
            return finish("error", f"{type(exc).__name__}: {exc}", failed_stage="inbox")

        final = out["final"]
        result.update(answer=final.get("answer"), agent_status=final.get("status"),
                      start_offsets=out.get("start_offsets"), deps=versions,
                      correlation_id=final.get("correlation_id"))
        if store and not bypass_cache:
            try:
                with tracing.span(trace_id, "cache_store") as sp:
                    key = self.cache.put(query, final.get("answer") or "", versions, None,
                                         self.mode)
                    sp["cache_key"] = key
                    result["cache_key"] = key
            except Exception as exc:  # noqa: BLE001 - the answer is still returned
                log(COMPONENT, f"trace_id={trace_id} cache_store failed: {exc}")
        log(COMPONENT, f"trace_id={trace_id} answered by agents status={final.get('status')}")
        return finish(agent_status=final.get("status"))

    def ensure_uncached(self, query):
        """Remove the entry that would serve this query, so the next request is a real miss."""
        removed = []
        for _ in range(5):
            entry, sim, _e, _s = self.cache.nearest(query)
            if not entry or sim < self.cache.threshold:
                break
            self.cache.delete(entry["key"])
            removed.append({"key": entry["key"], "query": entry["query"], "similarity": sim})
            time.sleep(0.05)
        return removed

    def close(self):
        self.pipeline.close()

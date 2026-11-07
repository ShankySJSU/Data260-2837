"""HW9 Part 2 - semantic cache at the ingress of the domain Q&A endpoint.

    hit  (similarity >= threshold, data versions unchanged) -> stored final answer,
         is_cached=True, similarity, latency; the agent pipeline is NOT run
    miss -> HW8 agent pipeline, store query + embedding + answer + data-version marker,
         is_cached=False

Every response carries is_cached, similarity, latency_ms and the timestamps of each stage.
"""

import time

from . import config as cfg
from .agent_backend import run_agent
from .db import Db
from .embedder import embed
from .semantic_cache import SemanticCache
from .util import log, ms_since, now_iso, redis_client

COMPONENT = "QA"


class QAService:
    def __init__(self, threshold=cfg.DEFAULT_THRESHOLD, agent_mode=None, db=None, redis_bin=None):
        self.db = db or Db()
        self.db.ensure_schema()
        self.db.seed_hw9_records()
        self.cache = SemanticCache(redis_bin or redis_client(decode=False), threshold)
        self.agent_mode = agent_mode or cfg.AGENT_MODE
        embed("warm-up")  # load MiniLM once so model loading is not timed as query latency

    def handle(self, query, threshold=None, validate_versions=True, use_cache=True):
        threshold = self.cache.threshold if threshold is None else threshold
        started_at = now_iso()
        t0 = time.perf_counter()
        result = {"query": query, "threshold": threshold, "started_at": started_at}

        vector = embed(query)
        entry, sim, embed_ms, search_ms = (self.cache.nearest(query, vector) if use_cache
                                           else (None, 0.0, 0.0, 0.0))
        result.update(similarity=sim, embed_ms=embed_ms, search_ms=search_ms,
                      nearest_query=entry["query"] if entry else None)

        stale = False
        if entry and sim >= threshold:
            if validate_versions:
                now_versions = self.cache.current_versions(list(entry["deps"]))
                changed = {c: (v, now_versions.get(c)) for c, v in entry["deps"].items()
                           if now_versions.get(c) != v}
                if changed:
                    stale = True
                    self.cache.delete(entry["key"])
                    self.cache.bump_stat("stale_invalidations")
                    log(COMPONENT, f"STALE entry {entry['key']} similarity={sim:.4f} - data "
                                   f"version changed {changed} -> invalidated, running agent")
            if not stale:
                latency = ms_since(t0)
                self.cache.bump_stat("hits")
                log(COMPONENT, f"CACHE HIT similarity={sim:.4f} >= {threshold} latency={latency} "
                               f"ms query={query!r} matched={entry['query']!r}")
                result.update(answer=entry["answer"], is_cached=True, matched_query=entry["query"],
                              cache_key=entry["key"], latency_ms=latency, agent_ms=0.0,
                              stale_detected=False, finished_at=now_iso())
                return result

        # ---- miss: normal HW8 agent path ----
        log(COMPONENT, f"CACHE MISS best_similarity={sim:.4f} < {threshold}"
                       f"{' (stale entry removed)' if stale else ''} query={query!r}")
        self.cache.bump_stat("misses")
        records_codes = [r["inspection_code"] for r in self.db.hw9_records()
                         if r["restaurant"].lower() in query.lower()]
        versions = self.cache.current_versions(records_codes)  # read BEFORE running the agent
        agent = run_agent(self.db, query, self.agent_mode)
        key = None
        if use_cache:
            t_store = time.perf_counter()
            key = self.cache.put(query, agent["answer"], versions, agent["agent_ms"],
                                 agent["mode"], vector)
            result["store_ms"] = ms_since(t_store)
        latency = ms_since(t0)
        log(COMPONENT, f"stored {key} deps={versions} total latency={latency} ms")
        result.update(answer=agent["answer"], is_cached=False, matched_query=None,
                      cache_key=key, latency_ms=latency, agent_ms=agent["agent_ms"],
                      agent_status=agent["status"], deps=versions, stale_detected=stale,
                      finished_at=now_iso())
        return result

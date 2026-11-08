"""Semantic response cache stored in Redis with a RediSearch vector index.

One HASH per cached query:  s2837:semcache:entry:<uuid>
    query, answer, embedding (FLOAT32 bytes), deps (JSON {inspection_code: data_version}),
    created_at, agent_ms, agent_mode
Index s2837:semcache:idx  : FLAT, COSINE, DIM 384, prefix s2837:semcache:entry:
Lookup = KNN 1 on the query embedding; similarity = 1 - cosine distance.

Data-version marker: when an answer is stored, deps records the current value of
s2837:dv:inspection:<code> for every s2837_rel record the answer used. On a hit the
service compares it with the live marker (see qa_service.py).
"""

import json
import os
import time
import uuid

import numpy as np

from . import hw09_config as cfg
from .embedder import cosine, embed
from .util import log, now_iso

COMPONENT = "SEMCACHE"


def _s(value):
    return value.decode("utf-8") if isinstance(value, bytes) else value


class SemanticCache:
    def __init__(self, redis_bin, threshold=cfg.DEFAULT_THRESHOLD):
        """redis_bin must be created with decode_responses=False (embeddings are bytes)."""
        self.r = redis_bin
        self.threshold = threshold
        self.brute_force = os.getenv("HW9_BRUTE_FORCE") == "1"  # smoke test without RediSearch
        if not self.brute_force:
            self.ensure_index()

    # ---- index -----------------------------------------------------------------
    def ensure_index(self):
        from redis.commands.search.field import TextField, VectorField
        try:
            from redis.commands.search.index_definition import IndexDefinition, IndexType
        except ImportError:  # redis-py < 6
            from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        ft = self.r.ft(cfg.CACHE_INDEX)
        try:
            ft.info()
            return
        except Exception as exc:
            if "unknown command" in str(exc).lower():
                raise RuntimeError("Redis has no RediSearch module - start redis-stack "
                                   "(docker compose up -d redis)") from exc
        ft.create_index(
            [TextField("query"),
             VectorField("embedding", "FLAT", {"TYPE": "FLOAT32", "DIM": cfg.EMBED_DIM,
                                               "DISTANCE_METRIC": "COSINE"})],
            definition=IndexDefinition(prefix=[cfg.CACHE_ENTRY_PREFIX], index_type=IndexType.HASH))
        log(COMPONENT, f"created vector index {cfg.CACHE_INDEX} (FLAT, COSINE, dim "
                       f"{cfg.EMBED_DIM}) on prefix {cfg.CACHE_ENTRY_PREFIX}")

    # ---- write -----------------------------------------------------------------
    def put(self, query, answer, deps, agent_ms=None, agent_mode=None, vector=None):
        vector = embed(query) if vector is None else vector
        key = cfg.CACHE_ENTRY_PREFIX + uuid.uuid4().hex[:12]
        self.r.hset(key, mapping={
            "query": query, "answer": answer,
            "embedding": np.asarray(vector, dtype=np.float32).tobytes(),
            "deps": json.dumps(deps), "created_at": now_iso(),
            "agent_ms": str(agent_ms or ""), "agent_mode": agent_mode or "",
        })
        self.r.expire(key, cfg.CACHE_TTL_SECONDS)
        return key

    def delete(self, key):
        return self.r.delete(key)

    def flush(self):
        """Remove every cached entry (keeps the index and the data-version markers)."""
        keys = list(self.r.scan_iter(match=cfg.CACHE_ENTRY_PREFIX + "*", count=500))
        if keys:
            self.r.delete(*keys)
        self.r.delete(cfg.CACHE_STATS_KEY)
        return len(keys)

    def size(self):
        return sum(1 for _ in self.r.scan_iter(match=cfg.CACHE_ENTRY_PREFIX + "*", count=500))

    # ---- read ------------------------------------------------------------------
    def nearest(self, query, vector=None):
        """Return (entry_or_None, similarity, embed_ms, search_ms) for the top-1 neighbour."""
        t0 = time.perf_counter()
        vector = embed(query) if vector is None else vector
        embed_ms = round((time.perf_counter() - t0) * 1000, 2)
        t1 = time.perf_counter()
        entry, sim = (self._nearest_brute(vector) if self.brute_force
                      else self._nearest_index(vector))
        search_ms = round((time.perf_counter() - t1) * 1000, 2)
        return entry, sim, embed_ms, search_ms

    def _nearest_index(self, vector):
        from redis.commands.search.query import Query
        q = (Query("*=>[KNN 1 @embedding $vec AS dist]").sort_by("dist")
             .return_fields("query", "answer", "deps", "created_at", "dist").dialect(2))
        res = self.r.ft(cfg.CACHE_INDEX).search(
            q, query_params={"vec": np.asarray(vector, dtype=np.float32).tobytes()})
        if not res.docs:
            return None, 0.0
        doc = res.docs[0]
        sim = 1.0 - float(_s(doc.dist))
        entry = {"key": _s(doc.id), "query": _s(doc.query), "answer": _s(doc.answer),
                 "deps": json.loads(_s(doc.deps) or "{}"), "created_at": _s(doc.created_at)}
        return entry, round(sim, 4)

    def _nearest_brute(self, vector):
        best, best_sim = None, -1.0
        for key in self.r.scan_iter(match=cfg.CACHE_ENTRY_PREFIX + "*"):
            h = self.r.hgetall(key)
            emb = np.frombuffer(h[b"embedding"], dtype=np.float32)
            sim = cosine(vector, emb)
            if sim > best_sim:
                best_sim = sim
                best = {"key": _s(key), "query": _s(h[b"query"]), "answer": _s(h[b"answer"]),
                        "deps": json.loads(_s(h[b"deps"]) or "{}"),
                        "created_at": _s(h[b"created_at"])}
        return (best, round(best_sim, 4)) if best else (None, 0.0)

    # ---- data-version markers --------------------------------------------------------
    def current_versions(self, codes):
        if not codes:
            return {}
        keys = [cfg.DATA_VERSION_KEY.format(code=c) for c in codes]
        return {c: int(_s(v) or 0) for c, v in zip(codes, self.r.mget(keys))}

    def bump_stat(self, field):
        self.r.hincrby(cfg.CACHE_STATS_KEY, field, 1)

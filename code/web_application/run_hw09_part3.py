"""HW9 Part 3 - threshold sweep, false-hit example, cost model, stale answers.

    cd code
    python -m web_application.hw9.run_part3 sweep    # 3.2 + 3.3 + 3.4
    python -m web_application.hw9.run_part3 stale    # 3.5
    python -m web_application.hw9.run_part3 all

Sweep method
  * Answers: every cached_query and every incoming query is answered ONCE by the HW8 agents
    (default --agent direct, i.e. the same plan/write/review functions without Kafka) and
    saved to raw/part3_agent_memo.json with its measured agent latency (reused on reruns;
    --refresh-memo regenerates).
  * For each threshold: flush the cache, warm it with the 30 cached_query entries, then look
    up each of the 40 queries (live embedding + live Redis KNN, timed). Misses are NOT
    stored, so every case sees the same warm cache.
  * Latency of a hit = measured lookup time. Latency of a miss = measured lookup time + the
    measured agent latency for that query from the memo (the agent is not rerun 5 times).
"""

import argparse
import json
import re
import sys
import time

import yaml

from . import hw09_config as cfg
from .agent_backend import run_agent
from hw09_db import Db
from .embedder import embed, embedder_name
from .qa_service import QAService
from .semantic_cache import SemanticCache
from .util import banner, load_raw, log, ms_since, redis_client, save_raw

COMPONENT = "PART3"

# ---- 3.4 cost model (US$ per query outcome) ----
MISS_COST = 0.02
FALSE_HIT_COST = 2.00
COST_JUSTIFICATION = {
    "miss": "A miss runs the full HW8 Planner->Writer->Reviewer pipeline: two model calls of "
            "~1-2k tokens plus several seconds of user waiting. Priced like a hosted small model "
            "call plus the user's waiting time: $0.02.",
    "false_hit": "A false hit shows a wrong score/status/date for a real restaurant (e.g. "
                 "'Golden Crust Bakery scored 91' when it scored 83). A diner or owner acts on it "
                 "or contacts support: ~6 minutes of staff time at $20/h = $2.00, ignoring "
                 "reputational/legal risk. So one false hit costs as much as 100 misses.",
}


def load_cases():
    data = yaml.safe_load(cfg.CACHE_CASES.read_text(encoding="utf-8"))
    cases = data["cases"]
    counts = {}
    for c in cases:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    assert len(cases) == 40 and all(v == 10 for v in counts.values()), counts
    return cases


def build_memo(db, cases, mode, refresh):
    memo = {} if refresh else (load_raw("part3_agent_memo.json", {}) or {})
    needed = []
    for c in cases:
        for q in (c.get("cached_query"), c["query"]):
            if q and q not in memo and q not in needed:
                needed.append(q)
    log(COMPONENT, f"agent memo: {len(memo)} answers on file, {len(needed)} to generate ({mode})")
    for i, q in enumerate(needed, 1):
        res = run_agent(db, q, mode)
        memo[q] = {"answer": res["answer"], "agent_ms": res["agent_ms"], "deps": res["deps"],
                   "mode": res["mode"], "status": res["status"]}
        log(COMPONENT, f"  [{i}/{len(needed)}] {res['agent_ms']} ms  {q}")
        save_raw("part3_agent_memo.json", memo)
    return memo


def classify(case, hit, matched):
    if case["expected"] == "hit":
        if hit and matched == case["cached_query"]:
            return "true_hit"
        return "false_hit" if hit else "missed_reuse"
    return "false_hit" if hit else "correct_miss"


def sweep(args):
    db = Db()
    db.ensure_schema()
    db.seed_hw9_records()
    cases = load_cases()
    memo = build_memo(db, cases, args.agent, args.refresh_memo)
    cache = SemanticCache(redis_client(decode=False))
    banner(COMPONENT, f"HW9 Part 3.2 - {cfg.STUDENT_NAME} - threshold sweep over 40 labeled "
                      f"cases, embeddings {embedder_name()}")
    warm = sorted({c["cached_query"] for c in cases if c.get("cached_query")})
    warm_vecs = {q: embed(q) for q in warm}
    versions_now = cache.current_versions(sorted({d for q in warm for d in memo[q]["deps"]}))

    table, per_threshold = [], {}
    for th in cfg.SWEEP_THRESHOLDS:
        cache.flush()
        for q in warm:
            deps = {d: versions_now.get(d, 0) for d in memo[q]["deps"]}
            cache.put(q, memo[q]["answer"], deps, memo[q]["agent_ms"], memo[q]["mode"],
                      warm_vecs[q])
        rows = []
        for c in cases:
            t0 = time.perf_counter()
            entry, sim, embed_ms, search_ms = cache.nearest(c["query"])
            lookup_ms = ms_since(t0)
            hit = bool(entry) and sim >= th
            matched = entry["query"] if entry else None
            outcome = classify(c, hit, matched)
            latency = lookup_ms if hit else round(lookup_ms + memo[c["query"]]["agent_ms"], 1)
            rows.append({"id": c["id"], "category": c["category"], "expected": c["expected"],
                         "query": c["query"], "nearest": matched, "similarity": sim,
                         "hit": hit, "outcome": outcome, "lookup_ms": lookup_ms,
                         "embed_ms": embed_ms, "search_ms": search_ms, "latency_ms": latency})
        n = len(rows)
        hits = sum(r["hit"] for r in rows)
        fh = sum(r["outcome"] == "false_hit" for r in rows)
        misses = n - hits
        cost = round(misses * MISS_COST + fh * FALSE_HIT_COST, 2)
        line = {"threshold": th, "hits": hits, "hit_rate_pct": round(100 * hits / n, 1),
                "false_hits": fh, "false_hit_rate_pct": round(100 * fh / n, 1),
                "true_hits": sum(r["outcome"] == "true_hit" for r in rows),
                "missed_reuse": sum(r["outcome"] == "missed_reuse" for r in rows),
                "misses": misses,
                "mean_latency_ms": round(sum(r["latency_ms"] for r in rows) / n, 1),
                "mean_hit_lookup_ms": round(sum(r["lookup_ms"] for r in rows if r["hit"])
                                            / hits, 2) if hits else None,
                "total_cost_usd": cost}
        table.append(line)
        per_threshold[str(th)] = rows
        log(COMPONENT, f"threshold {th:.2f}: hit rate {line['hit_rate_pct']}%  false-hit rate "
                       f"{line['false_hit_rate_pct']}%  mean latency {line['mean_latency_ms']} ms  "
                       f"cost ${cost}")
    cache.flush()

    # similarity of each case at any threshold (the nearest neighbour does not change)
    sims = {cat: [r["similarity"] for r in per_threshold[str(cfg.SWEEP_THRESHOLDS[0])]
                  if r["category"] == cat] for cat in
            ("exact_duplicate", "paraphrase", "similar_different", "unrelated")}
    sim_summary = {k: {"min": min(v), "max": max(v), "mean": round(sum(v) / len(v), 4)}
                   for k, v in sims.items()}

    best = min(table, key=lambda t: (t["total_cost_usd"], -t["threshold"]))
    chosen = best["threshold"]

    # ---- 3.3 one false hit in full ----
    pick_th = str(args.false_hit_threshold)
    fhs = [r for r in per_threshold.get(pick_th, []) if r["outcome"] == "false_hit"]
    if args.false_hit_case:
        fhs = [r for r in fhs if r["id"] == args.false_hit_case] or fhs
    fh_example = None
    if fhs:
        r = max(fhs, key=lambda x: x["similarity"]) if not args.false_hit_case else fhs[0]
        case = next(c for c in cases if c["id"] == r["id"])
        a, b = set(_words(r["nearest"])), set(_words(r["query"]))
        fh_example = {
            "threshold": float(pick_th), "case_id": r["id"], "category": r["category"],
            "cached_query": r["nearest"], "incoming_query": r["query"],
            "similarity": r["similarity"], "cached_answer_returned": memo[r["nearest"]]["answer"],
            "correct_answer": memo[r["query"]]["answer"],
            "why_different": case.get("why_different"),
            "shared_words": sorted(a & b), "differing_words": sorted(a ^ b),
            "word_jaccard": round(len(a & b) / len(a | b), 3),
            "facts_for_incoming": [f"{x['restaurant']} {x['inspection_code']} {x['status']} "
                                   f"{x['score']}" for x in db.hw9_records()
                                   if x["restaurant"].lower() in r["query"].lower()],
        }
        banner(COMPONENT, f"3.3 FALSE HIT at threshold {pick_th} ({r['id']})")
        for k in ("cached_query", "incoming_query", "similarity", "shared_words",
                  "differing_words", "why_different"):
            log(COMPONENT, f"{k}: {fh_example[k]}")
        log(COMPONENT, f"cached answer returned: {fh_example['cached_answer_returned'][:300]}")
        log(COMPONENT, f"correct answer: {fh_example['correct_answer'][:300]}")
    else:
        log(COMPONENT, f"no false hit at threshold {pick_th} - try --false-hit-threshold 0.75")

    banner(COMPONENT, "3.2 / 3.4 THRESHOLD TABLE")
    print(f"{'Threshold':>9} {'Hit rate':>9} {'False-hit':>10} {'Mean ms':>10} {'Total cost':>11}")
    for t in table:
        print(f"{t['threshold']:>9.2f} {t['hit_rate_pct']:>8}% {t['false_hit_rate_pct']:>9}% "
              f"{t['mean_latency_ms']:>10} {'$' + format(t['total_cost_usd'], '.2f'):>11}")
    log(COMPONENT, f"similarity by category: {json.dumps(sim_summary)}")
    log(COMPONENT, f"cost model: miss ${MISS_COST}, false hit ${FALSE_HIT_COST} -> lowest total "
                   f"cost at threshold {chosen} (${best['total_cost_usd']})")
    save_raw("part3_sweep.json", {
        "embedder": embedder_name(), "agent_mode": args.agent, "table": table,
        "rows": per_threshold, "similarity_by_category": sim_summary,
        "cost_model": {"miss_cost_usd": MISS_COST, "false_hit_cost_usd": FALSE_HIT_COST,
                       "justification": COST_JUSTIFICATION,
                       "formula": "total = misses * miss_cost + false_hits * false_hit_cost "
                                  "(40 queries; a hit costs ~0)"},
        "chosen_threshold": chosen, "false_hit_example": fh_example,
        "method": __doc__})
    log(COMPONENT, f"saved {cfg.RAW_DIR / 'part3_sweep.json'}")


def _words(text):
    return re.findall(r"[a-z0-9&']+", (text or "").lower())


def stale(args):
    """3.5 - stale hit, then data-version invalidation."""
    code, restaurant = "S2837-H9-0002", "Taj Grill"
    query = "What is the current status and score of Taj Grill's latest inspection?"
    svc = QAService(threshold=args.threshold, agent_mode=args.agent)
    r = svc.cache.r
    ref = {x["inspection_code"]: x for x in json.loads(cfg.REFERENCE_FILE.read_text())["restaurants"]}
    orig = ref[code]
    banner(COMPONENT, f"HW9 Part 3.5 - {cfg.STUDENT_NAME} - stale answers for {restaurant} "
                      f"({code}) in s2837_rel")
    v = svc.db.update_inspection(code, orig["status"], orig["score"], r)  # clean start
    svc.cache.flush()
    log(COMPONENT, f"reset {code} to {orig['status']} {orig['score']} (data version {v}); cache "
                   "flushed")
    steps = []

    def step(name, **kw):
        res = svc.handle(query, **kw)
        row = svc.db.inspection_by_code(code)
        steps.append({"step": name, "is_cached": res["is_cached"], "similarity": res["similarity"],
                      "stale_detected": res.get("stale_detected"), "latency_ms": res["latency_ms"],
                      "answer": res["answer"], "db_status": row["status"],
                      "db_score": row["score"],
                      "dv_marker": int(r.get(cfg.DATA_VERSION_KEY.format(code=code)) or 0),
                      "entry_deps": res.get("deps")})
        log(COMPONENT, f"[{name}] is_cached={res['is_cached']} sim={res['similarity']:.4f} "
                       f"db={row['status']} {row['score']} answer={res['answer'][:160]!r}")
        return res

    step("1 first ask (miss, stored with data-version marker)")
    step("2 ask again (hit, still correct)")
    new_v = svc.db.update_inspection(code, "PASS", 91, r)
    log(COMPONENT, f"UPDATE s2837_rel.restaurant_inspection {code}: WARNING 78 -> PASS 91 "
                   f"(re-inspection passed); {cfg.DATA_VERSION_KEY.format(code=code)} -> {new_v}")
    step("3 ask with version check OFF (STALE HIT - old answer)", validate_versions=False)
    step("4 ask with version check ON (stale detected -> invalidated -> agent rerun)")
    step("5 ask again (hit on the fresh answer)")
    v = svc.db.update_inspection(code, orig["status"], orig["score"], r)
    log(COMPONENT, f"restored {code} to {orig['status']} {orig['score']} (data version {v})")
    save_raw("part3_stale.json", {"query": query, "record": code, "steps": steps,
                                  "strategy": "per-record data-version marker "
                                              "s2837:dv:inspection:<code>, stored in the entry's "
                                              "deps, compared on every hit"})
    log(COMPONENT, f"saved {cfg.RAW_DIR / 'part3_stale.json'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["sweep", "stale", "all"])
    parser.add_argument("--agent", default="direct", choices=["kafka", "direct", "mock"])
    parser.add_argument("--refresh-memo", action="store_true")
    parser.add_argument("--threshold", type=float, default=cfg.DEFAULT_THRESHOLD)
    parser.add_argument("--false-hit-threshold", type=float, default=0.85)
    parser.add_argument("--false-hit-case", default=None, help="e.g. S01")
    args = parser.parse_args()
    if args.what in ("sweep", "all"):
        sweep(args)
    if args.what in ("stale", "all"):
        stale(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

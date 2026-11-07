"""HW9 Part 2 - run 12 queries (new, exact duplicates, paraphrases) through the semantic cache.

    cd code
    python -m web_application.hw9.run_part2                    # HW8 agents over Kafka
    python -m web_application.hw9.run_part2 --agent direct     # same agents in-process

Starts from an empty cache, threshold 0.85, and reports hit rate and the measured average
latency of cached vs non-cached queries (raw/part2_results.json).
"""

import argparse
import sys

from . import config as cfg
from .embedder import embedder_name
from .qa_service import QAService
from .util import banner, log, save_raw

COMPONENT = "PART2"

QUERIES = [
    ("new", "What score did Taj Grill get in its latest inspection?"),
    ("exact duplicate of #1", "What score did Taj Grill get in its latest inspection?"),
    ("paraphrase of #1", "What was Taj Grill's most recent inspection score?"),
    ("new", "What violations were found at Golden Dragon Bistro?"),
    ("paraphrase of #4", "Which violations did inspectors record at Golden Dragon Bistro?"),
    ("new", "When must Rustic Garden Deli be re-inspected?"),
    ("exact duplicate of #6", "When must Rustic Garden Deli be re-inspected?"),
    ("new", "What temperature must cold food be held at in a restaurant?"),
    ("paraphrase of #8", "At what temperature should a restaurant keep cold food?"),
    ("new", "How often are restaurants inspected in our county?"),
    ("exact duplicate of #4", "What violations were found at Golden Dragon Bistro?"),
    ("new (similar wording to #1, different restaurant)",
     "What score did Cafe Milano get in its latest inspection?"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default=cfg.AGENT_MODE, choices=["kafka", "direct", "mock"])
    parser.add_argument("--threshold", type=float, default=cfg.DEFAULT_THRESHOLD)
    args = parser.parse_args()

    svc = QAService(threshold=args.threshold, agent_mode=args.agent)
    removed = svc.cache.flush()
    banner(COMPONENT, f"HW9 Part 2 - {cfg.STUDENT_NAME} - semantic cache threshold "
                      f"{args.threshold}, embeddings {embedder_name()}, miss path = HW8 agents "
                      f"({args.agent}); cleared {removed} old entries")
    rows = []
    for i, (kind, query) in enumerate(QUERIES, 1):
        log(COMPONENT, f"--- query #{i} [{kind}] {query!r}")
        res = svc.handle(query)
        res.update(n=i, kind=kind)
        rows.append(res)
        log(COMPONENT, f"#{i} is_cached={res['is_cached']} similarity={res['similarity']:.4f} "
                       f"latency_ms={res['latency_ms']} answer={res['answer'][:110]!r}...")

    hits = [r for r in rows if r["is_cached"]]
    misses = [r for r in rows if not r["is_cached"]]
    avg = lambda xs: round(sum(x["latency_ms"] for x in xs) / len(xs), 1) if xs else None  # noqa
    summary = {"queries": len(rows), "hits": len(hits), "misses": len(misses),
               "hit_rate_pct": round(100 * len(hits) / len(rows), 1),
               "avg_latency_cached_ms": avg(hits), "avg_latency_uncached_ms": avg(misses),
               "threshold": args.threshold, "agent_mode": args.agent,
               "embedder": embedder_name()}
    if summary["avg_latency_cached_ms"]:
        summary["observed_ratio"] = round(summary["avg_latency_uncached_ms"]
                                          / summary["avg_latency_cached_ms"], 1)
    banner(COMPONENT, "RESULTS")
    print(f"{'#':>2} {'kind':<26} {'cached':<6} {'sim':>6} {'latency ms':>11}  query")
    for r in rows:
        print(f"{r['n']:>2} {r['kind'][:26]:<26} {str(r['is_cached']):<6} {r['similarity']:>6.3f} "
              f"{r['latency_ms']:>11}  {r['query']}")
    log(COMPONENT, f"hit rate {summary['hit_rate_pct']}% ({len(hits)}/{len(rows)}); avg latency "
                   f"cached {summary['avg_latency_cached_ms']} ms vs non-cached "
                   f"{summary['avg_latency_uncached_ms']} ms")
    save_raw("part2_results.json", {"summary": summary, "rows": rows})
    log(COMPONENT, f"saved {cfg.RAW_DIR / 'part2_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

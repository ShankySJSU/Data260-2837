"""HW10 OFFLINE SMOKE TEST - checks the HW10 logic without Kafka, Redis, MySQL or Ollama.

    cd code
    python -m web_application.hw10.smoke_test

Everything is faked and written to a TEMPORARY folder, never to reports/hw10:
    Redis -> in-memory dict, MySQL -> SQLite, embeddings -> hash bag-of-words,
    agents -> DirectPipeline with the HW8 template text, judge -> mock heuristic,
    human labels -> placeholder numbers.
Its numbers mean nothing and must never be used in the report.
"""

import fnmatch
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="hw10_smoke_")
os.environ.update({
    "HW10_REPORT_DIR": os.path.join(TMP, "hw10"), "HW9_REPORT_DIR": os.path.join(TMP, "hw09"),
    "HW8_REPORT_DIR": os.path.join(TMP, "hw08"), "HW9_SQLITE": os.path.join(TMP, "rel.sqlite"),
    "HW9_EMBEDDER": "hash", "HW9_BRUTE_FORCE": "1", "HW8_LLM": "template",
    "HW10_JUDGE": "mock", "HW10_PIPELINE": "direct",
})
os.environ.pop("HW10_SPAN_FILE", None)


class FakeRedis:
    """The few Redis commands SemanticCache uses in brute-force mode."""

    def __init__(self):
        self.data = {}

    @staticmethod
    def _b(value):
        return value if isinstance(value, bytes) else str(value).encode()

    def hset(self, key, mapping):
        self.data.setdefault(key, {}).update({self._b(k): self._b(v) for k, v in mapping.items()})

    def hgetall(self, key):
        return dict(self.data.get(key.decode() if isinstance(key, bytes) else key, {}))

    def hincrby(self, key, field, amount):
        h = self.data.setdefault(key, {})
        h[self._b(field)] = self._b(int(h.get(self._b(field), b"0")) + amount)

    def expire(self, key, seconds):
        return True

    def delete(self, *keys):
        return sum(1 for k in keys
                   if self.data.pop(k.decode() if isinstance(k, bytes) else k, None) is not None)

    def scan_iter(self, match="*", count=None):
        return [k.encode() for k in list(self.data) if fnmatch.fnmatch(k, match)]

    def mget(self, keys):
        return [self.data.get(k) for k in keys]


def run(module, argv):
    old = sys.argv
    sys.argv = [module.__name__] + argv
    try:
        code = module.main()
    finally:
        sys.argv = old
    print(f"--> {module.__name__.split('.')[-1]} {' '.join(argv)} exit code {code}\n")
    return code


def main():
    import csv

    from . import (build_eval_cases, config as cfg, make_hw10_report, run_part2, run_part3,
                   run_part4, traced_qa, verify_hw10)
    fake = FakeRedis()
    traced_qa.redis_client = lambda decode=True: fake
    codes = {}
    codes["part2"] = run(run_part2, [])
    codes["traces"] = run(run_part4, ["traces"])
    codes["latency"] = run(run_part4, ["latency", "--n", "8"])
    codes["cases"] = run(build_eval_cases, [])
    with open(cfg.HUMAN_LABELS, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for i, row in enumerate(rows):  # placeholder numbers, smoke test only
        row["human_label"] = str(1 + (i * 7) % 5)
    with open(cfg.HUMAN_LABELS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "human_label", "note"])
        writer.writeheader()
        writer.writerows(rows)
    codes["part3"] = run(run_part3, ["--allow-uncommitted"])
    run(verify_hw10, [])  # several checks fail by design here (direct mode, mock judge, n=8)
    codes["report"] = run(make_hw10_report, [])
    print(f"smoke output folder: {cfg.REPORT_DIR}")
    print("exit codes:", codes)
    ok = all(v == 0 for v in codes.values())
    print("SMOKE TEST", "PASSED" if ok else "FAILED",
          "(logic only - not evidence for the report)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

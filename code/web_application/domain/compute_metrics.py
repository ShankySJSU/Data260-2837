import csv
from collections import defaultdict

INPUT_FILE = "../../../reports/hw04/raw/n_plus_one_raw.csv"
OUTPUT_MD = "../../../reports/hw04/METRICS.md"


def percentile(data, p):
    """Linear-interpolation percentile, matching numpy's default method."""
    data = sorted(data)
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(data) else f
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def main():
    groups = defaultdict(list)

    with open(INPUT_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["version"], int(row["page_size"]))
            groups[key].append({
                "latency": float(row["latency_ms"]),
                "sql": int(row["sql_queries"]) if row["sql_queries"] else None,
            })

    lines = [
        "| Page size | Version | SQL stmts/req | p50 (ms) | p95 (ms) | p99 (ms) |",
        "|---|---|---|---|---|---|",
    ]

    for page_size in sorted({k[1] for k in groups}):
        for version in ["naive", "fixed"]:
            entries = groups[(version, page_size)]
            if not entries:
                continue
            latencies = [e["latency"] for e in entries]
            sql_counts = {e["sql"] for e in entries}
            sql_str = str(sql_counts.pop()) if len(sql_counts) == 1 else f"varied {sql_counts}"

            p50 = percentile(latencies, 50)
            p95 = percentile(latencies, 95)
            p99 = percentile(latencies, 99)

            lines.append(
                f"| {page_size} | {version} | {sql_str} | {p50:.2f} | {p95:.2f} | {p99:.2f} |"
            )
            print(f"page_size={page_size} version={version} n={len(entries)} "
                  f"sql={sql_str} p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms")

    with open(OUTPUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")

    print("\nWritten to", OUTPUT_MD)


if __name__ == "__main__":
    main()
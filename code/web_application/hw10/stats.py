"""Small statistics helpers (no SciPy needed) so every reported number can be recomputed."""


def percentile(values, q):
    """Linear-interpolation percentile (same definition as numpy.percentile). q in 0..100."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return float(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo))


def mean(values):
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def ranks(values):
    """Average ranks (ties share the mean of their positions), 1-based."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None  # undefined when one side is constant
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


def paired(xs, ys):
    """Keep only positions where both values exist."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def spearman(xs, ys):
    """Spearman rank correlation with average ranks for ties; None if undefined."""
    xs, ys = paired(xs, ys)
    if len(xs) < 2:
        return None
    return pearson(ranks(xs), ranks(ys))


def mean_abs_diff(xs, ys):
    xs, ys = paired(xs, ys)
    if not xs:
        return None
    return sum(abs(x - y) for x, y in zip(xs, ys)) / len(xs)


def repeatability(runs):
    """runs = list of score lists (one per repeated run, same case order).

    Returns how often and by how much scores change between repeated runs.
    """
    n_cases = len(runs[0]) if runs else 0
    changed, per_case_range, diffs, pair_stats = 0, [], [], []
    for i in range(n_cases):
        scores = [r[i] for r in runs if r[i] is not None]
        rng = (max(scores) - min(scores)) if len(scores) >= 2 else None
        per_case_range.append(rng)
        if rng:
            changed += 1
    for a in range(len(runs)):
        for b in range(a + 1, len(runs)):
            xa, xb = paired(runs[a], runs[b])
            d = [abs(x - y) for x, y in zip(xa, xb)]
            diffs.extend(d)
            pair_stats.append({"runs": f"{a + 1} vs {b + 1}", "n": len(d),
                               "changed": sum(1 for v in d if v),
                               "mean_abs_change": (sum(d) / len(d)) if d else None,
                               "max_abs_change": max(d) if d else None})
    comparable = sum(1 for r in per_case_range if r is not None)
    return {
        "n_cases": n_cases,
        "n_runs": len(runs),
        "cases_comparable": comparable,
        "cases_with_any_change": changed,
        "change_rate_pct": round(100.0 * changed / comparable, 1) if comparable else None,
        "pairwise_comparisons": len(diffs),
        "pairwise_changes": sum(1 for v in diffs if v),
        "mean_abs_change": round(sum(diffs) / len(diffs), 4) if diffs else None,
        "mean_abs_change_when_changed": (round(sum(v for v in diffs if v)
                                               / sum(1 for v in diffs if v), 4)
                                         if any(diffs) else 0.0),
        "max_abs_change": max(diffs) if diffs else None,
        "per_case_range": per_case_range,
        "by_run_pair": pair_stats,
    }

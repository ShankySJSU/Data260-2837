"""Plain-language readings computed from the measured results (dashboard + report).

Nothing here invents a result: every sentence is chosen by the numbers in the raw files, and
a missing or negative result is reported as such.
"""

from . import stats

# my criteria for "would I let this judge gate a deployment?"
TRUST_MIN_SPEARMAN = 0.70
TRUST_MAX_MAD = 0.75
TRUST_MAX_CHANGE_RATE_PCT = 10.0
TRUST_MAX_ABS_CHANGE = 1


def stage_means(records):
    def avg(path):
        values = []
        for r in records:
            node = r.get("criteria", {})
            for key in path:
                node = node.get(key) if isinstance(node, dict) else None
            values.append(node)
        m = stats.mean(values)
        return round(m, 2) if m is not None else None
    return {"plan_quality": avg(["plan_quality", "score"]),
            "writer_helpfulness": avg(["writer_helpfulness", "score"]),
            "final_helpfulness": avg(["final_helpfulness", "score"]),
            "draft_same_metric": avg(["improvement", "draft_score"]),
            "difference": avg(["improvement", "difference"]),
            "n": len(records)}


def coordination_reading(records):
    """What the Part 2 scores say about Planner / Writer / Reviewer coordination."""
    if not records:
        return ["No evaluation has been run yet."]
    m = stage_means(records)
    out = [f"Across {m['n']} evaluated request(s) the mean scores on the 1-5 scale are: Plan "
           f"Quality {m['plan_quality']}, Writer Helpfulness {m['writer_helpfulness']}, Final "
           f"Answer Helpfulness {m['final_helpfulness']}."]
    plan, writer = m["plan_quality"], m["writer_helpfulness"]
    if plan is not None and writer is not None:
        if plan - writer >= 1:
            out.append("Planner -> Writer: the plans score clearly higher than the drafts, so "
                       "the Writer is the weaker link - a usable plan is not being turned into "
                       "an equally good answer.")
        elif writer - plan >= 1:
            out.append("Planner -> Writer: the drafts score clearly higher than the plans. This suggests the "
                       "Writer answers mostly from the facts in the question and gets little "
                       "from the plan, so the Planner adds limited value in this hand-off.")
        else:
            out.append("Planner -> Writer: plan and draft scores are within one point of each "
                       "other, so the hand-off neither loses nor adds much quality.")
    improv = [r["criteria"]["improvement"] for r in records if "criteria" in r]
    identical = sum(1 for i in improv if i.get("texts_identical"))
    diffs = [i["difference"] for i in improv if i.get("difference") is not None]
    up = sum(1 for d in diffs if d > 0)
    down = sum(1 for d in diffs if d < 0)
    out.append(f"Writer -> Reviewer: in {identical} of {len(improv)} request(s) the final "
               f"answer is identical to the draft. Final-minus-draft difference: {up} higher, "
               f"{down} lower, {len(diffs) - up - down} unchanged (mean {m['difference']}).")
    if improv and identical == len(improv):
        out.append("The final answer did NOT improve on the draft. This is expected from the "
                   "design: my HW8 Reviewer is a rule-based gate (length, on-domain, no error "
                   "text) that approves or rejects but never edits, so the Reviewer cannot "
                   "raise quality - it can only block a bad draft. Any non-zero difference "
                   "between identical texts is judge noise.")
        rejected = sum(1 for r in records if r.get("final_status") == "rejected")
        low = sum(1 for r in records
                  if (r["criteria"]["final_helpfulness"].get("score") or 5) <= 2
                  and r.get("final_status") == "approved")
        if low:
            out.append(f"{low} answer(s) scored 2 or lower were still approved by the "
                       "Reviewer, so its rules do not catch unhelpful or inaccurate drafts.")
        out.append(f"Reviewer decisions in this set: {len(records) - rejected} approved, "
                   f"{rejected} rejected.")
    elif diffs and up > down:
        out.append("The review step improved the answer more often than it hurt it.")
    elif diffs:
        out.append("The review step did not improve the answers overall.")
    return out


def judge_trust_reading(p3):
    """Would I trust the judge to gate a deployment? Decided by the criteria above."""
    if not p3:
        return {"verdict": "No judge validation has been run yet.", "checks": [], "needed": []}
    rep = p3["repeatability"]
    rho, mad = p3.get("spearman"), p3.get("mean_abs_difference")
    checks = [
        {"check": f"Spearman vs human >= {TRUST_MIN_SPEARMAN}", "value": rho,
         "ok": rho is not None and rho >= TRUST_MIN_SPEARMAN},
        {"check": f"Mean absolute difference <= {TRUST_MAX_MAD}", "value": mad,
         "ok": mad is not None and mad <= TRUST_MAX_MAD},
        {"check": f"Drafts whose score changed across 3 runs <= {TRUST_MAX_CHANGE_RATE_PCT}%",
         "value": rep.get("change_rate_pct"),
         "ok": rep.get("change_rate_pct") is not None
         and rep["change_rate_pct"] <= TRUST_MAX_CHANGE_RATE_PCT},
        {"check": f"Largest score change <= {TRUST_MAX_ABS_CHANGE}",
         "value": rep.get("max_abs_change"),
         "ok": rep.get("max_abs_change") is not None
         and rep["max_abs_change"] <= TRUST_MAX_ABS_CHANGE},
        {"check": "No failed judge calls", "value": p3.get("judge_failures"),
         "ok": p3.get("judge_failures") == 0},
    ]
    passed = sum(1 for c in checks if c["ok"])
    if passed == len(checks):
        verdict = ("All of my criteria are met on these 20 drafts, but 20 drafts labeled by one "
                   "person is too little evidence for an automatic gate. I would use the judge "
                   "as a warning signal on deployments now and make it a blocking gate only "
                   "after the additional evidence below.")
    else:
        failed = "; ".join(c["check"] for c in checks if not c["ok"])
        verdict = (f"No - I would not let this judge gate a deployment yet. It misses "
                   f"{len(checks) - passed} of my {len(checks)} criteria ({failed}).")
    needed = [
        "A larger labeled set (100+ drafts) with enough 1-2 and 4-5 labels to test both ends "
        "of the scale.",
        "A second human labeler and the human-human agreement, to know the ceiling the judge "
        "can reach.",
        "Agreement on the gate decision itself (e.g. score >= 4 passes): false-pass and "
        "false-block rates, not only rank correlation.",
        "Repeatability across days, after an Ollama/model update, and with a second judge "
        "model.",
        "A check that the judge catches factual errors against s2837_rel (wrong score, status "
        "or date), since those are the costly mistakes in this domain.",
    ]
    return {"verdict": verdict, "checks": checks, "needed": needed,
            "criteria_passed": passed, "criteria_total": len(checks)}


def latency_reading(latency):
    if not latency or not latency.get("dominant"):
        return ["The stage-latency experiment has not been run yet."]
    dom = latency["dominant"]
    hit = latency.get("cache_hit_latency") or {}
    out = [f"Over {latency['confirmed_misses']} confirmed cache misses the dominant "
           f"contributor is {dom['stage']} with {dom['pct_of_end_to_end']}% of the cache-miss "
           f"end-to-end latency (p50 {dom['p50_ms']} ms, p95 {dom['p95_ms']} ms)."]
    advice = {
        "Evaluation": "Optimize the evaluation first: it is off the user's critical path, so "
                      "run it asynchronously (or sample requests), use one judge call that "
                      "returns all criteria, skip the draft re-judgment when the final text "
                      "is identical, or use a smaller judge model.",
        "Writer": "Optimize the Writer first: its local model call generates the long answer. "
                  "Cap the output tokens, keep the model loaded (keep_alive), use a faster or "
                  "quantized model, and raise the semantic-cache hit rate so fewer requests "
                  "reach it.",
        "Planner": "Optimize the Planner first: shorten or drop the planning call for simple "
                   "look-up questions (the facts are already in the prompt), or merge planning "
                   "into the Writer prompt.",
        "Reviewer": "Optimize the Reviewer first - unexpected for a rule-based stage; check "
                    "the produce/commit path of that agent.",
        "Queue wait (total)": "Optimize queue wait first: lower consumer poll intervals and "
                              "add consumers/partitions so messages are not waiting behind "
                              "busy agents.",
        "Cache lookup": "Optimize the cache lookup first: batch or cache the embedding and "
                        "use an HNSW index instead of FLAT.",
    }
    out.append(advice.get(dom["stage"], ""))
    if hit.get("n"):
        out.append(f"Cache hits are reported separately: p50 {hit['p50_ms']} ms, p95 "
                   f"{hit['p95_ms']} ms over {hit['n']} hit request(s).")
    return [x for x in out if x]

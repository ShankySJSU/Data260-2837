"""Build the HW10 report from the measured raw files.

    cd code
    python -m web_application.hw10.make_hw10_report

Writes reports/hw10/METRICS.md and reports/hw10/Ranjan_HW10_For_PDF.docx. Every number comes
from reports/hw10 (raw/*.json, judge_scores.csv, spans.jsonl); nothing is typed in by hand.
Formatting: main headings 14 pt bold, subheadings 12 pt bold, body 11 pt. Screenshot slots
are labeled "Figure N" - paste the screenshot above each caption in Word, then export to PDF
(limit: 35 pages).
"""

import json
import sys

from . import config as cfg
from . import insights, tracing
from .common import load_raw, log

COMPONENT = "REPORT"
SID = "018322837"


class Doc:
    def __init__(self):
        self.blocks = []
        self.figures = 0

    def h1(self, text):
        self.blocks.append(("h1", text))

    def h2(self, text):
        self.blocks.append(("h2", text))

    def p(self, text):
        if text:
            self.blocks.append(("p", str(text)))

    def bullets(self, items):
        self.blocks.append(("bullets", [str(i) for i in items if i]))

    def table(self, headers, rows):
        self.blocks.append(("table", headers, [["" if c is None else str(c) for c in r]
                                               for r in rows]))

    def code(self, text):
        self.blocks.append(("code", text.rstrip()))

    def shot(self, caption):
        self.figures += 1
        self.blocks.append(("shot", f"Figure {self.figures}: {caption}"))

    # ---- markdown ----
    def markdown(self):
        out = []
        for block in self.blocks:
            kind = block[0]
            if kind == "h1":
                out.append(f"\n## {block[1]}\n")
            elif kind == "h2":
                out.append(f"\n### {block[1]}\n")
            elif kind == "p":
                out.append(block[1] + "\n")
            elif kind == "bullets":
                out.extend(f"- {i}" for i in block[1])
                out.append("")
            elif kind == "table":
                out.append("| " + " | ".join(block[1]) + " |")
                out.append("|" + "---|" * len(block[1]))
                out.extend("| " + " | ".join(c.replace("|", "/").replace("\n", " ")
                                             for c in row) + " |" for row in block[2])
                out.append("")
            elif kind == "code":
                out.append("```\n" + block[1] + "\n```\n")
            elif kind == "shot":
                out.append(f"[screenshot] {block[1]}\n")
        return "\n".join(out)

    # ---- docx ----
    def docx(self, path):
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt, RGBColor

        doc = Document()
        for section in doc.sections:
            section.left_margin = section.right_margin = Inches(0.9)
            section.top_margin = section.bottom_margin = Inches(0.8)
        black = RGBColor(0, 0, 0)

        def style(name, size, bold, before, after):
            st = doc.styles[name]
            st.font.name = "Calibri"
            st.font.size = Pt(size)
            st.font.bold = bold
            st.font.color.rgb = black
            st.paragraph_format.space_before = Pt(before)
            st.paragraph_format.space_after = Pt(after)
            return st

        style("Normal", 11, False, 0, 6)
        style("Heading 1", 14, True, 12, 6)   # main headings: 14 pt bold
        style("Heading 2", 12, True, 10, 4)   # subheadings: 12 pt bold
        style("List Bullet", 11, False, 0, 3)

        for block in self.blocks:
            kind = block[0]
            if kind == "h1":
                doc.add_heading(block[1], level=1)
            elif kind == "h2":
                doc.add_heading(block[1], level=2)
            elif kind == "p":
                doc.add_paragraph(block[1])
            elif kind == "bullets":
                for item in block[1]:
                    doc.add_paragraph(item, style="List Bullet")
            elif kind == "table":
                table = doc.add_table(rows=1, cols=len(block[1]))
                table.style = "Table Grid"
                for cell, text in zip(table.rows[0].cells, block[1]):
                    cell.text = ""
                    run = cell.paragraphs[0].add_run(text)
                    run.bold = True
                    run.font.size = Pt(10)
                for row in block[2]:
                    cells = table.add_row().cells
                    for cell, text in zip(cells, row):
                        cell.text = ""
                        cell.paragraphs[0].add_run(text).font.size = Pt(10)
                for row in table.rows:
                    for cell in row.cells:
                        cell.paragraphs[0].paragraph_format.space_after = Pt(0)
                doc.add_paragraph()
            elif kind == "code":
                for line in block[1].splitlines():
                    para = doc.add_paragraph()
                    para.paragraph_format.space_after = Pt(0)
                    run = para.add_run(line or " ")
                    run.font.name = "Consolas"
                    run.font.size = Pt(8.5)
                doc.add_paragraph()
            elif kind == "shot":
                para = doc.add_paragraph()
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = para.add_run("[ paste screenshot here ]")
                run.italic = True
                run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
                cap = doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.add_run(block[1]).bold = True
        doc.save(path)


def short(text, limit=260):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "..."


def span_rows(row):
    return [[s["stage"], s["start_time"], s["end_time"], s["duration_ms"], s["status"],
             s["error"] or ""] for s in (row or {}).get("spans", [])]


def build():
    ev = load_raw(cfg.EVAL_RESULTS) or {}
    records = ev.get("records", [])
    part2 = [r for r in records if r.get("batch") == "part2"]
    judge = ev.get("judge") or {}
    p3 = load_raw(cfg.PART3_FILE)
    traces = load_raw(cfg.TRACES_FILE) or {}
    lat = load_raw(cfg.LATENCY_FILE)
    ver = None
    if (cfg.REPORT_DIR / "verification.json").exists():
        ver = json.loads((cfg.REPORT_DIR / "verification.json").read_text(encoding="utf-8"))
    na = "not run yet"

    d = Doc()
    d.h1("DATA 260 - Homework 10 Report")
    d.p(f"Student ID: {SID}        Name: {cfg.STUDENT_NAME}")
    d.h1("Section 0 - Personal Configuration and Domain")
    d.table(["Name", "Definition", "Value"], [
        ["SID", "Student ID", SID], ["SID4", "Last 4 of Student ID", cfg.SID4],
        ["PORT_BASE", "8000 + SID mod 900", f"{cfg.PORT_BASE} (dashboard on "
                                            f"{cfg.DASHBOARD_PORT})"],
        ["prefix", '"s" + SID4', cfg.PREFIX], ["Seed", "SID4", cfg.SEED],
        ["verify sid", "260000 + SID4", 260000 + cfg.SID4],
        ["DOMAIN_ID", "SID4 MOD 8", cfg.SID4 % 8],
        ["Assigned Domain", "Assignment domain", "Local restaurant inspections"]])
    d.p("Repository: https://github.com/ShankySJSU/Data260-2837")
    d.p("Submission Tag: hw10        Tagged commit hash (hw10): <paste output of "
        "git rev-parse HEAD>")
    d.p("Hardware: Local Windows PC, Python 3.12, VS Code Desktop, i7 CPU, 16GB RAM.")
    d.p(f"Builds on: HW8 Kafka pipeline ({cfg.PREFIX}_inbox -> Planner -> {cfg.PREFIX}_tasks "
        f"-> Writer -> {cfg.PREFIX}_drafts -> Reviewer -> {cfg.PREFIX}_final; Planner and "
        "Writer use local Ollama qwen2.5:1.5b, temperature 0, seed 2837; the Reviewer is "
        "rule-based) and the HW9 Redis semantic cache (MiniLM embeddings, threshold 0.85) in "
        "front of it. Database: MySQL s2837_rel.")
    d.p(f"Judge: GEval (DeepEval {judge.get('deepeval_version', '<version>')}) with the local "
        f"model {judge.get('model', 'ollama:' + cfg.JUDGE_MODEL)}, temperature "
        f"{cfg.JUDGE_TEMPERATURE}, seed {cfg.JUDGE_SEED}, thinking off, async_mode=False, "
        "explicit evaluation steps and a five-band rubric. No hosted model is used.")
    d.p("New HW10 code: code/web_application/hw10/ (tracing, traced_qa, pipeline, judge, "
        "evaluator, run_part2, build_eval_cases, label_cases, run_part3, run_part4, dashboard, "
        "verify_hw10) and span instrumentation in kafka_pipeline/agent_base.py.")

    # ------------------------------------------------------------------ Part 1
    d.h1("Part 1 - Streamlit operations dashboard")
    d.p("The dashboard (code/web_application/hw10/dashboard.py, port "
        f"{cfg.DASHBOARD_PORT}) is a read-only operations and evidence view of the existing "
        "system. It reads the span file written by the request path and the agents, the "
        "evaluation and validation result files, and the HW9 Redis counters.")
    d.h2("1.1 Summary page")
    d.p("Shows the request count, the semantic-cache hit rate with cache hits and cache "
        "misses as separate numbers, the error rate, and end-to-end latency (cache-miss and "
        "cache-hit p50/p95 kept apart). Under every metric the page states the time window "
        "(selectable: 15 minutes to all time, with the UTC bounds) and the data source.")
    d.table(["Metric", "Data source", "Time window"], [
        ["Recent requests", "spans.jsonl, root span (stage = request)", "selected window"],
        ["Cache hit rate, hits, misses", "spans.jsonl, cache_lookup spans (attrs.cache_hit)",
         "selected window"],
        ["Error rate", "spans.jsonl, spans with status = error", "selected window"],
        ["End-to-end latency", "spans.jsonl, duration of the root request span",
         "selected window"],
        ["Lifetime hits / misses", f"Redis hash {cfg.PREFIX}:semcache:stats",
         "since last cache flush"],
        ["Stage latency table", "raw/part4_latency.json (computed from spans)",
         "the 50-request experiment"]])
    d.p("Caching: @st.cache_resource holds the one reusable Redis connection; @st.cache_data "
        "caches the parsed span file and result files, keyed on file modification time and "
        "size so they are re-read only when they change.")
    d.shot("Summary page - request count, hit rate with hits vs misses, error rate, latency, "
           "each with window and source")
    d.h2("1.2 Evaluation page")
    d.p("Shows the Part 2 scores by pipeline stage (Planner, Writer, Reviewer) and by case "
        "(trace_id), the case detail with reasons, the Part 3 judge validation (Spearman, mean "
        "absolute difference, repeatability, raw per-case table) and the interpretation.")
    d.shot("Evaluation page - scores by stage and case, coordination interpretation")
    d.shot("Evaluation page - judge validation: Spearman, mean absolute difference, "
           "repeatability")
    d.h2("1.3 Trace lookup page")
    d.p("A trace_id input shows the request journey in stage order with start time, end "
        "time, duration, status and error for each stage. A cache hit shows a green CACHE HIT "
        "banner and only the cache_lookup stage; a cache miss shows the CACHE MISS banner and "
        "the full Kafka path; a failure shows the failing stage and its error.")
    d.shot("Trace lookup - cache-miss trace in stage order")
    d.shot("Trace lookup - cache-hit trace")
    d.shot("Trace lookup - failed trace with failing stage and error")

    # ------------------------------------------------------------------ Part 2
    d.h1("Part 2 - Automated evaluation of the Kafka pipeline")
    d.h2("2.1 Evaluation inputs and linkage")
    d.p(f"After a test question has gone through the pipeline, the evaluator reads "
        f"{cfg.PREFIX}_tasks (plan), {cfg.PREFIX}_drafts (draft) and {cfg.PREFIX}_final "
        "(final answer) with a group-less Kafka consumer and joins the three messages on "
        "correlation_id. The original message values are stored with topic, partition, offset "
        "and timestamp in raw/eval_results.json, together with the judge settings, so an "
        "evaluation can be reproduced.")
    d.p("Bounds: the Kafka read stops at the end offsets captured at start or after "
        f"{cfg.EVAL_COLLECT_TIMEOUT_S:.0f} s; messages that are not JSON objects are counted "
        "and skipped; a missing or malformed plan/draft/final gives that criterion the status "
        "missing_input instead of blocking. Each Ollama call has a "
        f"{cfg.JUDGE_CALL_TIMEOUT_S:.0f} s HTTP timeout, each GEval measurement a "
        f"{cfg.JUDGE_HARD_TIMEOUT_S:.0f} s wall-clock limit, and after "
        f"{cfg.JUDGE_MAX_CONSECUTIVE_FAILURES} consecutive failures the judge is marked "
        "unavailable and the remaining judgments are skipped.")
    d.code('''found, stats = self.source.fetch([trace_id], start_offsets=start_offsets)  # bounded
messages = found.get(trace_id, {})          # {"plan":..., "draft":..., "final":...}
record["inputs"] = messages                 # original messages + topic/partition/offset
plan   = judge("plan_quality", plan_text(data["steps"]))
writer = judge("writer_helpfulness", data["draft"])
final  = judge("final_helpfulness", data["final"])
draft_same_metric = judge("final_helpfulness", data["draft"])   # baseline for improvement''')
    d.h2("2.2 Evaluation criteria and results")
    d.p("Scale for every criterion and for the human labels: 1 very poor, 2 poor, 3 "
        "acceptable, 4 good, 5 excellent. GEval scores 0-10 internally; the rubric defines "
        "five bands (0-2, 3-4, 5-6, 7-8, 9-10) that map to 1-5. For Final-vs-Draft Improvement "
        "the draft and the final answer are both scored with the same Final Answer Helpfulness "
        "metric so the two scores are comparable.")
    if part2:
        d.table(["Case (trace_id)", "Question", "Plan Quality", "Writer Helpfulness",
                 "Final Answer Helpfulness", "Draft (final metric)", "Final - draft"],
                [[r["trace_id"], short(r.get("query"), 90),
                  r["criteria"]["plan_quality"]["score"],
                  r["criteria"]["writer_helpfulness"]["score"],
                  r["criteria"]["final_helpfulness"]["score"],
                  r["criteria"]["improvement"]["draft_score"],
                  r["criteria"]["improvement"]["difference"]] for r in part2])
        first = part2[0]
        c = first["criteria"]
        d.p(f"Detail for trace_id {first['trace_id']}:")
        d.table(["Criterion", "Saved fields"], [
            ["Plan Quality", f"score {c['plan_quality']['score']}; reason: "
                             f"{short(c['plan_quality']['reason'])}"],
            ["Writer Helpfulness", f"score {c['writer_helpfulness']['score']}; trace_id "
                                   f"{c['writer_helpfulness']['trace_id']}"],
            ["Final Answer Helpfulness", f"score {c['final_helpfulness']['score']}; final "
                                         f"answer: {short(c['final_helpfulness']['final_answer'])}"],
            ["Final-vs-Draft Improvement",
             f"draft {c['improvement']['draft_score']}, final {c['improvement']['final_score']}"
             f", difference {c['improvement']['difference']}. "
             f"{c['improvement']['interpretation']}"]])
        d.h2("What the scores indicate about coordination")
        for sentence in insights.coordination_reading(part2):
            d.p(sentence)
        if len(records) > len(part2):
            m = insights.stage_means(records)
            d.p(f"The same evaluator also scored the Part 4 requests; over all {m['n']} "
                f"evaluated requests the means are Plan Quality {m['plan_quality']}, Writer "
                f"Helpfulness {m['writer_helpfulness']}, Final Answer Helpfulness "
                f"{m['final_helpfulness']}, final minus draft {m['difference']}.")
    else:
        d.p(f"Evaluation results: {na} (python -m web_application.hw10.run_part2).")
    d.shot("run_part2 console output - evaluator scores for the end-to-end test questions")

    # ------------------------------------------------------------------ Part 3
    d.h1("Part 3 - Validate the judge")
    d.h2("3.1 Frozen evaluation cases")
    d.p("reports/hw10/eval_cases.json holds 20 Writer drafts produced by my pipeline for 20 "
        "restaurant-inspection questions (look-ups, date arithmetic, policy boundaries, "
        "comparisons, advice, and questions the database cannot answer). "
        "reports/hw10/human_labels.csv holds my hand-assigned 1-5 helpfulness label for each "
        "draft. I labeled them myself with label_cases.py, which shows only the question, "
        "the facts and the draft and never calls a model. Both files were committed before "
        "any judge score existed; run_part3.py refuses to start otherwise and records the "
        "commit and SHA-256 of both files, and verify_hw10.py checks they are unchanged.")
    if p3:
        d.table(["File", "Commit", "Committed at", "SHA-256 (first 16)"],
                [[name, str(f.get("commit"))[:12], f.get("committed_at"),
                  str(f.get("sha256"))[:16]] for name, f in p3["frozen_files"].items()])
    d.shot("git log showing eval_cases.json and human_labels.csv committed before the judge "
           "run")
    d.h2("3.2 Judge scores vs human labels")
    if p3:
        rep = p3["repeatability"]
        d.table(["Statistic", "Value"], [
            ["Drafts", p3["n_cases"]],
            ["Spearman rank correlation (human vs judge run 1)",
             p3["spearman"] if p3["spearman"] is not None else "undefined"],
            ["Mean absolute difference (human vs judge run 1)", p3["mean_abs_difference"]],
            ["Human label distribution (1..5)", p3["human_distribution"]],
            ["Judge score distribution run 1 (1..5)", p3["judge_distribution_run1"]],
            ["Failed judge calls (of 60)", p3["judge_failures"]]])
        if p3.get("spearman_note"):
            d.p(p3["spearman_note"])
        d.p("Raw per-case data (also in reports/hw10/judge_scores.csv), from which the "
            "statistics can be recomputed:")
        d.table(["Case", "Human", "Judge run 1", "Judge run 2", "Judge run 3",
                 "|human - run 1|", "Range across runs"],
                [[r["case_id"], r["human_label"], r["judge_run1"], r["judge_run2"],
                  r["judge_run3"], r["abs_diff_run1"], r["range_across_runs"]]
                 for r in p3["per_case"]])
        d.h2("3.3 Repeatability")
        d.p("The judge ran three times on the same 20 drafts with identical inputs and "
            f"settings ({p3['judge'].get('model')}, temperature "
            f"{p3['judge'].get('temperature')}, seed {p3['judge'].get('seed')}).")
        d.table(["Measure", "Value"], [
            ["Drafts whose score changed in at least one run",
             f"{rep['cases_with_any_change']} of {rep['cases_comparable']} "
             f"({rep['change_rate_pct']}%)"],
            ["Pairwise comparisons that differ",
             f"{rep['pairwise_changes']} of {rep['pairwise_comparisons']}"],
            ["Mean absolute change (all pairwise comparisons)", rep["mean_abs_change"]],
            ["Mean absolute change when a score changed", rep["mean_abs_change_when_changed"]],
            ["Maximum absolute change", rep["max_abs_change"]]])
        d.table(["Runs", "Changed", "Mean abs change", "Max abs change"],
                [[x["runs"], f"{x['changed']} of {x['n']}",
                  round(x["mean_abs_change"], 3) if x["mean_abs_change"] is not None else "",
                  x["max_abs_change"]] for x in rep["by_run_pair"]])
        d.table(["Run", "Spearman vs human", "Mean abs difference vs human"],
                [[x["run"], x["spearman"], x["mean_abs_difference"]]
                 for x in p3["comparison_by_run"]])
        trust = insights.judge_trust_reading(p3)
        d.h2("Would I trust this judge to gate a deployment?")
        d.p(trust["verdict"])
        d.table(["My criterion", "Measured", "Met"],
                [[c["check"], c["value"], "yes" if c["ok"] else "no"] for c in trust["checks"]])
        d.p("Additional evidence I would require first:")
        d.bullets(trust["needed"])
    else:
        d.p(f"Judge validation: {na} (python -m web_application.hw10.run_part3).")
    d.shot("run_part3 console output - per-case table, Spearman, mean absolute difference, "
           "repeatability")

    # ------------------------------------------------------------------ Part 4
    d.h1("Part 4 - Distributed tracing and latency analysis")
    d.h2("4.1 Trace propagation")
    d.p("The trace_id is created once at the Q&A ingress (traced_qa.py) and sent to Kafka as "
        "the HW8 correlation_id, so there is one identifier and nothing to join: the cache "
        "lookup, every message on inbox, tasks, drafts and final, the dead-letter record and "
        "the evaluator all carry the same value. Each stage appends one JSON line to "
        "reports/hw10/raw/spans.jsonl. The Kafka agents write their spans in the shared loop "
        "(agent_base.py): a queue-wait span from the producer timestamp of the input record "
        "to the moment the agent received it, and a stage span from receipt until the output "
        "was acknowledged; a dead-lettered message gives a stage span with status error.")
    d.table(["Stage", "What the span measures"], [
        ["cache_lookup", "embedding + Redis KNN + data-version check; attrs.cache_hit true / "
                         "false separates the hit and miss paths"],
        ["inbox / tasks / drafts / final", "queue wait on that topic (produced -> consumed)"],
        ["planner / writer / reviewer", "agent work (received -> output acknowledged)"],
        ["cache_store", "writing the new answer to the semantic cache"],
        ["evaluation", "the GEval judge calls for the trace"],
        ["request", "root span: what the caller waited for"]])
    spans = tracing.read_spans()
    example = next((s for s in spans if s["stage"] == "writer"), spans[0] if spans else None)
    if example:
        d.code(json.dumps({k: v for k, v in example.items() if not k.startswith("_")},
                          indent=1))
    d.h2("4.2 Trace examples")
    if traces:
        exp = traces.get("expectations", {})
        d.table(["Example", "trace_id", "Path", "Status", "Stages recorded"], [
            [label, (traces.get(key) or {}).get("trace_id"), (traces.get(key) or {}).get("path"),
             (traces.get(key) or {}).get("status"),
             " -> ".join(s["stage"] for s in (traces.get(key) or {}).get("spans", []))]
            for key, label in (("cache_hit", "Cache hit"),
                               ("cache_miss", "Cache miss (completed agent path)"),
                               ("failed", "Failed"))])
        d.p(f"Failed trace: the failing stage is {exp.get('failed_stage')} and the error is "
            f"\"{exp.get('failed_error')}\". The failure was triggered on purpose with a "
            f"fault flag on the request (inject_failure = "
            f"{traces.get('injected_failure_stage')}); the agent retried, dead-lettered the "
            f"message to {cfg.PREFIX}_dead_letter and the client reported the failing stage.")
        for key, label in (("cache_miss", "Cache-miss trace"), ("cache_hit", "Cache-hit trace"),
                           ("failed", "Failed trace")):
            d.p(f"{label} {(traces.get(key) or {}).get('trace_id')}:")
            d.table(["Stage", "Start time", "End time", "Duration (ms)", "Status", "Error"],
                    span_rows(traces.get(key)))
    else:
        d.p(f"Trace examples: {na} (python -m web_application.hw10.run_part4 traces).")
    d.h2("4.3 Stage-latency experiment")
    if lat and lat.get("table"):
        d.p(f"{lat['confirmed_misses']} requests, each a confirmed cache miss: every request "
            "did the real semantic-cache lookup and returned is_cached = False (highest "
            f"nearest-neighbour similarity {lat.get('max_nearest_similarity')}, threshold "
            f"{lat.get('threshold')}). Experiment answers were not stored in the cache, so no "
            f"request could be served by an earlier one; {len(lat.get('excluded', []))} "
            "candidate(s) were excluded (cache hit or failure) and replaced. End-to-end is "
            "measured from the start of the cache lookup to the end of the evaluation; the "
            "share column is the sum of the stage over all requests divided by the sum of "
            "end-to-end.")
        d.table(["Stage", "p50 (ms)", "p95 (ms)", "% of cache-miss end-to-end"],
                [[r["stage"], r["p50_ms"], r["p95_ms"], r["pct_of_end_to_end"]]
                 for r in lat["table"]])
        hit = lat.get("cache_hit_latency") or {}
        d.p(f"Cache-hit latency (separate metric, not part of the table): p50 "
            f"{hit.get('p50_ms')} ms, p95 {hit.get('p95_ms')} ms over {hit.get('n')} cache-hit "
            "request(s).")
        for sentence in insights.latency_reading(lat):
            d.p(sentence)
    else:
        d.p(f"Stage latency: {na} (python -m web_application.hw10.run_part4 latency).")
    d.shot("run_part4 latency console output - stage latency table over 50 cache misses")
    d.shot("Planner, Writer and Reviewer consoles while a traced request is processed")

    # ------------------------------------------------------------------ closing
    d.h1("Verification")
    if ver:
        d.p(f"verify_hw10.py: {ver['passed']} of {ver['total']} checks passed "
            f"(reports/hw10/verification.json).")
        failed = [c for c in ver["checks"] if c["status"] != "PASS"]
        if failed:
            d.table(["Failed check", "Detail"], [[c["check"], short(c["detail"], 120)]
                                                 for c in failed])
    else:
        d.p(f"Verification: {na} (python -m web_application.hw10.verify_hw10).")
    d.h1("AI Use")
    ai = cfg.REPORT_DIR / "AI_USE.md"
    if ai.exists():
        for line in ai.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                d.p(line.strip())
    else:
        d.p("See reports/hw10/AI_USE.md.")
    return d


def main():
    d = build()
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md = cfg.REPORT_DIR / "METRICS.md"
    md.write_text(f"# HW10 METRICS - {cfg.STUDENT_NAME} (SID4 {cfg.SID4}, PREFIX {cfg.PREFIX})\n"
                  + d.markdown(), encoding="utf-8")
    log(COMPONENT, f"wrote {md}")
    try:
        path = cfg.REPORT_DIR / "Ranjan_HW10_For_PDF.docx"
        d.docx(path)
        log(COMPONENT, f"wrote {path} ({d.figures} screenshot slots)")
    except ImportError:
        log(COMPONENT, "python-docx is not installed - only METRICS.md was written")
    return 0


if __name__ == "__main__":
    sys.exit(main())

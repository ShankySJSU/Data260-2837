"""Build reports/hw09/METRICS.md and reports/hw09/Ranjan_HW9_For_PDF.docx from raw/*.json.

    cd code
    python -m web_application.hw9.make_hw09_report

Formatting follows the assignment: main headings 14 pt bold, subheadings 12 pt bold, body 11 pt.
Yellow [SCREENSHOT ...] lines mark where to paste terminal screenshots (name visible).
"""

import inspect
import json
import sys

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt

from . import hw09_config as cfg
from .agent import evaluator_agent, system
from .util import load_json, load_raw

doc = Document()
_style = doc.styles["Normal"]
_style.font.name = "Calibri"
_style.font.size = Pt(11)
MD = []


def h1(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.font.size = True, Pt(14)
    MD.append(f"\n## {text}\n")


def h2(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.font.size = True, Pt(12)
    MD.append(f"\n### {text}\n")


def para(text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(11)
    MD.append(text + "\n")


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(text).font.size = Pt(11)
    MD.append(f"- {text}")


def shot(text):
    p = doc.add_paragraph()
    r = p.add_run(f"[SCREENSHOT - {text}]")
    r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    r.font.size = Pt(11)


def code(text, max_lines=40):
    lines = text.rstrip().splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["    # ... (see repository for the rest)"]
    p = doc.add_paragraph()
    r = p.add_run("\n".join(lines))
    r.font.name, r.font.size = "Consolas", Pt(8.5)
    MD.append("```\n" + "\n".join(lines) + "\n```")


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(str(h))
        run.bold, run.font.size = True, Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            cells[i].paragraphs[0].add_run(str(v)).font.size = Pt(9.5)
    doc.add_paragraph()
    MD.append("| " + " | ".join(map(str, headers)) + " |")
    MD.append("|" + "---|" * len(headers))
    for row in rows:
        MD.append("| " + " | ".join(str(v).replace("\n", " ") for v in row) + " |")
    MD.append("")


def src(obj):
    return inspect.getsource(obj)


def short(text, n=260):
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[:n] + "..."


def main():
    p1 = load_raw("part1_counter.json") or {}
    p2 = load_raw("part2_results.json") or {}
    sw = load_raw("part3_sweep.json") or {}
    st = load_raw("part3_stale.json") or {}
    tr = load_raw("part4_training.json") or {}
    va = load_raw("part4_validation.json") or {}
    te = load_raw("part4_test.json") or {}
    de = load_raw("part4_demo.json") or {}
    lessons = load_json(cfg.LESSONS_FILE)
    ver = {}
    if (cfg.REPORT_DIR / "verification.json").exists():
        ver = json.loads((cfg.REPORT_DIR / "verification.json").read_text(encoding="utf-8"))

    # ---------------- header / Section 0 ----------------
    h1("DATA 260 – Homework 9 Report")
    para("Student ID: 018322837                                        Name: Shashank Ranjan",
         bold=True)
    h1("Section 0 – Personal Configuration and Domain")
    table(["Name", "Definition", "Value"], [
        ["SID", "Student ID", "018322837"], ["SID4", "Last 4 of Student ID", "2837"],
        ["PORT_BASE", "8000 + SID mod 900", "8137 (HW9 API on 8138)"],
        ["prefix", '"s" + SID4', "s2837"], ["Seed", "SID4", "2837"],
        ["verify sid", "260000 + SID4", "262837"], ["DOMAIN_ID", "SID4 MOD 8", "5"],
        ["Assigned Domain", "Assignment domain", "Local restaurant inspections"]])
    para("Repository: https://github.com/ShankySJSU/Data260-2837")
    para("Submission Tag: hw9   Tagged commit hash (hw9): <paste output of git rev-parse HEAD>")
    para("Builds on HW8: the semantic cache sits in front of the HW8 Kafka Planner -> Writer -> "
         "Reviewer pipeline (local Ollama qwen2.5:1.5b through the HW1 adapter, temperature 0, "
         "seed 2837). Database: MySQL s2837_rel. Cache: Redis Stack (container s2837-redis). "
         "Embeddings: sentence-transformers/all-MiniLM-L6-v2 (384-d).")
    para("Hardware: Local Windows PC, Python 3.12, VS Code Desktop, i7 CPU, 16GB RAM.")
    para("New HW9 code: code/web_application/hw9/ (view_counter, semantic_cache, qa_service, "
         "agent_backend, run_part2, run_part3, cache_cases.yaml, agents/ for Part 4), "
         "hw9_main.py, docker-compose redis service.")
    shot("VS Code explorer with hw9/ folder and reports/hw09/ boxed")
    shot("docker compose up -d redis  +  docker ps showing s2837-redis, s2837-kafka")

    # ---------------- Part 1 ----------------
    h1("Part 1 – Redis View Counter")
    para("Every access to an inspection calls increment_inspection_views(inspection_id) on my "
         "InspectionStore (database + cache class). Redis INCR on "
         "s2837:views:inspection:<id> counts the view; every 10th increment writes the count to "
         "s2837_rel.restaurant_inspection.view_count (column added by HW9).")
    
    from . import view_hw09_counter as view_counter
    code(src(view_counter.InspectionStore.increment_inspection_views))
    if p1:
        out = ["=== Testing Counter ==="]
        for a in p1["accesses"]:
            out.append(f"Access #{a['access']}: Total = {a['total']}")
            if a["total"] % cfg.SYNC_EVERY == 0:
                out.append("✓ Synced views to database")
        code("\n".join(out), 40)
        table(["Measure", "Value"], [
            ["Inspection", f"{p1['inspection_code']} (id {p1['inspection_id']})"],
            ["Redis key", p1["key"]], ["Final Redis count", p1["final_redis"]],
            ["view_count in s2837_rel (last sync)", p1["final_db"]],
            ["Avg ms per view, Redis INCR path", p1["avg_ms_redis_path"]],
            ["Avg ms per view if every view did a DB UPDATE", p1["avg_ms_db_update_per_view"]]])
    shot("python -m web_application.hw9.view_counter")
    shot("MySQL: SELECT inspection_code, view_count FROM restaurant_inspection WHERE "
         "inspection_code='S2837-H9-0001';  and redis-cli GET s2837:views:inspection:<id>")

    # ---------------- Part 2 ----------------
    h1("Part 2 – Semantic Response Cache")
    para("The cache is the ingress of my Q&A endpoint (QAService.handle, also POST /qa in "
         "hw9_main.py). Each query is embedded with MiniLM and a KNN-1 search runs on the Redis "
         f"vector index {cfg.CACHE_INDEX} (FLAT, COSINE, 384 dims) over hashes "
         f"{cfg.CACHE_ENTRY_PREFIX}<id> that store query, embedding, final answer and a "
         "data-version marker. Similarity = 1 - cosine distance; threshold 0.85.")
    bullet("Hit: return the stored final answer, is_cached=True, similarity, latency. The HW8 "
           "agents are not called.")
    bullet("Miss: ground the question with the s2837_rel rows it mentions, run the HW8 pipeline "
           "(s2837_inbox -> planner -> writer -> reviewer -> s2837_final), store the entry, "
           "return is_cached=False.")
    from . import qa_service as qa_service
    code(src(qa_service.QAService.handle), 60)
    if p2:
        s = p2["summary"]
        table(["#", "Kind", "is_cached", "Similarity", "Latency (ms)", "Query"],
              [[r["n"], r["kind"], r["is_cached"], f"{r['similarity']:.3f}", r["latency_ms"],
                r["query"]] for r in p2["rows"]])
        table(["Metric", "Measured"], [
            ["Queries", s["queries"]], ["Cache hit rate", f"{s['hit_rate_pct']}%"],
            ["Avg latency, cached", f"{s['avg_latency_cached_ms']} ms"],
            ["Avg latency, non-cached (agent run)", f"{s['avg_latency_uncached_ms']} ms"],
            ["Miss path", s["agent_mode"]], ["Threshold", s["threshold"]]])
        para("These are the latencies I measured on my machine; the non-cached time is dominated "
             "by the two local model calls in the HW8 pipeline, while a hit costs one embedding "
             "plus one Redis KNN query.")
    shot("planner.py / writer.py / reviewer.py running (4 terminals)")
    shot("python -m web_application.hw9.run_part2 - log lines with CACHE HIT/MISS and the table")

    # ---------------- Part 3 ----------------
    h1("Part 3 – Threshold Economics and Stale Answers")
    h2("3.1 Labeled test set")
    para("code/web_application/hw9/cache_cases.yaml has 40 domain queries: 10 exact duplicates, "
         "10 paraphrases (should hit), 10 superficially similar questions with different correct "
         "answers and 10 unrelated questions (should miss). The cache is warmed with the 30 "
         "cached_query entries; every query is looked up against all of them. The file was "
         "committed before the sweep and not relabeled (errata go to cache_cases_errata.md).")
    code("""- {id: S01, category: similar_different, expected: miss,
   cached_query: "What score did Bayside Sushi Bar get in its latest inspection?",
   query: "What score did Golden Crust Bakery get in its latest inspection?",
   why_different: "different restaurant: 91 vs 83"}
- {id: P03, category: paraphrase, expected: hit,
   cached_query: "When is Spicy Pho House's re-inspection deadline?",
   query: "By what date does Spicy Pho House have to be inspected again?"}""")
    if sw:
        h2("3.2 Threshold sweep")
        para("Hit rate = hits / 40. False-hit rate = false hits / 40 (a hit on a should-miss "
             "query, or a paraphrase hitting the wrong entry). Mean latency over the 40 queries: "
             "hits use the measured lookup time, misses add the measured agent time for that "
             "query (each query answered once by the HW8 agents and reused across thresholds).")
        table(["Threshold", "Hit rate", "False-hit rate", "Mean latency (ms)", "Total cost"],
              [[f"{t['threshold']:.2f}", f"{t['hit_rate_pct']}%", f"{t['false_hit_rate_pct']}%",
                t["mean_latency_ms"], f"${t['total_cost_usd']:.2f}"] for t in sw["table"]])
        table(["Category", "min sim", "mean sim", "max sim"],
              [[k, v["min"], v["mean"], v["max"]] for k, v in sw["similarity_by_category"].items()])
        fh = sw.get("false_hit_example")
        h2("3.3 One false hit in full")
        if fh:
            table(["Field", "Value"], [
                ["Threshold", fh["threshold"]], ["Case", f"{fh['case_id']} ({fh['category']})"],
                ["Cached query", fh["cached_query"]], ["Incoming query", fh["incoming_query"]],
                ["Similarity", fh["similarity"]],
                ["Cached answer returned", short(fh["cached_answer_returned"], 600)],
                ["Correct answer", short(fh["correct_answer"], 600)],
                ["Records involved", "; ".join(fh.get("facts_for_incoming") or []) or "-"]])
            para(f"Why the embedding confused them: the two questions share "
                 f"{len(fh['shared_words'])} words ({', '.join(fh['shared_words'][:12])}) and "
                 f"differ only in {', '.join(fh['differing_words'])} (word Jaccard "
                 f"{fh['word_jaccard']}). MiniLM mean-pools all token vectors, so the shared "
                 "question template dominates the sentence vector while the few tokens that "
                 "change the answer (a restaurant name, a status word or a number) move it only "
                 f"slightly. The cosine similarity therefore stays at {fh['similarity']}, above "
                 f"the threshold, although the correct answers differ ({fh.get('why_different')}).")
        h2("3.4 Cost model and threshold choice")
        cm = sw["cost_model"]
        table(["Outcome", "Cost", "Justification"], [
            ["Cache miss", f"${cm['miss_cost_usd']}", cm["justification"]["miss"]],
            ["False hit", f"${cm['false_hit_cost_usd']}", cm["justification"]["false_hit"]]])
        para("Total cost = misses x miss cost + false hits x false-hit cost, over the 40 queries "
             "(a correct hit costs ~0).")
        best = next(t for t in sw["table"] if t["threshold"] == sw["chosen_threshold"])
        para(f"Threshold to ship: {sw['chosen_threshold']:.2f}. It has the lowest total cost "
             f"(${best['total_cost_usd']:.2f}) with hit rate {best['hit_rate_pct']}% and "
             f"false-hit rate {best['false_hit_rate_pct']}%. Because one false hit costs as much "
             "as 100 misses, the cost curve is driven by false hits: lower thresholds buy a few "
             "extra paraphrase hits but pay for them with wrong restaurant facts.")
    shot("python -m web_application.hw9.run_part3 sweep - threshold table and false hit")
    if st:
        h2("3.5 Stale answers and invalidation")
        para(f"Query: \"{st['query']}\" depends on s2837_rel record {st['record']} (Taj Grill). "
             "When the answer is stored, the entry keeps deps = {inspection_code: version} read "
             "from s2837:dv:inspection:<code>. db.update_inspection() is the write path: it "
             "updates s2837_rel and INCRs that marker. On every hit the service compares the "
             "stored versions with the live ones; a mismatch deletes the entry and reruns the "
             "agents.")
        table(["Step", "is_cached", "Similarity", "s2837_rel now", "Answer (start)"],
              [[s["step"], s["is_cached"], s["similarity"], f"{s['db_status']} {s['db_score']}",
                short(s["answer"], 160)] for s in st["steps"]])
        para("Trade-off: the check costs one extra Redis MGET per hit and only reacts to writes "
             "that go through update_inspection (a direct SQL update would not bump the marker, "
             "so the 24 h TTL remains as a safety net). In exchange, invalidation is precise: "
             "only answers that used the changed record are dropped, and the rest of the cache "
             "keeps its hit rate. Answers about general rules have no deps and are never "
             "invalidated by record changes.")
        shot("python -m web_application.hw9.run_part3 stale (stale hit, then STALE -> "
             "invalidated -> fresh answer)")

    # ---------------- Part 4 ----------------
    h1("Part 4 – Self-Improving Multi-Agent System")
    para("Answering Agent: local Ollama qwen2.5:1.5b (HW1 adapter). It looks up the s2837_rel "
         "row of the restaurant named (restaurant, code, date, status, score, violations) and "
         "loads the lessons for the question type. Evaluator Agent: checks the answer against "
         "reference_data.json (ground truth incl. derived re-inspection dates and county score "
         "bands) and returns PASS/REVISE, a short explanation and correction feedback.")
    table(["File", "Content"], [
        ["reference_data.json", "10 restaurants/inspections + county rules (Evaluator only)"],
        ["training_data.json", "10 questions - used to create lessons"],
        ["validation_data.json", "10 questions - decides which lessons are kept"],
        ["test_data.json", "12 held-out questions - final evaluation only"],
        ["lessons.json", f"{len(lessons)} lessons with lesson_id, failure_pattern, correction, "
                         "created_at, use_count"]])
    code(src(system.TwoAgentSystem.run), 45)
    code(src(evaluator_agent.EvaluatorAgent.evaluate), 30)
    cr = (de or {}).get("controlled_revision")
    if cr:
        h2("4.1 Revision sequence (controlled test case)")
        a1, a2 = cr["attempts"][0], cr["attempts"][-1]
        table(["Field", "Value"], [
            ["Question", cr["question"]],
            ["Initial answer (intentionally incomplete)", a1["answer"]],
            ["Evaluator result", f"{a1['evaluation']['result']} - {a1['evaluation']['explanation']}"],
            ["Evaluator feedback", a1["evaluation"]["feedback"]],
            ["Revised answer", a2["answer"]],
            ["Final evaluation", f"{a2['evaluation']['result']} - {a2['evaluation']['explanation']}"],
            ["Number of attempts", cr["n_attempts"]], ["Final response", cr["final_answer"]]])
        shot("python -m web_application.hw9.agents.run_part4 demo")
    if de and de.get("lesson_reuse_row"):
        h2("4.2 Lesson saved and reused")
        lr = de["lesson_reuse"]
        lesson = next((x for x in lessons if x["lesson_id"] == lr["lesson_id"]), {})
        src_q = next((r for r in tr.get("rows", []) if r["id"] == lesson.get("source_question")),
                     {})
        row = de["lesson_reuse_row"]
        table(["Field", "Value"], [
            ["Lesson", f"{lesson.get('lesson_id')} ({lesson.get('failure_code')})"],
            ["Created after failed answer", f"{src_q.get('id')}: {src_q.get('question')}"],
            ["Failed initial answer", short(src_q.get("attempts", [{}])[0].get("answer"), 300)],
            ["failure_pattern", lesson.get("failure_pattern")],
            ["correction", lesson.get("correction")],
            ["Later question that loaded it", f"{row['id']}: {row['question']}"],
            ["Answer with lesson", short(row["final_answer"], 300)],
            ["Result", f"{row['final_result']} in {row['n_attempts']} attempt(s)"]])
        code(json.dumps({k: lesson.get(k) for k in ("lesson_id", "failure_pattern", "correction",
                                                    "created_at", "use_count")}, indent=1))
    if va:
        h2("4.3 Validation before keeping a lesson")
        rows = []
        for x in lessons:
            v = x.get("validation") or {}
            rows.append([x["lesson_id"], x["failure_code"], x.get("status"),
                         f"{v.get('summary_before', {}).get('correct')} -> "
                         f"{v.get('summary_after', {}).get('correct')}",
                         f"{v.get('first_try_pass_before')} -> {v.get('first_try_pass_after')}",
                         ", ".join(v.get("regressions") or []) or "none",
                         ", ".join(v.get("unsupported") or []) or "none"])
        table(["Lesson", "Code", "Decision", "Validation correct (before -> after)",
               "First-try passes", "Regressions", "Unsupported answers"], rows)
        para("Keep rule: failure cases improve or stay the same, previously correct answers stay "
             "correct, and questions about restaurants without a record get no unsupported "
             "answer. Lessons are tried one at a time on top of the already kept ones.")
    if te:
        h2("4.4 Four system variants on test_data.json")
        table(["Variant", "Correct answers", "Incorrect answers", "Average attempts",
               "Average latency (ms)"],
              [[t["variant"], t["correct"], t["incorrect"], t["avg_attempts"],
                t["avg_latency_ms"]] for t in te["table"]])
        shot("python -m web_application.hw9.agents.run_part4 test - results table")
    h2("4.5 Explanation")
    bullet("Agent communication: the orchestrator passes the question to the Answering Agent, "
           "sends {question, answer} to the Evaluator, and on REVISE returns {previous answer, "
           "feedback} to the Answering Agent.")
    bullet("Lesson reuse: a lesson is created when the Evaluator reports the same failure code "
           "on two training answers; before answering, the Answering Agent loads lessons whose "
           "applies_to matches the question type and adds their corrections to its system "
           "prompt (use_count increments).")
    bullet("Stopping condition: PASS or two answer attempts, whichever comes first.")
    bullet("Validation: each candidate lesson is tested on validation_data.json against the "
           "current kept set and kept only if it causes no regression; test_data.json is used "
           "once per variant at the end and never creates lessons.")
    bullet("Limitation: the Evaluator is a rule-based fact checker over reference_data.json, so "
           "it can only verify facts it knows how to find (scores, statuses, dates, violation "
           "keywords, score bands); a fluent answer with an extra unsupported detail outside "
           "these checks could still PASS. Also, because feedback contains the correct fact, "
           "Evaluator Repair mostly measures how well the model follows feedback.")

    # ---------------- verification + AI use ----------------
    if ver:
        h1("verification.json (make verify-hw09)")
        para(f"{ver['summary']['passed']} of {ver['summary']['total']} checks passed.")
        table(["Check", "Status"], [[c["check"], c["status"]] for c in ver["checks"]])
    h1("AI Use")
    p = doc.add_paragraph()
    r = p.add_run("[EDIT BEFORE SUBMITTING - describe in your own words] 1. What I used an AI "
                  "assistant for and what I did myself. 2. One AI-produced output that was wrong. "
                  "3. How I detected it. 4. What I changed and why it works now.")
    r.font.highlight_color = WD_COLOR_INDEX.YELLOW

    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = cfg.REPORT_DIR / "Ranjan_HW9_For_PDF.docx"
    doc.save(out)
    (cfg.REPORT_DIR / "METRICS.md").write_text(
        f"# HW9 METRICS - {cfg.STUDENT_NAME} (SID4 2837, PREFIX s2837)\n" + "\n".join(MD),
        encoding="utf-8")
    print(f"wrote {out}\nwrote {cfg.REPORT_DIR / 'METRICS.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

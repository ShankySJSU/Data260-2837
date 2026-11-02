"""Build reports/hw08/Ranjan_HW8_For_PDF.docx from the REAL run outputs.

Run after: homework_demo.py, send_question.py, run_hw08_failures.py all, verify_hw08.
    python -m web_application.make_hw08_report --hardware "Windows 11 PC, i7, 16 GB RAM"

Everything numeric/log-like is read from reports/hw08 (RUN_LOG.txt, raw/, verification.json).
Yellow "[SCREENSHOT ...]" paragraphs mark where to paste your terminal screenshots.
Formatting per the assignment: headings 14 pt bold, subheadings 12 pt bold, body 11 pt.
"""

import argparse
import ast
import json
import subprocess

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from web_application.kafka_pipeline import config as cfg

ROOT = cfg.REPO_ROOT
PKG = ROOT / "code" / "web_application" / "kafka_pipeline"
REPO_URL = "https://github.com/ShankySJSU/Data260-2837"


# ----------------------------------------------------------------------------
# docx helpers
# ----------------------------------------------------------------------------


class Report:
    def __init__(self):
        self.doc = Document()
        normal = self.doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        for section in self.doc.sections:
            section.left_margin = section.right_margin = Pt(54)
            section.top_margin = section.bottom_margin = Pt(54)

    def heading(self, text):
        p = self.doc.add_paragraph()
        run = p.add_run(text)
        run.bold, run.font.size = True, Pt(14)
        p.paragraph_format.space_before = Pt(12)

    def sub(self, text):
        p = self.doc.add_paragraph()
        run = p.add_run(text)
        run.bold, run.font.size = True, Pt(12)
        p.paragraph_format.space_before = Pt(8)

    def para(self, text, bold_prefix=None):
        p = self.doc.add_paragraph()
        if bold_prefix:
            p.add_run(bold_prefix).bold = True
        run = p.add_run(text)
        run.font.size = Pt(11)
        return p

    def bullets(self, items):
        for item in items:
            p = self.doc.add_paragraph(style="List Bullet")
            p.add_run(item).font.size = Pt(11)

    def code(self, text, size=8.5):
        for line in text.rstrip("\n").split("\n"):
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            run = p.add_run(line if line else " ")
            run.font.name = "Consolas"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
            run.font.size = Pt(size)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:val"), "clear")
            shade.set(qn("w:fill"), "F2F2F2")
            p._p.get_or_add_pPr().append(shade)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def screenshot(self, text):
        p = self.doc.add_paragraph()
        run = p.add_run(f"[SCREENSHOT - {text}]")
        run.bold = True
        run.font.color.rgb = RGBColor(0x9C, 0x00, 0x06)
        run.font.highlight_color = WD_COLOR_INDEX.YELLOW

    def table(self, header, rows, widths=None):
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        for i, h in enumerate(header):
            cell = t.rows[0].cells[i]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(h))
            run.bold, run.font.size = True, Pt(10)
        for row in rows:
            cells = t.add_row().cells
            for i, value in enumerate(row):
                cells[i].text = ""
                cells[i].paragraphs[0].add_run(str(value)).font.size = Pt(9.5)
        self.doc.add_paragraph()
        return t

    def save(self, path):
        self.doc.save(path)


# ----------------------------------------------------------------------------
# data helpers
# ----------------------------------------------------------------------------


def load(name, default=None):
    path = cfg.RAW_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def snippet(file, name, max_lines=40):
    source = (PKG / file).read_text(encoding="utf-8") if (PKG / file).exists() else \
        (ROOT / "code" / "web_application" / file).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            lines = ast.get_source_segment(source, node).split("\n")
            if len(lines) > max_lines:
                lines = lines[:max_lines] + ["    # ... (see repository for the rest)"]
            return f"# {file}\n" + "\n".join(lines)
    return f"# {file}: {name} not found"


def compact(line, width=170):
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 5:  # time | name | prefix | component | message
        line = f"{parts[0][11:]} {parts[3]:<11} {' | '.join(parts[4:])}"
    return line if len(line) <= width else line[:width - 3] + "..."


def run_log_lines(*needles, limit=40):
    if not cfg.RUN_LOG.exists():
        return []
    out = [ln for ln in cfg.RUN_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
           if any(n and n in ln for n in needles)]
    return out[-limit:]


def excerpt_file(name, limit=18):
    path = cfg.RAW_DIR / name
    if not path.exists():
        return "(run run_hw08_failures.py to produce this log)"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return "\n".join(compact(ln) for ln in lines[:limit])


# ----------------------------------------------------------------------------
# sections
# ----------------------------------------------------------------------------


def front(r, args):
    tag_commit = git("rev-list", "-n", "1", "hw8") or "(tag hw8 not created yet)"
    head = git("rev-parse", "HEAD")
    verification = json.loads((cfg.REPORT_DIR / "verification.json").read_text()) if (
        cfg.REPORT_DIR / "verification.json").exists() else {}
    title = r.doc.add_paragraph()
    run = title.add_run("DATA 260 - Homework 8 Report")
    run.bold, run.font.size = True, Pt(16)
    r.para(f"Name: {cfg.STUDENT_NAME}    Student ID: 018322837")
    r.para(REPO_URL, bold_prefix="Repository: ")
    r.para("Sbnikitha, supriyaselvanganesan", bold_prefix="Collaborators with access: ")
    r.para(f"hw8 -> {tag_commit}", bold_prefix="Submission tag / commit: ")
    if verification:
        r.para(f"{verification.get('commit_hash')} "
               f"({verification.get('summary', {}).get('passed')}/"
               f"{verification.get('summary', {}).get('total')} checks passed)",
               bold_prefix="Commit verified by verify_hw08: ")
    r.para(head, bold_prefix="HEAD when this report was generated: ")
    r.para(args.hardware, bold_prefix="Hardware: ")
    r.para(args.model, bold_prefix="Local model: ")

    r.heading("Section 0 - Personal Configuration and Domain")
    r.table(["Value", "Definition", "My value"], [
        ["SID4", "Last four digits of SJSU ID", cfg.SID4],
        ["PORT_BASE", "8000 + (SID4 mod 900) = 8000 + 137", cfg.PORT_BASE],
        ["PREFIX", '"s" + SID4', cfg.PREFIX],
        ["SEED", "SID4", cfg.SEED],
        ["VERIFY_SEED", "260000 + SID4", cfg.VERIFY_SEED],
        ["DOMAIN_ID", "SID4 mod 8", f"{cfg.DOMAIN_ID} - {cfg.DOMAIN}"],
        ["Primary entity", "ENTITY in this homework", "Inspection (inspection_id)"],
    ])
    r.sub("New HW8 files (extension of the HW1-HW7 codebase, no separate copy)")
    r.code("""docker-compose.yml, Dockerfile.hw8, Makefile (verify-hw08), code/requirements_hw8.txt
code/web_application/hw8_main.py              FastAPI wrapper (port 8137) -> Kafka
code/web_application/verify_hw08.py           smoke test -> reports/hw08/verification.json
code/web_application/make_hw08_report.py      builds this report from the real run outputs
code/web_application/kafka_pipeline/
    config.py  kafka_io.py  idempotency.py  agent_base.py  llm.py  create_topics.py
    inspection_worker.py  request_client.py  homework_demo.py          (Part 1)
    planner.py  writer.py  reviewer.py  send_question.py               (Part 2)
    run_hw08_failures.py                                               (Part 3)
reports/hw08/  RUN_LOG.txt  raw/  METRICS.md  AI_USE.md  verification.json  Ranjan_HW8.pdf""")


def part1(r):
    demo = load("part1_sequence.json", {})
    errors = load("part1_error_cases.json", [])
    r.heading("Part 1 - Backend Service Request/Response over Kafka")
    r.para("The domain logic for my primary entity (Inspection) now runs in a separate worker "
           "process. The client / FastAPI wrapper and the worker communicate only through two "
           "Kafka topics; the worker keeps inspections in a plain Python dictionary and "
           "validates input with my existing InspectionCreate Pydantic schema.")
    r.sub("1.1 Topics and operations")
    r.table(["Topic", "Written by", "Read by", "Partitions"], [
        [cfg.REQUEST_TOPIC, "client / FastAPI (hw8_main.py)", "inspection_worker.py", 1],
        [cfg.RESPONSE_TOPIC, "inspection_worker.py (reply_to)", "client / FastAPI", 1],
    ])
    r.table(["Operation", "Input data", "Success output", "Error output"], [
        [cfg.OP_CREATE, "name, inspection_code, inspection_date, status, score, restaurant_id",
         '{"success": true, "inspection_id": "<uuid4>", "message": "Inspection created"}',
         '{"success": false, "error": "Invalid inspection data - ..."}'],
        [cfg.OP_GET, '{"inspection_id": "<uuid>"}', '{"success": true, "inspection": {...}}',
         '{"success": false, "error": "Inspection not found"}'],
        ["anything else", "-", "-", '{"success": false, "error": "Unknown operation"}'],
    ])
    r.sub("1.2 Request and response message schemas")
    create = demo.get("create", {})
    r.code("REQUEST  (" + cfg.REQUEST_TOPIC + ")\n" + json.dumps(create.get("request", {
        "correlation_id": "unique-id", "reply_to": cfg.RESPONSE_TOPIC,
        "operation": cfg.OP_CREATE, "data": {}}), indent=2) + "\n\nRESPONSE (" +
        cfg.RESPONSE_TOPIC + ")\n" + json.dumps(create.get("response", {}), indent=2))
    r.sub("1.3 correlation_id flow")
    r.bullets([
        "The client (KafkaRequestClient.request / homework_demo.py) creates the correlation_id "
        "once with uuid4 and puts it in the request together with reply_to, operation and data.",
        "FastAPI accepts an X-Correlation-ID header and forwards it unchanged (it only creates "
        "one when the caller did not).",
        "The worker never generates a new id: it copies correlation_id into every response, "
        "including error responses, and publishes to the reply_to topic.",
        "The client's background listener matches the response to the waiting request by "
        "correlation_id. A repeated correlation_id returns the stored reply (no second entity).",
    ])
    r.sub("1.4 Code - worker, client and API wrapper")
    r.code(snippet("inspection_worker.py", "process"))
    r.code(snippet("request_client.py", "request", 22))
    r.code(snippet("hw8_main.py", "create_inspection_kafka") + "\n\n" +
           snippet("hw8_main.py", "kafka_call"))
    r.sub("1.5 Required screenshots")
    r.screenshot("docker ps showing s2837-kafka, s2837-worker and s2837-api running (name visible)")
    r.screenshot("docker logs s2837-worker -> 'Consumer is ready and listening...'")
    r.screenshot("docker logs s2837-api -> 'FastAPI server started at http://127.0.0.1:8137'")
    r.screenshot("python homework_demo.py output: CREATE/GET requests, inspection_id, success, "
                 "correlation_id")
    r.sub("1.6 Full sequence CREATE_INSPECTION -> GET_INSPECTION (from raw/part1_sequence.json)")
    lines = []
    for event in demo.get("sequence", []):
        where = event.get("topic") or event.get("where") or ""
        part = f"[p{event['partition']}@{event['offset']}]" if "offset" in event else ""
        lines.append(f"{event['ts'][11:23]}  {event.get('operation', ''):<18} "
                     f"{event['event']:<15} {event['component']:<7} {where}{part} "
                     f"cid={event['correlation_id'][:8]}")
    r.code("\n".join(lines) or "(run homework_demo.py)")
    ids = [create.get("request", {}).get("correlation_id"),
           demo.get("get", {}).get("request", {}).get("correlation_id")]
    worker_lines = [compact(ln) for ln in run_log_lines(*[i for i in ids if i])
                    if "| WORKER" in ln or "| CLIENT" in ln or "| API" in ln]
    if worker_lines:
        r.para("Matching console lines from RUN_LOG.txt (client + worker):")
        r.code("\n".join(worker_lines[:16]))
    r.para(f"correlation_id preserved for both requests: "
           f"{demo.get('correlation_id_preserved')}", bold_prefix="Result: ")
    if errors:
        r.sub("1.7 Validation and error responses")
        r.table(["Case", "success", "error", "correlation_id preserved"], [
            [e["case"], e["response"].get("success"), e["response"].get("error"),
             e["response"].get("correlation_id") == e["request"]["correlation_id"]]
            for e in errors])


def part2(r):
    data = load("part2_final.json", {})
    final = data.get("final", {})
    r.heading("Part 2 - Three-Agent Kafka Pipeline")
    r.para("Planner, Writer and Reviewer run as separate Python processes. No agent imports or "
           "calls another one - each consumes one topic and produces to the next, and every "
           "message carries the same correlation_id plus a trace list (stage, agent, pid, "
           "topic/partition/offset, timestamps).")
    r.sub("2.1 Topics and workflow")
    r.table(["Sender", "Reads topic", "Sends message to"], [
        ["You (send_question.py)", "-", f"{cfg.INBOX_TOPIC} (a question)"],
        ["Planner (planner.py)", cfg.INBOX_TOPIC, f"{cfg.TASKS_TOPIC} (a plan, 2 partitions)"],
        ["Writer (writer.py)", cfg.TASKS_TOPIC, f"{cfg.DRAFTS_TOPIC} (a draft answer)"],
        ["Reviewer (reviewer.py)", cfg.DRAFTS_TOPIC, f"{cfg.FINAL_TOPIC} (approval)"],
    ])
    r.sub("2.2 Topic creation")
    r.code("\n".join(
        f"docker exec s2837-kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists "
        f"--topic {t} --partitions {n} --replication-factor 1 --bootstrap-server localhost:9092"
        for t, n in cfg.TOPICS.items()))
    r.screenshot("kafka-topics.sh --describe / --list showing the s2837_* topics "
                 "(s2837_tasks with PartitionCount: 2)")
    r.sub("2.3 Agent code")
    r.code(snippet("planner.py", "handle"))
    r.code(snippet("writer.py", "handle", 22))
    r.code(snippet("reviewer.py", "review"))
    r.sub("2.4 Running the agents (4 terminals)")
    r.screenshot("Terminal 1 python planner.py | Terminal 2 python writer.py | Terminal 3 python "
                 "reviewer.py | Terminal 4 python send_question.py (name visible)")
    r.sub("2.5 One complete message journey (inbox -> final)")
    cid = final.get("correlation_id")
    journey = [compact(ln) for ln in run_log_lines(cid) if any(
        k in ln for k in ("SENT", "RECEIVED", "PLAN", "DRAFT", "REVIEW", "COMMITTED"))]
    r.code("\n".join(journey[:22]) or "(run send_question.py)")
    stages = []
    for s in final.get("trace", []):
        stages.append([s["stage"], s["agent"], f"{s['topic']}[p{s['partition']}@{s['offset']}]",
                       s["received_at"][11:23], s["finished_at"][11:23]])
    if stages:
        r.table(["Stage", "Agent", "Read from", "Received", "Finished"], stages)
    r.sub("2.6 Final JSON from " + cfg.FINAL_TOPIC)
    shown = {k: final.get(k) for k in ("correlation_id", "status", "answer", "review",
                                       "writer") if k in final}
    r.code(json.dumps(shown, indent=2)[:3500] or "(run send_question.py)")
    r.sub("2.7 How Kafka helped the agents coordinate")
    r.para("Kafka acted as the only contract between the agents: each agent knows just its "
           "input topic, its output topic and the JSON shape, so I could start, stop or restart "
           "any agent independently and the messages waited in the topic instead of being lost. "
           "Consumer groups and committed offsets let every agent resume exactly where it "
           "stopped, the two-partition tasks topic lets me add a second Writer without code "
           "changes, and the correlation_id plus the trace inside each message gave me an "
           "end-to-end audit of one question across three processes. The cost is that the "
           "pipeline is asynchronous: send_question.py has to wait on s2837_final and match the "
           "correlation_id instead of getting a return value.")


def part3(r):
    res = load("part3_results.json", {})
    r.heading("Part 3 - Failure Behavior")
    r.para("All experiments are produced by run_hw08_failures.py, which starts the agents as "
           "separate processes with their own consumer groups and test_run tag, toggles the "
           "safety feature off (before) and on (after), and writes raw/part3_*.json|csv|txt. "
           "Agents use the deterministic writer template here so timing reflects Kafka, not "
           "the model.")

    r.sub("3.I Duplicate delivery - idempotency")
    r.code(snippet("agent_base.py", "_process_once", 32))
    dup = res.get("duplicate", {})
    if dup:
        r.table(["Run", "Deliveries", "Drafts produced", "Finals produced", "DUPLICATE skips"],
                [[m, d["deliveries_to_writer"], d["drafts_produced"], d["finals_produced"],
                  d["duplicate_skipped_logs"]] for m, d in dup.items()])
    r.para("Before fix (--no-idempotency):")
    r.code(excerpt_file("part3_duplicate_before_log.txt"))
    r.para("After fix (SQLite idempotency store keyed by correlation_id):")
    r.code(excerpt_file("part3_duplicate_after_log.txt"))

    r.sub("3.II Consumer death - commit offsets only after successful processing")
    r.code(snippet("agent_base.py", "_handle", 34))
    crash = res.get("crash", {})
    if crash:
        r.table(["Run", "commit mode", "msg offset", "committed at kill", "after restart",
                 "redelivered", "lost"],
                [[m, c["commit_mode"], f"p{c['message_partition']}@{c['message_offset']}",
                  c["committed_at_kill"], c["committed_after_restart"],
                  c["redelivered_after_restart"], c["message_lost"]] for m, c in crash.items()])
    r.para("Before fix (--commit-mode early, offset committed on receipt):")
    r.code(excerpt_file("part3_crash_before_log.txt"))
    r.para("After fix (commit after the draft is acked):")
    r.code(excerpt_file("part3_crash_after_log.txt"))
    r.screenshot("optional: kafka-consumer-groups.sh --describe --group <crash group> showing "
                 "CURRENT-OFFSET after the restart")

    r.sub(f"3.III Poison message - bounded retries and {cfg.DEAD_LETTER_TOPIC}")
    r.code(snippet("agent_base.py", "_dead_letter", 30))
    poison = res.get("poison", {})
    if poison:
        r.table(["Run", "Attempts", "Good msgs processed", "Dead-letter records"],
                [[m, p["poison_attempts"], f"{p['good_messages_processed']}/3",
                  p["dead_letter_records"]] for m, p in poison.items()])
        sample = poison.get("after", {}).get("dead_letter_sample")
        if sample:
            r.para(f"Record in {cfg.DEAD_LETTER_TOPIC}:")
            r.code(json.dumps(sample, indent=2))
    r.para("Before fix (--no-dlq, retries forever):")
    r.code(excerpt_file("part3_poison_before_log.txt", 14))
    r.para("After fix:")
    r.code(excerpt_file("part3_poison_after_log.txt"))

    r.sub("3.IV Ordering - 2 partitions, 2 Writers in one group, VERIFY_SEED messages")
    r.code(snippet("run_hw08_failures.py", "ordering_messages") + "\n\n# partition key:\n"
           "meta = send_json(producer, cfg.TASKS_TOPIC, body, key=msg['entity_id'])  # keyed run")
    order = res.get("ordering", {})
    for run in ("unkeyed", "keyed"):
        if run in order:
            r.para(f"Run - {run} ({'key = entity_id' if run == 'keyed' else 'no key'}):",
                   bold_prefix="")
            r.table(["Entity", "Processed seq order", "Partitions", "In order"],
                    [[e, s["processed_seq_order"], s["partitions"], s["in_order"]]
                     for e, s in order[run]["per_entity"].items()])
            r.code(excerpt_file(f"part3_ordering_{run}_log.txt", 24))

    r.sub("3.V Failure table")
    metrics = (cfg.REPORT_DIR / "METRICS.md").read_text(encoding="utf-8") if (
        cfg.REPORT_DIR / "METRICS.md").exists() else ""
    rows = [ln.strip("|").split("|") for ln in metrics.splitlines()
            if ln.startswith("| ") and ln.count("|") == 4 and "Failure scenario" not in ln]
    rows = [[c.strip() for c in row] for row in rows if len(row) == 3]
    r.table(["Failure scenario", "Before fix", "After fix"], rows or [["(run METRICS)", "", ""]])

    r.sub("3.VI Comparison with the HW2 in-process graph")
    r.para("In HW2 my LangGraph Planner -> Reviewer -> Supervisor graph ran as function calls in "
           "one Python process: each node returned its state directly to the next node.")
    r.para("Benefits gained by moving to Kafka:", bold_prefix="")
    r.bullets([
        "Independent scaling - a second Writer joined the same consumer group and took one of "
        "the two s2837_tasks partitions with no code change (Part 3.IV).",
        "Decoupled failure - when the Writer was killed, the Planner and Reviewer kept running "
        "and the unfinished task stayed in Kafka until the restarted Writer finished it "
        "(Part 3.II); in HW2 an exception in one node stopped the whole graph run.",
    ])
    r.para("New responsibilities I now handle myself:", bold_prefix="")
    r.bullets([
        "Duplicate delivery - Kafka is at-least-once, so the same correlation_id can arrive "
        "twice; I added an idempotency store and offset commits after success (Part 3.I/II).",
        "Ordering and poison messages - order is only guaranteed inside one partition, so I "
        "had to choose entity_id as the message key; and a bad message would block a "
        "partition forever, so I added bounded retries and s2837_dead_letter (Part 3.III/IV).",
    ])


def jmeter(r):
    path = cfg.RAW_DIR / "jmeter_summary.csv"
    if not path.exists():
        return
    import csv
    rows = list(csv.reader(path.open(encoding="utf-8")))
    r.heading("Optional - JMeter load test (direct endpoint vs Kafka endpoint)")
    r.para("100 threads, 10 s ramp-up, loop 1, against /inspections-direct and "
           "/inspections/kafka on port 8137 (JMeter Summary Report exported to "
           "raw/jmeter_summary.csv).")
    if rows:
        r.table(rows[0], rows[1:])
    r.screenshot("JMeter Summary Report / Aggregate Report")


def verification(r):
    path = cfg.REPORT_DIR / "verification.json"
    r.heading("verification.json (make verify-hw08)")
    if not path.exists():
        r.para("(run python -m web_application.verify_hw08)")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    r.para(f"HW {data['homework']}, SID4 {data['sid4']}, commit {data['commit_hash']}, "
           f"SEED {data['seed']}, VERIFY_SEED {data['verify_seed']}, model: {data['model']}")
    r.table(["Check", "Result"], [[c["check"], c["status"]] for c in data["checks"]])


def ai_use(r):
    path = cfg.REPORT_DIR / "AI_USE.md"
    r.heading("AI Use")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                r.para(line.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hardware", default="Local Windows PC, Python 3.12, VS Code, i7 CPU, "
                                              "16 GB RAM, Docker Desktop (Kafka 3.8 KRaft)")
    parser.add_argument("--model", default="Ollama qwen2.5:1.5b (temperature 0, seed 2837) for "
                                           "Planner/Writer in Part 2; deterministic template in "
                                           "Part 3 tests and the smoke test")
    parser.add_argument("--out", default=str(cfg.REPORT_DIR / "Ranjan_HW8_For_PDF.docx"))
    args = parser.parse_args()
    r = Report()
    front(r, args)
    part1(r)
    part2(r)
    part3(r)
    jmeter(r)
    verification(r)
    ai_use(r)
    r.save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

"""HW8 Part 3 - failure-behaviour experiments (before fix vs after fix).

Kafka must be running. STOP the Part 2 planner/writer/reviewer terminals first (the test
agents are started here as separate processes with their own consumer groups).

    python run_hw08_failures.py all            # duplicate, crash, poison, ordering
    python run_hw08_failures.py duplicate|crash|poison|ordering

Outputs (reports/hw08/): raw/part3_*.json|csv, raw/part3_*_log.txt, METRICS.md
"""

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # .../code

from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.kafka_io import (  # noqa: E402
    TopicReader, banner, group_committed, log, make_producer, new_id, now_iso, record_json,
    send_json, wait_for_kafka, ensure_topics,
)

COMPONENT = "RUNNER"
RUN = time.strftime("%Y%m%d%H%M%S")
RESULTS = {}


# ----------------------------------------------------------------------------
# child processes
# ----------------------------------------------------------------------------


class Agent:
    def __init__(self, script, instance, group, *flags, test_run):
        self.instance = instance
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        env.setdefault("HW8_LLM", "template")
        cmd = [sys.executable, str(HERE / script), "--instance", instance, "--group", group,
               "--offset-reset", "latest", "--test-run", test_run, *flags]
        log(COMPONENT, f"START {instance}: {' '.join(cmd[1:])}")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=env)
        self.lines = []
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            line = line.rstrip()
            self.lines.append(line)
            print("    " + line, flush=True)  # child already wrote it to RUN_LOG.txt

    def wait_for(self, text, timeout=60, start=0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for i, line in enumerate(self.lines[start:], start):
                if text in line:
                    return i, line
            if self.proc.poll() is not None:
                raise RuntimeError(f"{self.instance} exited: {self.lines[-5:]}")
            time.sleep(0.1)
        raise TimeoutError(f"{self.instance}: '{text}' not seen in {timeout}s")

    def latest_assignment(self):
        for line in reversed(self.lines):
            if "READY assigned partitions=" in line:
                inner = line.split("partitions=[", 1)[1].split("]", 1)[0]
                return [int(x) for x in inner.split(",") if x.strip()]
        return None

    def count(self, text):
        return sum(text in line for line in self.lines)

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(10)
        return self.proc.pid

    stop = kill


def wait_ready(*agents, partitions=None, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        sets = [a.latest_assignment() for a in agents]
        if all(s for s in sets):
            if partitions is None or sorted(p for s in sets for p in s) == partitions:
                time.sleep(1.0)  # one more poll cycle so positions are resolved
                return sets
        time.sleep(0.2)
    raise TimeoutError(f"agents not ready: {[a.latest_assignment() for a in agents]}")


def matching(records, predicate, test_run=None):
    out = [m for m in (record_json(r) for r in records) if predicate(m)]
    return [m for m in out if test_run is None or m.get("test_run") == test_run]


def excerpt(name, agents, keywords):
    lines = []
    for agent in agents:
        lines += [ln for ln in agent.lines if any(k in ln for k in keywords)]
    lines.sort()
    path = cfg.RAW_DIR / f"part3_{name}_log.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def task(test_run, question="How should a restaurant fix a WARNING inspection?", **extra):
    return {"correlation_id": new_id(), "test_run": test_run, "kind": "answer_task",
            "question": question,
            "plan": {"steps": ["Explain the WARNING status", "List corrective actions",
                               "Verify fixes before re-inspection"], "model": "runner"},
            **extra}


# ----------------------------------------------------------------------------
# I. duplicate delivery
# ----------------------------------------------------------------------------


def test_duplicate(producer):
    banner(COMPONENT, "PART 3.I  DUPLICATE DELIVERY - replay the same correlation_id")
    rows = {}
    for mode in ("before", "after"):
        test_run = f"dup-{mode}-{RUN}"
        flags = ["--no-idempotency"] if mode == "before" else []
        state = cfg.STATE_DIR / f"{test_run}.sqlite"
        writer = Agent("writer.py", f"writer-dup-{mode}", f"{cfg.PREFIX}_dup_w_{mode}_{RUN}",
                       *flags, "--state-file", str(state), test_run=test_run)
        reviewer = Agent("reviewer.py", f"reviewer-dup-{mode}",
                         f"{cfg.PREFIX}_dup_r_{mode}_{RUN}", *flags, "--state-file",
                         str(state) + ".rev", test_run=test_run)
        wait_ready(writer, reviewer)
        drafts, finals = TopicReader(cfg.DRAFTS_TOPIC), TopicReader(cfg.FINAL_TOPIC)
        message = task(test_run)
        cid = message["correlation_id"]
        meta1 = send_json(producer, cfg.TASKS_TOPIC, message, key=cid)
        log(COMPONENT, f"[{mode}] SENT original correlation_id={cid} -> p{meta1.partition}@"
                       f"{meta1.offset}")
        writer.wait_for("COMMITTED", 30)
        time.sleep(1)
        meta2 = send_json(producer, cfg.TASKS_TOPIC, message, key=cid)  # identical replay
        log(COMPONENT, f"[{mode}] REPLAYED same correlation_id={cid} -> p{meta2.partition}@"
                       f"{meta2.offset}")
        time.sleep(6)
        d = matching(drafts.collect(timeout=4, idle_stop=2), lambda m: m.get("correlation_id") == cid, test_run)
        f = matching(finals.collect(timeout=4, idle_stop=2), lambda m: m.get("correlation_id") == cid,
                     test_run)
        drafts.close()
        finals.close()
        rows[mode] = {"mode": mode, "idempotency": mode == "after", "correlation_id": cid,
                      "deliveries_to_writer": 2, "drafts_produced": len(d),
                      "finals_produced": len(f),
                      "duplicate_skipped_logs": writer.count("DUPLICATE") + reviewer.count(
                          "DUPLICATE")}
        log(COMPONENT, f"[{mode}] RESULT drafts={len(d)} finals={len(f)} "
                       f"duplicate_skips={rows[mode]['duplicate_skipped_logs']}")
        excerpt(f"duplicate_{mode}", [writer, reviewer],
                ["RECEIVED", "DUPLICATE", "SENT s2837", "COMMITTED", "started pid"])
        writer.stop()
        reviewer.stop()
    RESULTS["duplicate"] = rows
    return rows


# ----------------------------------------------------------------------------
# II. consumer death mid-processing
# ----------------------------------------------------------------------------


def test_crash(producer):
    banner(COMPONENT, "PART 3.II  CONSUMER DEATH - kill Writer mid-processing, restart it")
    rows = {}
    for mode in ("before", "after"):
        test_run = f"crash-{mode}-{RUN}"
        group = f"{cfg.PREFIX}_crash_{mode}_{RUN}"
        commit = "early" if mode == "before" else "after"
        state = cfg.STATE_DIR / f"{test_run}.sqlite"
        flags = ["--commit-mode", commit, "--state-file", str(state)]
        writer = Agent("writer.py", f"writer-crash-{mode}", group, *flags, test_run=test_run)
        wait_ready(writer)
        drafts = TopicReader(cfg.DRAFTS_TOPIC)
        warm = task(test_run)  # gives the new group a committed offset to resume from
        send_json(producer, cfg.TASKS_TOPIC, warm, key="crash-test")
        writer.wait_for("SENT s2837_drafts", 30)
        slow = task(test_run, simulate_slow_seconds=8)
        cid = slow["correlation_id"]
        meta = send_json(producer, cfg.TASKS_TOPIC, slow, key="crash-test")
        log(COMPONENT, f"[{mode}] SENT slow task correlation_id={cid} -> "
                       f"{cfg.TASKS_TOPIC}[p{meta.partition}@{meta.offset}]")
        writer.wait_for("WORKING slowly", 30)
        time.sleep(2)
        before_kill = group_committed(group, cfg.TASKS_TOPIC)
        pid = writer.kill()
        log(COMPONENT, f"[{mode}] KILLED {writer.instance} pid={pid} mid-processing; "
                       f"committed offsets at kill = {before_kill} (message offset "
                       f"{meta.offset} on p{meta.partition})")
        time.sleep(2)
        restarted = Agent("writer.py", f"writer-crash-{mode}-restart", group, *flags,
                          test_run=test_run)
        wait_ready(restarted, timeout=90)
        got = matching(drafts.collect(until=lambda rs: any(record_json(r).get("correlation_id")
                                                           == cid for r in rs), timeout=40),
                       lambda m: m.get("correlation_id") == cid, test_run)
        after_restart = group_committed(group, cfg.TASKS_TOPIC)
        drafts.close()
        lost = not got
        rows[mode] = {"mode": mode, "commit_mode": commit, "correlation_id": cid,
                      "message_partition": meta.partition, "message_offset": meta.offset,
                      "committed_at_kill": before_kill, "committed_after_restart": after_restart,
                      "redelivered_after_restart": restarted.count(cid) > 0 and not lost,
                      "redelivery_detected_log": restarted.count("REDELIVERY") > 0,
                      "draft_completed": not lost, "message_lost": lost}
        log(COMPONENT, f"[{mode}] RESULT draft_completed={not lost} message_lost={lost} "
                       f"committed_after_restart={after_restart}")
        excerpt(f"crash_{mode}", [writer, restarted],
                ["started pid", "READY", "RECEIVED", "WORKING", "COMMITTED", "REDELIVERY",
                 "SENT s2837"])
        restarted.stop()
    RESULTS["crash"] = rows
    return rows


# ----------------------------------------------------------------------------
# III. poison message
# ----------------------------------------------------------------------------


def test_poison(producer):
    banner(COMPONENT, "PART 3.III  POISON MESSAGE - bounded retries + s2837_dead_letter")
    rows = {}
    for mode in ("before", "after"):
        test_run = f"poison-{mode}-{RUN}"
        flags = ["--no-dlq"] if mode == "before" else ["--max-retries", str(cfg.MAX_RETRIES)]
        writer = Agent("writer.py", f"writer-poison-{mode}", f"{cfg.PREFIX}_poison_{mode}_{RUN}",
                       *flags, "--state-file", str(cfg.STATE_DIR / f"{test_run}.sqlite"),
                       test_run=test_run)
        wait_ready(writer)
        drafts, dlq = TopicReader(cfg.DRAFTS_TOPIC), TopicReader(cfg.DEAD_LETTER_TOPIC)
        poison = {"correlation_id": new_id(), "test_run": test_run, "kind": "answer_task",
                  "question": "poison", "plan": "THIS-IS-NOT-A-LIST"}
        goods = [task(test_run, question=f"Good question {i} about a restaurant inspection")
                 for i in range(1, 4)]
        meta = send_json(producer, cfg.TASKS_TOPIC, poison, key="poison-test")
        log(COMPONENT, f"[{mode}] SENT poison correlation_id={poison['correlation_id']} -> "
                       f"p{meta.partition}@{meta.offset} (plan is not a list)")
        for g in goods:  # same key -> same partition, queued behind the poison
            m = send_json(producer, cfg.TASKS_TOPIC, g, key="poison-test")
            log(COMPONENT, f"[{mode}] SENT good correlation_id={g['correlation_id']} -> "
                           f"p{m.partition}@{m.offset}")
        good_ids = {g["correlation_id"] for g in goods}
        window = 15 if mode == "before" else 30
        got = matching(drafts.collect(until=lambda rs: len(matching(
            rs, lambda x: x.get("correlation_id") in good_ids)) >= 3, timeout=window),
            lambda x: x.get("correlation_id") in good_ids, test_run)
        letters = matching(dlq.collect(timeout=3, idle_stop=2),
                           lambda x: x.get("correlation_id") == poison["correlation_id"])
        drafts.close()
        dlq.close()
        rows[mode] = {"mode": mode, "dlq_enabled": mode == "after",
                      "max_retries": None if mode == "before" else cfg.MAX_RETRIES,
                      "poison_attempts": writer.count("ERROR attempt"),
                      "observed_seconds": window if mode == "before" else None,
                      "good_messages_sent": 3, "good_messages_processed": len(got),
                      "dead_letter_records": len(letters),
                      "dead_letter_sample": letters[0] if letters else None}
        log(COMPONENT, f"[{mode}] RESULT attempts={rows[mode]['poison_attempts']} "
                       f"good_processed={len(got)}/3 dead_letter={len(letters)}")
        excerpt(f"poison_{mode}", [writer],
                ["RECEIVED", "ERROR attempt", "RETRY", "DEAD-LETTER", "COMMITTED", "SENT s2837"])
        writer.stop()
    RESULTS["poison"] = rows
    return rows


# ----------------------------------------------------------------------------
# IV. ordering with two partitions / two writers
# ----------------------------------------------------------------------------


def ordering_messages():
    rng = random.Random(cfg.VERIFY_SEED)
    entities = [f"INSP-{cfg.SID4}-{c}" for c in "ABCD"]
    lifecycle = ["SCHEDULED", "STARTED", "VIOLATION_RECORDED", "SCORE_UPDATED",
                 "STATUS_CHANGED", "REINSPECTION_BOOKED", "CLOSED", "NOTE_ADDED"]
    seq = {e: 0 for e in entities}
    out = []
    for i in range(20):
        entity = rng.choice(entities)
        seq[entity] += 1
        out.append({"global_index": i, "entity_id": entity, "seq": seq[entity],
                    "event": lifecycle[(seq[entity] - 1) % len(lifecycle)],
                    "work_ms": rng.randint(30, 900)})
    return out


def analyse(rows):
    by_entity = {}
    for row in sorted(rows, key=lambda r: r["processed_at"]):
        by_entity.setdefault(row["entity_id"], []).append(row)
    summary = {}
    for entity, items in sorted(by_entity.items()):
        seqs = [r["seq"] for r in items]
        inversions = sum(1 for a in range(len(seqs)) for b in range(a + 1, len(seqs))
                         if seqs[a] > seqs[b])
        summary[entity] = {"processed_seq_order": seqs, "in_order": seqs == sorted(seqs),
                           "inversions": inversions,
                           "partitions": sorted({r["partition"] for r in items}),
                           "writers": sorted({r["writer"] for r in items})}
    return summary


def test_ordering(producer):
    banner(COMPONENT, f"PART 3.IV  ORDERING - 20 messages from VERIFY_SEED={cfg.VERIFY_SEED}, "
                      f"{cfg.TASKS_TOPIC} has 2 partitions, 2 writers in one group")
    base = ordering_messages()
    (cfg.RAW_DIR / "part3_ordering_messages.json").write_text(json.dumps(base, indent=2),
                                                              encoding="utf-8")
    runs = {}
    for run in ("unkeyed", "keyed"):
        test_run = f"order-{run}-{RUN}"
        group = f"{cfg.PREFIX}_order_{run}_{RUN}"
        w1 = Agent("writer.py", f"writer-order-1-{run}", group, "--state-file",
                   str(cfg.STATE_DIR / f"{test_run}-1.sqlite"), test_run=test_run)
        w2 = Agent("writer.py", f"writer-order-2-{run}", group, "--state-file",
                   str(cfg.STATE_DIR / f"{test_run}-2.sqlite"), test_run=test_run)
        assignment = wait_ready(w1, w2, partitions=[0, 1], timeout=90)
        log(COMPONENT, f"[{run}] both writers ready, assignment={assignment}")
        drafts = TopicReader(cfg.DRAFTS_TOPIC)
        sent = []
        for msg in base:
            body = {"correlation_id": new_id(), "test_run": test_run, "kind": "ordering_event",
                    "run": run, **msg}
            if run == "unkeyed":
                # no key: spread round-robin over both partitions (what a key-less producer
                # does over time; made explicit so the run is reproducible)
                meta = send_json(producer, cfg.TASKS_TOPIC, body, partition=msg["global_index"] % 2)
            else:
                meta = send_json(producer, cfg.TASKS_TOPIC, body, key=msg["entity_id"])
            sent.append({**msg, "sent_partition": meta.partition, "sent_offset": meta.offset,
                         "key": msg["entity_id"] if run == "keyed" else None})
        log(COMPONENT, f"[{run}] sent 20 messages "
                       f"({'key=entity_id' if run == 'keyed' else 'no key'})")
        results = matching(drafts.collect(until=lambda rs: len(matching(
            rs, lambda x: x.get("test_run") == test_run)) >= 20, timeout=90),
            lambda x: x.get("test_run") == test_run)
        drafts.close()
        rows = sorted(({k: r[k] for k in ("global_index", "entity_id", "seq", "event",
                                          "partition", "offset", "writer", "processed_at")}
                       for r in results), key=lambda r: r["processed_at"])
        for i, row in enumerate(rows, 1):
            row["processing_rank"] = i
        with open(cfg.RAW_DIR / f"part3_ordering_{run}.csv", "w", newline="",
                  encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["processing_rank", "global_index",
                                                        "entity_id", "seq", "event", "partition",
                                                        "offset", "writer", "processed_at"])
            writer.writeheader()
            writer.writerows(rows)
        summary = analyse(rows)
        runs[run] = {"received": len(rows), "sent": sent, "per_entity": summary,
                     "entities_out_of_order": sum(not s["in_order"] for s in summary.values()),
                     "entities_split_across_partitions": sum(len(s["partitions"]) > 1
                                                             for s in summary.values()),
                     "total_inversions": sum(s["inversions"] for s in summary.values())}
        for entity, s in summary.items():
            log(COMPONENT, f"[{run}] {entity} processed seq order={s['processed_seq_order']} "
                           f"partitions={s['partitions']} in_order={s['in_order']}")
        log(COMPONENT, f"[{run}] RESULT out_of_order_entities="
                       f"{runs[run]['entities_out_of_order']}/4 inversions="
                       f"{runs[run]['total_inversions']}")
        excerpt(f"ordering_{run}", [w1, w2], ["READY", "ORDER entity"])
        w1.stop()
        w2.stop()
    RESULTS["ordering"] = runs
    return runs


# ----------------------------------------------------------------------------
# METRICS.md
# ----------------------------------------------------------------------------


def load_all():
    path = cfg.RAW_DIR / "part3_results.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.update(RESULTS)
    data["updated_at"] = now_iso()
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return data


def write_metrics(data):
    lines = [f"# HW8 METRICS - {cfg.STUDENT_NAME} (SID4 {cfg.SID4}, PREFIX {cfg.PREFIX})", "",
             f"Generated {now_iso()} by run_hw08_failures.py from raw/part3_results.json.",
             f"Kafka bootstrap: {cfg.BOOTSTRAP}; {cfg.TASKS_TOPIC} partitions = 2; "
             f"MAX_RETRIES = {cfg.MAX_RETRIES}; VERIFY_SEED = {cfg.VERIFY_SEED}.", ""]
    p1 = cfg.RAW_DIR / "part1_sequence.json"
    if p1.exists():
        demo = json.loads(p1.read_text(encoding="utf-8"))
        lines += ["## Part 1 - request/response over Kafka", "",
                  "| Operation | correlation_id | success | result | preserved |",
                  "|---|---|---|---|---|",
                  f"| {cfg.OP_CREATE} | {demo['create']['request']['correlation_id']} | "
                  f"{demo['create']['response']['success']} | inspection_id="
                  f"{demo['create']['response'].get(cfg.ID_FIELD)} | "
                  f"{demo['correlation_id_preserved']} |",
                  f"| {cfg.OP_GET} | {demo['get']['request']['correlation_id']} | "
                  f"{demo['get']['response']['success']} | entity returned | "
                  f"{demo['correlation_id_preserved']} |", ""]
    p2 = cfg.RAW_DIR / "part2_final.json"
    if p2.exists():
        final = json.loads(p2.read_text(encoding="utf-8"))["final"]
        lines += ["## Part 2 - three-agent pipeline", "",
                  f"- correlation_id `{final['correlation_id']}` status **{final['status']}**, "
                  f"stages: {' -> '.join(s['stage'] for s in final.get('trace', []))}, "
                  f"writer model: {(final.get('writer') or {}).get('model')}", ""]

    lines += ["## Part 3 - failure table", "",
              "| Failure scenario | Before fix | After fix |", "|---|---|---|"]
    dup = data.get("duplicate")
    if dup:
        b, a = dup["before"], dup["after"]
        lines.append(f"| Duplicate delivery | same correlation_id delivered twice -> "
                     f"{b['drafts_produced']} drafts, {b['finals_produced']} finals (extra side "
                     f"effect) | idempotency store -> {a['drafts_produced']} draft, "
                     f"{a['finals_produced']} final, {a['duplicate_skipped_logs']} DUPLICATE "
                     f"skips |")
    crash = data.get("crash")
    if crash:
        b, a = crash["before"], crash["after"]
        lines.append(f"| Consumer killed mid-work | commit-before-processing: offset already "
                     f"{b['committed_at_kill']} at kill -> after restart message_lost="
                     f"{b['message_lost']} | commit-after-success: committed {a['committed_at_kill']}"
                     f" at kill -> redelivered, REDELIVERY detected={a['redelivery_detected_log']}"
                     f", draft completed={a['draft_completed']}, committed now "
                     f"{a['committed_after_restart']} |")
    poison = data.get("poison")
    if poison:
        b, a = poison["before"], poison["after"]
        lines.append(f"| Poison message | unbounded retry: {b['poison_attempts']} attempts in "
                     f"{b['observed_seconds']}s, good messages processed "
                     f"{b['good_messages_processed']}/3 (partition blocked) | "
                     f"{a['poison_attempts']} attempts (limit {a['max_retries']}) -> "
                     f"{a['dead_letter_records']} record in {cfg.DEAD_LETTER_TOPIC}, good "
                     f"messages processed {a['good_messages_processed']}/3 |")
    order = data.get("ordering")
    if order:
        u, k = order["unkeyed"], order["keyed"]
        lines.append(f"| Two partitions/two consumers | no key: "
                     f"{u['entities_split_across_partitions']}/4 entities split across "
                     f"partitions, {u['entities_out_of_order']}/4 processed out of order "
                     f"({u['total_inversions']} inversions) | key=entity_id: "
                     f"{k['entities_split_across_partitions']}/4 split, "
                     f"{k['entities_out_of_order']}/4 out of order ({k['total_inversions']} "
                     f"inversions) |")
        for run in ("unkeyed", "keyed"):
            lines += ["", f"### Ordering run - {run}", "",
                      "| entity | processed seq order | partitions | writers | in order |",
                      "|---|---|---|---|---|"]
            for entity, s in order[run]["per_entity"].items():
                lines.append(f"| {entity} | {s['processed_seq_order']} | {s['partitions']} | "
                             f"{', '.join(s['writers'])} | {s['in_order']} |")
    lines.append("")
    (cfg.REPORT_DIR / "METRICS.md").write_text("\n".join(lines), encoding="utf-8")
    log(COMPONENT, f"wrote {cfg.REPORT_DIR / 'METRICS.md'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("test", nargs="?", default="all",
                        choices=["all", "duplicate", "crash", "poison", "ordering", "metrics"])
    args = parser.parse_args()
    cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
    cfg.STATE_DIR.mkdir(parents=True, exist_ok=True)
    wait_for_kafka(COMPONENT)
    ensure_topics(COMPONENT)
    producer = make_producer()
    banner(COMPONENT, f"HW8 Part 3 failure tests - {cfg.STUDENT_NAME} - run {RUN}")
    tests = {"duplicate": test_duplicate, "crash": test_crash, "poison": test_poison,
             "ordering": test_ordering}
    selected = list(tests) if args.test == "all" else ([] if args.test == "metrics"
                                                       else [args.test])
    for name in selected:
        tests[name](producer)
        load_all()
    write_metrics(load_all())
    producer.close()


if __name__ == "__main__":
    main()

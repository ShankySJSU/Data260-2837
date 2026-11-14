"""HW8 smoke test -> reports/hw08/verification.json   (make verify-hw08)

Start the system first:  docker compose up -d --build   (Kafka + worker + API)
Then from the code folder:
    python -m web_application.verify_hw08

The script only sends Kafka messages / HTTP calls and starts temporary planner, writer and
reviewer processes (own consumer groups, tagged test_run) - it never modifies application code.
Temporary SQLite state goes to a temp folder that is deleted at the end.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import requests

TMP = Path(tempfile.mkdtemp(prefix="hw08_verify_"))
os.environ["HW8_STATE_DIR"] = str(TMP)  # temp state for spawned agents
os.environ.setdefault("HW8_LLM", "template")  # objective, model-independent checks

from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.idempotency import IdempotencyStore  # noqa: E402
from web_application.kafka_pipeline.kafka_io import (  # noqa: E402
    TopicReader, ensure_topics, make_producer, record_json, send_json, wait_for_kafka,
)
from web_application.kafka_pipeline.request_client import KafkaRequestClient  # noqa: E402
from web_application.kafka_pipeline.run_hw08_failures import Agent, matching, wait_ready  # noqa: E402

OUTPUT = cfg.REPORT_DIR / "verification.json"
API = f"http://127.0.0.1:{cfg.PORT_BASE}"
RUN = uuid.uuid4().hex[:8]
checks = []
SAMPLE = {"name": "Verify Diner routine inspection", "inspection_code": "VERIFY-0001",
          "inspection_date": "2026-11-02T09:00:00", "status": "WARNING", "score": 77,
          "restaurant_id": 3}


def check(name, fn):
    try:
        passed = bool(fn())
        checks.append({"check": name, "status": "PASS" if passed else "FAIL"})
    except Exception as exc:
        checks.append({"check": name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
    print(f"{checks[-1]['status']:<5} {name}", flush=True)


def commit_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cfg.REPO_ROOT,
                                       text=True).strip()
    except Exception:
        return "unknown"


def topics_ok():
    from kafka import KafkaConsumer
    probe = KafkaConsumer(bootstrap_servers=cfg.BOOTSTRAP)
    ok = all(len(probe.partitions_for_topic(t) or ()) == n for t, n in cfg.TOPICS.items())
    probe.close()
    return ok


def kafka_checks(client):
    state = {}

    def roundtrip():
        cid = str(uuid.uuid4())
        req, resp = client.request(cfg.OP_CREATE, SAMPLE, cid)
        state["create"] = (cid, req, resp)
        inspection_id = resp.get(cfg.ID_FIELD)
        _, got = client.request(cfg.OP_GET, {cfg.ID_FIELD: inspection_id})
        state["get"] = got
        return (resp.get("success") is True and isinstance(inspection_id, str)
                and got.get("success") is True
                and got["inspection"][cfg.ID_FIELD] == inspection_id
                and got["inspection"]["inspection_code"] == SAMPLE["inspection_code"])

    check("create_then_get_roundtrip_through_kafka", roundtrip)
    check("correlation_id_preserved_request_to_response",
          lambda: state["create"][0] == state["create"][1]["correlation_id"]
          == state["create"][2]["correlation_id"])
    check("request_has_required_envelope_fields",
          lambda: {"correlation_id", "reply_to", "operation", "data"} <= set(state["create"][1])
          and state["create"][1]["reply_to"] == cfg.RESPONSE_TOPIC)

    def error_case(operation, data):
        cid = str(uuid.uuid4())
        _, resp = client.request(operation, data, cid)
        return resp.get("success") is False and bool(resp.get("error")) and \
            resp.get("correlation_id") == cid

    check("get_unknown_id_returns_error_with_correlation_id",
          lambda: error_case(cfg.OP_GET, {cfg.ID_FIELD: str(uuid.uuid4())}))
    check("unknown_operation_returns_error",
          lambda: error_case("DROP_ALL_TABLES", {}))
    check("invalid_or_missing_fields_rejected",
          lambda: error_case(cfg.OP_CREATE, {**SAMPLE, "score": 500, "name": ""}))

    def duplicate_create():
        cid = str(uuid.uuid4())
        _, first = client.request(cfg.OP_CREATE, {**SAMPLE, "inspection_code": "VERIFY-0002"},
                                  cid)
        _, second = client.request(cfg.OP_CREATE, {**SAMPLE, "inspection_code": "VERIFY-0002"},
                                   cid)
        return first.get(cfg.ID_FIELD) == second.get(cfg.ID_FIELD) is not None

    check("duplicate_request_same_correlation_id_creates_no_second_entity", duplicate_create)


def api_checks():
    check("fastapi_running_on_port_base",
          lambda: requests.get(f"{API}/", timeout=5).json()["port"] == cfg.PORT_BASE)

    def api_roundtrip():
        cid = str(uuid.uuid4())
        created = requests.post(f"{API}/inspections/kafka", json=SAMPLE,
                                headers={"X-Correlation-ID": cid}, timeout=20).json()
        inspection_id = created["response"][cfg.ID_FIELD]
        got = requests.get(f"{API}/inspections/kafka/{inspection_id}", timeout=20).json()
        return created["response"]["correlation_id"] == cid and got["response"]["success"]

    check("fastapi_create_get_via_kafka", api_roundtrip)


def pipeline_checks(producer):
    tag = f"verify-{RUN}"
    agents = [
        Agent("planner.py", "planner-verify", f"{cfg.PREFIX}_verify_p_{RUN}", test_run=tag),
        Agent("writer.py", "writer-verify", f"{cfg.PREFIX}_verify_w_{RUN}", test_run=tag),
        Agent("reviewer.py", "reviewer-verify", f"{cfg.PREFIX}_verify_r_{RUN}", test_run=tag),
    ]
    try:
        wait_ready(*agents, timeout=90)
        finals = TopicReader(cfg.FINAL_TOPIC)
        dlq = TopicReader(cfg.DEAD_LETTER_TOPIC)
        drafts = TopicReader(cfg.DRAFTS_TOPIC)
        cid = str(uuid.uuid4())
        send_json(producer, cfg.INBOX_TOPIC, {"correlation_id": cid, "test_run": tag,
                                              "question": "What does a FAIL inspection mean?"},
                  key=cid)
        got = matching(finals.collect(until=lambda rs: any(
            record_json(r).get("correlation_id") == cid for r in rs), timeout=60),
            lambda m: m.get("correlation_id") == cid, tag)

        check("pipeline_inbox_to_final_with_status_and_answer",
              lambda: got and got[0]["status"] in ("approved", "rejected") and got[0]["answer"])
        check("pipeline_correlation_id_preserved_all_stages",
              lambda: got and [s["stage"] for s in got[0]["trace"]] ==
              ["planner", "writer", "reviewer"])

        poison_id, good_id = str(uuid.uuid4()), str(uuid.uuid4())
        send_json(producer, cfg.TASKS_TOPIC, {"correlation_id": poison_id, "test_run": tag,
                                              "kind": "answer_task", "question": "x",
                                              "plan": "not-a-list"}, key="verify-poison")
        send_json(producer, cfg.TASKS_TOPIC, {"correlation_id": good_id, "test_run": tag,
                                              "kind": "answer_task", "question": "Restaurant "
                                              "inspection prep?", "plan": {"steps": ["a", "b"]}},
                  key="verify-poison")
        letters = matching(dlq.collect(until=lambda rs: any(
            record_json(r).get("correlation_id") == poison_id for r in rs), timeout=40),
            lambda m: m.get("correlation_id") == poison_id)
        good = matching(drafts.collect(until=lambda rs: any(
            record_json(r).get("correlation_id") == good_id for r in rs), timeout=30),
            lambda m: m.get("correlation_id") == good_id)
        check("poison_message_retried_then_dead_lettered",
              lambda: letters and letters[0]["attempts"] == cfg.MAX_RETRIES)
        check("message_after_poison_still_processed", lambda: bool(good))

        replay_id = str(uuid.uuid4())
        replay = {"correlation_id": replay_id, "test_run": tag, "kind": "answer_task",
                  "question": "Restaurant inspection replay?", "plan": {"steps": ["a", "b"]}}
        send_json(producer, cfg.TASKS_TOPIC, replay, key=replay_id)
        agents[1].wait_for(replay_id, 30)
        time.sleep(2)
        send_json(producer, cfg.TASKS_TOPIC, replay, key=replay_id)
        time.sleep(4)
        count = len(matching(drafts.collect(timeout=4, idle_stop=2),
                             lambda m: m.get("correlation_id") == replay_id))
        check("replayed_task_produces_no_second_draft",
              lambda: agents[1].count("DUPLICATE") >= 1 and count <= 1)
        for reader in (finals, dlq, drafts):
            reader.close()
    finally:
        for agent in agents:
            agent.stop()


def keyed_partition_check(producer):
    parts = {send_json(producer, cfg.TASKS_TOPIC,
                       {"correlation_id": str(uuid.uuid4()), "test_run": f"keycheck-{RUN}",
                        "kind": "ordering_event", "entity_id": "INSP-KEY", "seq": i},
                       key="INSP-KEY").partition for i in range(5)}
    return len(parts) == 1


def idempotency_unit():
    store = IdempotencyStore(TMP / "unit.sqlite")
    store.mark_started("abc")
    first = store.status("abc")
    store.mark_done("abc", {})
    ok = first == "in_progress" and store.status("abc") == "done" and store.status("x") is None
    store.close()
    return ok


def main():
    started = time.time()
    check("kafka_reachable", lambda: wait_for_kafka("VERIFY", timeout=30))
    ensure_topics("VERIFY")
    check("all_prefix_topics_exist_with_partitions", topics_ok)
    producer = make_producer()
    client = KafkaRequestClient(component="VERIFY")
    try:
        kafka_checks(client)
    finally:
        client.close()
    api_checks()
    pipeline_checks(producer)
    check("same_key_messages_land_in_one_partition", lambda: keyed_partition_check(producer))
    check("idempotency_store_tracks_in_progress_and_done", idempotency_unit)
    producer.close()

    passed = sum(c["status"] == "PASS" for c in checks)
    result = {
        "homework": "HW8",
        "student": cfg.STUDENT_NAME,
        "sid4": cfg.SID4,
        "commit_hash": commit_hash(),
        "model": os.getenv("HW8_LLM") + " for smoke test; agents use ollama qwen2.5:1.5b in Part 2",
        "configuration": {"prefix": cfg.PREFIX, "port_base": cfg.PORT_BASE,
                          "kafka_bootstrap": cfg.BOOTSTRAP, "max_retries": cfg.MAX_RETRIES,
                          "topics": cfg.TOPICS},
        "seed": cfg.SEED,
        "verify_seed": cfg.VERIFY_SEED,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(time.time() - started, 1),
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks)},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{passed}/{len(checks)} checks passed -> {OUTPUT}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

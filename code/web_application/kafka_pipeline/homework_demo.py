"""HW8 Part 1 - homework_demo.py: CREATE_INSPECTION -> GET_INSPECTION over Kafka.

Start Kafka + worker first (docker compose up -d), then from the code folder:
    python web_application/kafka_pipeline/homework_demo.py            # client talks to Kafka
    python web_application/kafka_pipeline/homework_demo.py --via-api  # through FastAPI :8137

Steps 1-10 of the assignment are printed in order. At the end the full send -> receive ->
process -> reply -> client-response sequence is rebuilt from raw/trace_events.jsonl (written
by the client AND the worker) and saved to raw/part1_sequence.json.
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

import requests  # noqa: E402

from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.kafka_io import banner, log, short  # noqa: E402

COMPONENT = "DEMO"
RANK = {"CLIENT_SEND": 1, "WORKER_RECEIVE": 2, "WORKER_PROCESS": 3, "WORKER_REPLY": 4,
        "CLIENT_RECEIVE": 5}
LABEL = {"CLIENT_SEND": "send", "WORKER_RECEIVE": "receive", "WORKER_PROCESS": "process",
         "WORKER_REPLY": "reply", "CLIENT_RECEIVE": "client-response"}

SAMPLE_INSPECTION = {
    "name": "Rangoli Indian Cuisine - routine inspection",
    "inspection_code": "S2837-INSP-0001",
    "inspection_date": "2026-11-02T10:30:00",
    "status": "PASS",
    "score": 94,
    "restaurant_id": 1,
}


def via_client(client, operation, data, correlation_id):
    return client.request(operation, data, correlation_id)


def via_api(operation, data, correlation_id):
    base = f"http://127.0.0.1:{cfg.PORT_BASE}"
    headers = {"X-Correlation-ID": correlation_id}
    if operation == cfg.OP_CREATE:
        reply = requests.post(f"{base}/inspections/kafka", json=data, headers=headers, timeout=20)
    else:
        reply = requests.get(f"{base}/inspections/kafka/{data[cfg.ID_FIELD]}", headers=headers,
                             timeout=20)
    reply.raise_for_status()
    body = reply.json()
    log(COMPONENT, f"HTTP {reply.status_code} from FastAPI: {short(body)}")
    return body["request"], body["response"]


def rebuild_sequence(correlation_ids):
    events = []
    if cfg.TRACE_FILE.exists():
        for line in cfg.TRACE_FILE.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("correlation_id") in correlation_ids and event.get("event") in RANK:
                events.append(event)
    # causal order: request order first, then send -> receive -> process -> reply -> response
    events.sort(key=lambda e: (correlation_ids.index(e["correlation_id"]), RANK[e["event"]],
                               e["ts"]))
    # keep the latest event of each kind (duplicates from older demo runs are impossible:
    # correlation ids are fresh UUIDs)
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--via-api", action="store_true", help="go through FastAPI on PORT_BASE")
    args = parser.parse_args()

    banner(COMPONENT, f"HW8 Part 1 demo - {cfg.STUDENT_NAME} - SID4={cfg.SID4} "
                      f"PREFIX={cfg.PREFIX} - {'via FastAPI' if args.via_api else 'Kafka client'}")
    client = None
    if not args.via_api:
        from web_application.kafka_pipeline.request_client import KafkaRequestClient
        client = KafkaRequestClient(component="CLIENT")

    def call(operation, data, correlation_id):
        if args.via_api:
            return via_api(operation, data, correlation_id)
        return via_client(client, operation, data, correlation_id)

    # 1. one correlation_id, created by the client before sending
    create_cid = str(uuid.uuid4())
    log(COMPONENT, f"STEP 1  created correlation_id={create_cid}")
    # 2-6. CREATE request -> worker -> response
    log(COMPONENT, f"STEP 2  sending {cfg.OP_CREATE} to {cfg.REQUEST_TOPIC}")
    create_req, create_resp = call(cfg.OP_CREATE, SAMPLE_INSPECTION, create_cid)
    log(COMPONENT, f"STEP 3  request message = {json.dumps(create_req)}")
    log(COMPONENT, "STEP 4-5 worker received/processed/replied (see worker log + sequence below)")
    log(COMPONENT, f"STEP 6  response received = {json.dumps(create_resp)}")
    if not create_resp.get("success"):
        log(COMPONENT, "CREATE failed - stopping")
        return 1
    # 7. extract generated id
    inspection_id = create_resp[cfg.ID_FIELD]
    log(COMPONENT, f"STEP 7  generated {cfg.ID_FIELD}={inspection_id}")
    # 8-9. GET with that id
    get_cid = str(uuid.uuid4())
    log(COMPONENT, f"STEP 8  sending {cfg.OP_GET} correlation_id={get_cid} "
                   f"{cfg.ID_FIELD}={inspection_id}")
    get_req, get_resp = call(cfg.OP_GET, {cfg.ID_FIELD: inspection_id}, get_cid)
    log(COMPONENT, f"STEP 9  GET request = {json.dumps(get_req)}")
    log(COMPONENT, f"STEP 9  GET response = {json.dumps(get_resp)}")
    # 10. show entity + correlation check
    log(COMPONENT, f"STEP 10 retrieved inspection = {json.dumps(get_resp.get('inspection'))}")
    preserved = (create_req["correlation_id"] == create_resp["correlation_id"] == create_cid
                 and get_req["correlation_id"] == get_resp["correlation_id"] == get_cid)
    log(COMPONENT, f"STEP 10 correlation_id preserved: CREATE {create_cid} == "
                   f"{create_resp['correlation_id']} ; GET {get_cid} == "
                   f"{get_resp['correlation_id']} -> {preserved}")

    time.sleep(1.5)  # let the worker finish writing its trace lines
    sequence = rebuild_sequence([create_cid, get_cid])
    banner(COMPONENT, "FULL SEQUENCE  CREATE_INSPECTION -> GET_INSPECTION")
    for event in sequence:
        operation = event.get("operation") or "?"
        where = event.get("topic") or event.get("where") or ""
        part = f"[p{event['partition']}@{event['offset']}]" if "offset" in event else ""
        log(COMPONENT, f"{event['ts']}  {operation:<18} {LABEL[event['event']]:<16} "
                       f"{event['component']:<7} {where}{part} "
                       f"correlation_id={event['correlation_id']}")
    if len(sequence) < 10:
        log(COMPONENT, "note: worker trace lines missing - is reports/ mounted into the worker?")

    cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = {"student": cfg.STUDENT_NAME, "via_api": args.via_api,
           "request_topic": cfg.REQUEST_TOPIC, "response_topic": cfg.RESPONSE_TOPIC,
           "create": {"request": create_req, "response": create_resp},
           "get": {"request": get_req, "response": get_resp},
           "correlation_id_preserved": preserved, "sequence": sequence}
    (cfg.RAW_DIR / "part1_sequence.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(COMPONENT, f"saved {cfg.RAW_DIR / 'part1_sequence.json'}")

    # Extra evidence: validation / error responses keep the original correlation_id
    banner(COMPONENT, "ERROR CASES (each must return success=false + same correlation_id)")
    cases = [
        ("unknown inspection_id", cfg.OP_GET, {cfg.ID_FIELD: str(uuid.uuid4())}),
        ("unknown operation", "DELETE_EVERYTHING", {}),
        ("missing/invalid fields", cfg.OP_CREATE,
         {"name": "", "inspection_code": "X1", "status": "MAYBE", "score": 150}),
    ]
    results = []
    for label, operation, data in cases:
        cid = str(uuid.uuid4())
        if args.via_api:
            body = requests.post(f"http://127.0.0.1:{cfg.PORT_BASE}/kafka/request",
                                 json={"operation": operation, "data": data,
                                       "correlation_id": cid}, timeout=20).json()
            request, response = body["request"], body["response"]
        else:
            request, response = client.request(operation, data, cid)
        ok = response.get("success") is False and response.get("correlation_id") == cid
        log(COMPONENT, f"{label:<24} -> success={response.get('success')} "
                       f"error={response.get('error')!r} correlation_id_preserved="
                       f"{response.get('correlation_id') == cid}")
        results.append({"case": label, "request": request, "response": response, "pass": ok})
    (cfg.RAW_DIR / "part1_error_cases.json").write_text(json.dumps(results, indent=2),
                                                        encoding="utf-8")
    if client:
        client.close()
    all_ok = preserved and get_resp.get("success") and all(r["pass"] for r in results)
    log(COMPONENT, f"demo finished - all checks passed: {bool(all_ok)}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

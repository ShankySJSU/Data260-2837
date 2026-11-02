"""HW8 Part 1 - Inspection worker (Kafka consumer -> process -> reply).

Consumes  s2837_inspection_requests
Replies   to the topic named by reply_to (must be s2837_inspection_responses)
Storage   plain Python dict inside the worker (as required for this exercise)

Run:  python inspection_worker.py          (or the "worker" service in docker-compose.yml)
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

import warnings  # noqa: E402

warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
from pydantic import ValidationError  # noqa: E402

from web_application.domain.schema import InspectionCreate  # noqa: E402
from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.kafka_io import (  # noqa: E402
    decode, ensure_topics, log, make_group_consumer, make_producer, now_iso, send_json, short,
    trace, wait_for_kafka,
)

COMPONENT = "WORKER"
INSPECTIONS = {}  # inspection_id -> inspection dict   (the in-worker "database")
REPLIES = {}  # correlation_id -> response already sent (duplicate request => same reply)


def validation_message(exc):
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", ())) or "data"
        parts.append(f"{field}: {err.get('msg')}")
    return "Invalid inspection data - " + "; ".join(parts)


def create_inspection(data):
    if not isinstance(data, dict) or not data:
        return {"success": False, "error": "data must be a non-empty object"}
    try:
        inspection = InspectionCreate(**data)
    except ValidationError as exc:
        return {"success": False, "error": validation_message(exc)}
    inspection_id = str(uuid.uuid4())
    record = {cfg.ID_FIELD: inspection_id, **inspection.model_dump(mode="json"),
              "created_at": now_iso()}
    INSPECTIONS[inspection_id] = record
    return {"success": True, cfg.ID_FIELD: inspection_id, "message": "Inspection created"}


def get_inspection(data):
    inspection_id = (data or {}).get(cfg.ID_FIELD) if isinstance(data, dict) else None
    if not isinstance(inspection_id, str) or not inspection_id.strip():
        return {"success": False, "error": f"{cfg.ID_FIELD} is required"}
    record = INSPECTIONS.get(inspection_id.strip())
    if record is None:
        return {"success": False, "error": "Inspection not found"}
    return {"success": True, "inspection": record}


HANDLERS = {cfg.OP_CREATE: create_inspection, cfg.OP_GET: get_inspection}


def process(request):
    """Validate the envelope and run the operation. Always returns a response dict."""
    correlation_id = request.get("correlation_id")
    operation = request.get("operation")
    if not isinstance(correlation_id, str) or not correlation_id:
        body = {"success": False, "error": "Missing correlation_id"}
    elif "data" not in request:
        body = {"success": False, "error": "Missing data"}
    elif operation not in HANDLERS:
        body = {"success": False, "error": "Unknown operation"}
    else:
        body = HANDLERS[operation](request.get("data"))
    return {"correlation_id": correlation_id, "operation": operation, **body,
            "worker_processed_at": now_iso()}


def reply_topic(request):
    reply_to = request.get("reply_to")
    return reply_to if reply_to == cfg.RESPONSE_TOPIC else None


def main():
    wait_for_kafka(COMPONENT)
    ensure_topics(COMPONENT)
    producer = make_producer()
    consumer = make_group_consumer(cfg.WORKER_GROUP, [cfg.REQUEST_TOPIC])
    ready = False
    log(COMPONENT, f"connecting to {cfg.BOOTSTRAP}, group={cfg.WORKER_GROUP}")
    while True:
        batches = consumer.poll(timeout_ms=1000)
        if not ready and consumer.assignment():
            ready = True
            log(COMPONENT, f"Consumer is ready and listening... topic={cfg.REQUEST_TOPIC} "
                           f"partitions={sorted(tp.partition for tp in consumer.assignment())}")
        for tp, records in batches.items():
            for record in records:
                handle_record(producer, consumer, record)


def handle_record(producer, consumer, record):
    where = f"{record.topic}[p{record.partition}@{record.offset}]"
    try:
        request = decode(record.value)
    except (ValueError, UnicodeDecodeError) as exc:
        log(COMPONENT, f"RECEIVED unreadable message at {where}: {exc}")
        response = {"correlation_id": None, "success": False,
                    "error": f"Malformed request: {exc}"}
        send_json(producer, cfg.RESPONSE_TOPIC, response)
        consumer.commit()
        return

    correlation_id = request.get("correlation_id")
    operation = request.get("operation")
    log(COMPONENT, f"RECEIVED from {where} correlation_id={correlation_id} "
                   f"operation={operation} message={short(request)}")
    trace(COMPONENT, "WORKER_RECEIVE", correlation_id, operation=operation,
          topic=record.topic, partition=record.partition, offset=record.offset, message=request)

    if correlation_id in REPLIES:  # idempotency: duplicate delivery -> resend, no new entity
        response = REPLIES[correlation_id]
        log(COMPONENT, f"DUPLICATE correlation_id={correlation_id} - re-sending stored reply, "
                       "no new side effect")
    else:
        log(COMPONENT, f"PROCESSING {operation} correlation_id={correlation_id}")
        response = process(request)
        if isinstance(correlation_id, str) and correlation_id:
            REPLIES[correlation_id] = response
        trace(COMPONENT, "WORKER_PROCESS", correlation_id, operation=operation,
              success=response.get("success"), result=response)
        log(COMPONENT, f"PROCESSED {operation} correlation_id={correlation_id} "
                       f"success={response['success']} "
                       f"{'inspection_id=' + response[cfg.ID_FIELD] if cfg.ID_FIELD in response else ''}"
                       f"{'error=' + response['error'] if 'error' in response else ''}")

    topic = reply_topic(request)
    if topic is None:
        response = {**response, "success": False,
                    "error": f"reply_to must be {cfg.RESPONSE_TOPIC}"}
        topic = cfg.RESPONSE_TOPIC
    meta = send_json(producer, topic, response, key=correlation_id)
    consumer.commit()  # commit only after the reply is safely written
    log(COMPONENT, f"SENT response to {topic}[p{meta.partition}@{meta.offset}] "
                   f"correlation_id={correlation_id} response={short(response)}")
    trace(COMPONENT, "WORKER_REPLY", correlation_id, operation=operation, topic=topic,
          partition=meta.partition, offset=meta.offset, response=response)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log(COMPONENT, "stopped")

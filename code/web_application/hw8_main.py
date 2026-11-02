"""HW8 FastAPI wrapper over the Kafka request/response service.

Run from the code folder:
    python -m uvicorn web_application.hw8_main:app --host 127.0.0.1 --port 8137
(or the "api" service in docker-compose.yml)

The API never touches the inspection store directly: every call becomes a Kafka request on
s2837_inspection_requests and waits for the worker's reply on s2837_inspection_responses.
/inspections-direct is an in-process baseline used only for the JMeter comparison.
"""

import time
import uuid
import warnings
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")

from web_application.domain.schema import InspectionCreate
from web_application.kafka_pipeline import config as cfg
from web_application.kafka_pipeline.kafka_io import ensure_topics, log, wait_for_kafka
from web_application.kafka_pipeline.request_client import KafkaRequestClient

COMPONENT = "API"
STATE = {}
DIRECT_STORE = {}


@asynccontextmanager
async def lifespan(_app):
    wait_for_kafka(COMPONENT)
    ensure_topics(COMPONENT)
    STATE["client"] = KafkaRequestClient(component=COMPONENT)
    log(COMPONENT, f"FastAPI server started at http://127.0.0.1:{cfg.PORT_BASE} "
                   f"(Kafka {cfg.BOOTSTRAP}, requests={cfg.REQUEST_TOPIC}, "
                   f"responses={cfg.RESPONSE_TOPIC})")
    yield
    STATE["client"].close()
    log(COMPONENT, "FastAPI server stopped")


app = FastAPI(title="DATA260 HW8 - Inspections over Kafka", version="1.0.0", lifespan=lifespan)


async def kafka_call(operation, data, correlation_id):
    log(COMPONENT, f"HTTP -> Kafka operation={operation} correlation_id={correlation_id}")
    try:
        message, response = await run_in_threadpool(
            STATE["client"].request, operation, data, correlation_id)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    log(COMPONENT, f"Kafka -> HTTP returning to caller correlation_id="
                   f"{response.get('correlation_id')} success={response.get('success')}")
    return {"request": message, "response": response}


@app.get("/")
def root():
    return {"message": "DATA260 HW8 Kafka API running", "student": cfg.STUDENT_NAME,
            "port": cfg.PORT_BASE, "request_topic": cfg.REQUEST_TOPIC,
            "response_topic": cfg.RESPONSE_TOPIC}


@app.post("/inspections/kafka")
async def create_inspection_kafka(data: dict = Body(...),
                                  x_correlation_id: str | None = Header(default=None)):
    return await kafka_call(cfg.OP_CREATE, data, x_correlation_id or str(uuid.uuid4()))


@app.get("/inspections/kafka/{inspection_id}")
async def get_inspection_kafka(inspection_id: str,
                               x_correlation_id: str | None = Header(default=None)):
    return await kafka_call(cfg.OP_GET, {cfg.ID_FIELD: inspection_id},
                            x_correlation_id or str(uuid.uuid4()))


@app.post("/kafka/request")
async def raw_kafka_request(body: dict = Body(...)):
    """Generic envelope: {"operation": ..., "data": {...}, "correlation_id": optional}."""
    return await kafka_call(body.get("operation"), body.get("data"),
                            body.get("correlation_id") or str(uuid.uuid4()))


@app.post("/inspections-direct")
def create_inspection_direct(data: dict = Body(...)):
    """JMeter baseline: same validation, stored in-process, no Kafka hop."""
    started = time.perf_counter()
    try:
        inspection = InspectionCreate(**data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
    inspection_id = str(uuid.uuid4())
    DIRECT_STORE[inspection_id] = inspection.model_dump(mode="json")
    return {"success": True, cfg.ID_FIELD: inspection_id, "message": "Inspection created",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}

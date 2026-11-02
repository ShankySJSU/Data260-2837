"""HW8 Part 1 - Kafka request/response client.

The client creates the correlation_id ONCE, sends
    {"correlation_id", "reply_to", "operation", "data"}
to s2837_inspection_requests and waits for the response with the same correlation_id on
s2837_inspection_responses. Used by homework_demo.py and by the FastAPI wrapper (hw8_main.py).
"""

import threading
import time

from . import config as cfg
from .kafka_io import TopicReader, log, make_producer, new_id, record_json, send_json, short, trace


class KafkaRequestClient:
    def __init__(self, component="CLIENT"):
        self.component = component
        self.producer = make_producer()
        self.reader = TopicReader(cfg.RESPONSE_TOPIC)  # pinned to end BEFORE any request is sent
        self._pending = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    # background thread: route responses to waiting callers by correlation_id
    def _listen(self):
        while not self._stop.is_set():
            for record in self.reader.poll(300):
                response = record_json(record)
                correlation_id = response.get("correlation_id")
                with self._lock:
                    slot = self._pending.get(correlation_id)
                if slot is not None:
                    slot["response"] = response
                    slot["where"] = f"{record.topic}[p{record.partition}@{record.offset}]"
                    slot["event"].set()

    @staticmethod
    def build_request(operation, data, correlation_id=None):
        return {
            "correlation_id": correlation_id or new_id(),
            "reply_to": cfg.RESPONSE_TOPIC,
            "operation": operation,
            "data": data,
        }

    def request(self, operation, data, correlation_id=None, timeout=15):
        message = self.build_request(operation, data, correlation_id)
        correlation_id = message["correlation_id"]
        slot = {"event": threading.Event()}
        with self._lock:
            self._pending[correlation_id] = slot
        started = time.perf_counter()
        meta = send_json(self.producer, cfg.REQUEST_TOPIC, message, key=correlation_id)
        log(self.component, f"SENT to {cfg.REQUEST_TOPIC}[p{meta.partition}@{meta.offset}] "
                            f"correlation_id={correlation_id} message={short(message)}")
        trace(self.component, "CLIENT_SEND", correlation_id, operation=operation,
              topic=cfg.REQUEST_TOPIC, partition=meta.partition, offset=meta.offset,
              message=message)
        try:
            if not slot["event"].wait(timeout):
                raise TimeoutError(f"no response for correlation_id={correlation_id} "
                                   f"within {timeout}s - is the worker running?")
        finally:
            with self._lock:
                self._pending.pop(correlation_id, None)
        response = slot["response"]
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        log(self.component, f"RECEIVED response from {slot['where']} correlation_id="
                            f"{response.get('correlation_id')} success={response.get('success')} "
                            f"round_trip_ms={elapsed_ms} response={short(response)}")
        trace(self.component, "CLIENT_RECEIVE", correlation_id, operation=operation,
              where=slot["where"], round_trip_ms=elapsed_ms, response=response)
        return message, response

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self.reader.close()
        self.producer.close()

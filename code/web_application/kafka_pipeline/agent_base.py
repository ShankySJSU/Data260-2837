"""Shared consume -> process -> produce loop for Planner / Writer / Reviewer (HW8 Part 2 + 3).

Safety features (Part 3) and the switches that turn them OFF for the "before fix" runs:

  idempotency   correlation_id stored in SQLite; replay => no new output      --no-idempotency
  offset commit commit only AFTER output is acked by Kafka                     --commit-mode early
  retries/DLQ   bounded retries, then s2837_dead_letter, then move on          --no-dlq
"""

import argparse
import os
import time
import traceback

from . import config as cfg
from .idempotency import IdempotencyStore
from .kafka_io import (
    decode, ensure_topics, log, make_group_consumer, make_producer, now_iso, send_json, short,
    trace, wait_for_kafka,
)


class PermanentError(ValueError):
    """Message can never succeed (bad JSON / missing fields)."""


def build_parser(default_instance, default_group):
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", default=default_instance)
    parser.add_argument("--group", default=default_group)
    parser.add_argument("--offset-reset", default="earliest", choices=["earliest", "latest"])
    parser.add_argument("--state-file", default=None)
    parser.add_argument("--no-idempotency", action="store_true")
    parser.add_argument("--commit-mode", default="after", choices=["after", "early"])
    parser.add_argument("--no-dlq", action="store_true")
    parser.add_argument("--max-retries", type=int, default=cfg.MAX_RETRIES)
    parser.add_argument("--test-run", default=None,
                        help="Part 3 isolation: only handle messages tagged with this test_run")
    return parser


class AgentRunner:
    def __init__(self, name, in_topic, handler, args):
        self.name = name
        self.component = args.instance.upper()
        self.in_topic = in_topic
        self.handler = handler
        self.args = args
        state = args.state_file or (cfg.STATE_DIR / f"{args.instance}_{args.group}.sqlite")
        self.store = None if args.no_idempotency else IdempotencyStore(state)
        self.producer = None
        self.consumer = None
        self._assignment = None

    # ------------------------------------------------------------------
    def start(self):
        wait_for_kafka(self.component)
        ensure_topics(self.component)
        self.producer = make_producer()
        self.consumer = make_group_consumer(self.args.group, [self.in_topic],
                                            offset_reset=self.args.offset_reset,
                                            client_id=f"{self.args.instance}-{os.getpid()}")
        log(self.component, f"{self.name} started pid={os.getpid()} topic={self.in_topic} "
                            f"group={self.args.group} idempotency={self.store is not None} "
                            f"commit_mode={self.args.commit_mode} "
                            f"dlq={'off' if self.args.no_dlq else cfg.DEAD_LETTER_TOPIC} "
                            f"max_retries={self.args.max_retries}")
        try:
            while True:
                batches = self.consumer.poll(timeout_ms=1000)
                self._check_assignment(batches)
                for _tp, records in batches.items():
                    for record in records:
                        self._handle(record)
        except KeyboardInterrupt:
            log(self.component, "stopped by Ctrl+C (uncommitted work will be redelivered)")
        finally:
            self.consumer.close(autocommit=False)
            self.producer.close()

    def _check_assignment(self, batches):
        current = sorted(tp.partition for tp in self.consumer.assignment())
        if current != self._assignment:
            self._assignment = current
            # next offset to process = position minus what this poll already returned
            positions = {tp.partition: self.consumer.position(tp) - len(batches.get(tp, []))
                         for tp in self.consumer.assignment()}
            log(self.component, f"READY assigned partitions={current} positions={positions} "
                                "- Consumer is ready and listening...")

    # ------------------------------------------------------------------
    def _handle(self, record):
        where = f"{record.topic}[p{record.partition}@{record.offset}]"
        if self.args.commit_mode == "early":
            self.consumer.commit()
            log(self.component, f"COMMITTED offset {record.offset + 1} on p{record.partition} "
                                "BEFORE processing (unsafe early-commit mode)")
        attempts = 0
        while True:
            attempts += 1
            try:
                outcome = self._process_once(record, where, attempts)
                break
            except Exception as exc:  # retry / dead-letter
                permanent = isinstance(exc, (PermanentError, ValueError, UnicodeDecodeError))
                log(self.component, f"ERROR attempt {attempts}"
                                    f"{'' if self.args.no_dlq else '/' + str(self.args.max_retries)}"
                                    f" at {where}: {type(exc).__name__}: {exc}")
                if not self.args.no_dlq and attempts >= self.args.max_retries:
                    self._dead_letter(record, exc, attempts, permanent)
                    outcome = "dead_letter"
                    break
                backoff = 1.0 if self.args.no_dlq else min(0.5 * 2 ** (attempts - 1), 4)
                log(self.component, f"RETRY in {backoff:.1f}s (message blocks this partition "
                                    "until it succeeds" + (")" if self.args.no_dlq
                                                           else " or reaches the limit)"))
                time.sleep(backoff)
        if self.args.commit_mode == "after":
            self.consumer.commit()
            log(self.component, f"COMMITTED offset {record.offset + 1} on p{record.partition} "
                                f"after {outcome}")

    def _process_once(self, record, where, attempts):
        message = decode(record.value)  # ValueError -> poison
        correlation_id = message.get("correlation_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise PermanentError("missing correlation_id")
        if message.get("test_run") != self.args.test_run:
            log(self.component, f"IGNORED {where} test_run={message.get('test_run')} "
                                f"(this agent handles test_run={self.args.test_run})")
            return "ignored"
        if attempts == 1:
            log(self.component, f"RECEIVED {where} correlation_id={correlation_id} "
                                f"message={short(message, 300)}")
        if self.store is not None:
            status = self.store.status(correlation_id)
            if status == "done":
                log(self.component, f"DUPLICATE correlation_id={correlation_id} already "
                                    "processed - skipped, no new output (idempotent)")
                trace(self.component, "DUPLICATE_SKIPPED", correlation_id, where=where)
                return "duplicate_skipped"
            if status == "in_progress" and attempts == 1:
                log(self.component, f"REDELIVERY correlation_id={correlation_id} - previous "
                                    "attempt never finished (consumer died); processing again")
            self.store.mark_started(correlation_id)

        message.setdefault("trace", [])
        stage = {"stage": self.name, "agent": self.args.instance, "pid": os.getpid(),
                 "topic": record.topic, "partition": record.partition, "offset": record.offset,
                 "received_at": now_iso()}
        log(self.component, f"PROCESSING correlation_id={correlation_id}")
        outputs = self.handler(message, record, self)
        stage["finished_at"] = now_iso()
        for topic, value, key in outputs:
            value.setdefault("trace", message["trace"] + [stage])
            meta = send_json(self.producer, topic, value, key=key)
            log(self.component, f"SENT {topic}[p{meta.partition}@{meta.offset}] "
                                f"correlation_id={correlation_id} message={short(value, 300)}")
            trace(self.component, "SENT", correlation_id, topic=topic,
                  partition=meta.partition, offset=meta.offset)
        if self.store is not None:
            self.store.mark_done(correlation_id, {"outputs": len(outputs)})
        return "success"

    def _dead_letter(self, record, exc, attempts, permanent):
        raw = record.value.decode("utf-8", "replace") if record.value else None
        try:
            correlation_id = decode(record.value).get("correlation_id")
        except Exception:
            correlation_id = None
        letter = {
            "correlation_id": correlation_id,
            "failed_stage": self.name,
            "failed_agent": self.args.instance,
            "source_topic": record.topic, "source_partition": record.partition,
            "source_offset": record.offset,
            "error_type": type(exc).__name__, "error": str(exc),
            "permanent": permanent, "attempts": attempts,
            "raw_value": raw, "dead_lettered_at": now_iso(),
            "traceback_tail": traceback.format_exception_only(type(exc), exc)[-1].strip(),
        }
        meta = send_json(self.producer, cfg.DEAD_LETTER_TOPIC, letter, key=correlation_id)
        log(self.component, f"DEAD-LETTER after {attempts} attempts -> "
                            f"{cfg.DEAD_LETTER_TOPIC}[p{meta.partition}@{meta.offset}] "
                            f"source={record.topic}[p{record.partition}@{record.offset}]")
        trace(self.component, "DEAD_LETTER", correlation_id, offset=record.offset)


def require(message, field, kind=str):
    value = message.get(field)
    if not isinstance(value, kind) or (kind is str and not value.strip()):
        raise PermanentError(f"field '{field}' missing or invalid")
    return value

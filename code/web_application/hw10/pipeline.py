"""HW10 - traced client for the HW8 Planner -> Writer -> Reviewer pipeline.

The caller supplies trace_id; it is sent as the HW8 correlation_id, so the same value is on
s2837_inbox, s2837_tasks, s2837_drafts, s2837_final (and s2837_dead_letter on failure).

KafkaPipeline   real path. One group-less consumer watches s2837_final and
                s2837_dead_letter, so a dead-lettered request fails fast with the failing
                stage instead of waiting for the timeout. Every wait is bounded.
DirectPipeline  the same llm.plan / llm.write / reviewer.review functions in this process and
                the same message shapes, appended to raw/direct_messages.jsonl.
                DEBUG / OFFLINE SMOKE TEST ONLY - never used for reported numbers.
"""

import json
import os
import time

from ..kafka_pipeline import config as kcfg
from . import config as cfg
from . import tracing
from .common import log

COMPONENT = "PIPELINE"


class PipelineError(RuntimeError):
    def __init__(self, stage, error):
        super().__init__(f"{stage}: {error}")
        self.stage = stage
        self.error = error


def _tracking_fields(trace_id, question, inject_failure):
    message = {"correlation_id": trace_id, "question": question,
               "sent_at": tracing.iso(time.time()), "source": "hw10.traced_qa"}
    if inject_failure:
        message["inject_failure"] = inject_failure
    return message


# ----------------------------------------------------------------------------
# Kafka
# ----------------------------------------------------------------------------

class Tap:
    """One group-less consumer assigned to every partition of the given topics."""

    def __init__(self, topics):
        from kafka import KafkaConsumer, TopicPartition
        from ..kafka_pipeline.kafka_io import _partitions
        self.consumer = KafkaConsumer(bootstrap_servers=kcfg.BOOTSTRAP, group_id=None,
                                      enable_auto_commit=False)
        self.tps = []
        for topic in topics:
            parts = _partitions(self.consumer, topic)
            if not parts:
                self.consumer.close()
                raise RuntimeError(f"topic {topic} not found - run create_topics.py first")
            self.tps.extend(TopicPartition(topic, p) for p in parts)
        self.consumer.assign(self.tps)

    def positions(self):
        out = {}
        for tp in self.tps:
            out.setdefault(tp.topic, {})[str(tp.partition)] = self.consumer.position(tp)
        return out

    def mark_end(self):
        """Jump to the current end of every partition; returns {topic: {partition: offset}}."""
        self.consumer.seek_to_end(*self.tps)
        return self.positions()

    def seek(self, offsets=None):
        """Seek to {topic: {partition: offset}}; partitions not listed start at the beginning."""
        offsets = offsets or {}
        missing = []
        for tp in self.tps:
            per_topic = offsets.get(tp.topic) or {}
            value = per_topic.get(str(tp.partition), per_topic.get(tp.partition))
            if value is None:
                missing.append(tp)
            else:
                self.consumer.seek(tp, int(value))
        if missing:
            self.consumer.seek_to_beginning(*missing)

    def end_offsets(self):
        return {(tp.topic, tp.partition): off
                for tp, off in self.consumer.end_offsets(self.tps).items()}

    def done(self, ends):
        return all(self.consumer.position(tp) >= ends.get((tp.topic, tp.partition), 0)
                   for tp in self.tps)

    def poll(self, timeout_ms=300):
        out = []
        for _tp, records in self.consumer.poll(timeout_ms=timeout_ms).items():
            out.extend(records)
        return out

    def close(self):
        try:
            self.consumer.close()
        except Exception:  # noqa: BLE001
            pass


class KafkaPipeline:
    mode = "kafka"

    def __init__(self):
        from ..kafka_pipeline.kafka_io import make_producer, wait_for_kafka
        wait_for_kafka(COMPONENT, timeout=30)
        self.producer = make_producer()
        self.tap = Tap([kcfg.FINAL_TOPIC, kcfg.DEAD_LETTER_TOPIC, kcfg.TASKS_TOPIC,
                        kcfg.DRAFTS_TOPIC])

    def run(self, trace_id, question, inject_failure=None, timeout=None):
        """Send one question and wait (bounded) for its final message.

        Returns {"final": dict, "start_offsets": {...}}; raises PipelineError(stage, error).
        """
        from ..kafka_pipeline.kafka_io import record_json, send_json
        timeout = cfg.PIPELINE_TIMEOUT_S if timeout is None else timeout
        start_offsets = self.tap.mark_end()  # positioned BEFORE we send
        message = _tracking_fields(trace_id, question, inject_failure)
        meta = send_json(self.producer, kcfg.INBOX_TOPIC, message, key=trace_id)
        log(COMPONENT, f"SENT {kcfg.INBOX_TOPIC}[p{meta.partition}@{meta.offset}] "
                       f"trace_id={trace_id}", echo=False)
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline:
            for record in self.tap.poll(300):
                value = record_json(record)
                if value.get("correlation_id") != trace_id:
                    continue
                received = time.time()
                if record.topic == kcfg.FINAL_TOPIC:
                    produced = (record.timestamp or 0) / 1000.0 or received
                    tracing.write_span(trace_id, "final", min(produced, received), received,
                                       "ok", None, topic=record.topic,
                                       partition=record.partition, offset=record.offset,
                                       review_status=value.get("status"))
                    return {"final": value, "start_offsets": start_offsets,
                            "inbox": {"partition": meta.partition, "offset": meta.offset}}
                if record.topic == kcfg.DEAD_LETTER_TOPIC:
                    raise PipelineError(value.get("failed_stage") or "unknown",
                                        f"{value.get('error_type')}: {value.get('error')} "
                                        f"(dead-lettered after {value.get('attempts')} attempts)")
                seen.add(record.topic)
        # bounded wait expired: say where the request stopped
        if kcfg.DRAFTS_TOPIC in seen:
            stage, last = "reviewer", "a draft was produced but no final message"
        elif kcfg.TASKS_TOPIC in seen:
            stage, last = "writer", "a task was produced but no draft"
        else:
            stage, last = "planner", "no task was produced"
        error = f"timeout after {timeout:.0f}s waiting on {kcfg.FINAL_TOPIC}: {last}"
        now = time.time()
        tracing.write_span(trace_id, stage, now, now, "error", error, inferred=True)
        raise PipelineError(stage, error)

    def close(self):
        self.tap.close()
        try:
            self.producer.close()
        except Exception:  # noqa: BLE001
            pass


class KafkaMessageSource:
    """Evaluator input: plan / draft / final messages joined on correlation_id."""

    name = "kafka"
    TOPICS = {"plan": kcfg.TASKS_TOPIC, "draft": kcfg.DRAFTS_TOPIC, "final": kcfg.FINAL_TOPIC}

    def fetch(self, trace_ids, start_offsets=None, timeout=None):
        """Bounded read of the three topics up to their end offsets at call time.

        Returns ({trace_id: {"plan": rec, "draft": rec, "final": rec}}, stats). Messages that
        are not JSON objects are counted as malformed and skipped.
        """
        from ..kafka_pipeline.kafka_io import record_json
        timeout = cfg.EVAL_COLLECT_TIMEOUT_S if timeout is None else timeout
        wanted = set(trace_ids)
        found = {t: {} for t in wanted}
        stats = {"source": "kafka", "scanned": 0, "malformed": 0, "timed_out": False,
                 "topics": dict(self.TOPICS)}
        role_of = {topic: role for role, topic in self.TOPICS.items()}
        tap = Tap(list(self.TOPICS.values()))
        try:
            tap.seek(start_offsets)
            ends = tap.end_offsets()
            deadline = time.time() + timeout
            while True:
                if all(len(found[t]) == 3 for t in wanted) or tap.done(ends):
                    break
                if time.time() > deadline:
                    stats["timed_out"] = True
                    break
                for record in tap.poll(300):
                    stats["scanned"] += 1
                    value = record_json(record)
                    if "_raw" in value and "correlation_id" not in value:
                        stats["malformed"] += 1
                        continue
                    tid = value.get("correlation_id")
                    if tid in wanted:
                        # keep the last message per role (a redelivery overwrites)
                        found[tid][role_of[record.topic]] = {
                            "topic": record.topic, "partition": record.partition,
                            "offset": record.offset, "timestamp_ms": record.timestamp,
                            "key": record.key.decode("utf-8", "replace") if record.key else None,
                            "value": value}
        finally:
            tap.close()
        return found, stats


# ----------------------------------------------------------------------------
# direct (no Kafka) - debug / smoke test only
# ----------------------------------------------------------------------------

class DirectPipeline:
    mode = "direct"

    def _emit(self, topic, value, offset):
        cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
        record = {"topic": topic, "partition": 0, "offset": offset,
                  "timestamp_ms": int(time.time() * 1000), "key": value.get("correlation_id"),
                  "value": value}
        with open(cfg.DIRECT_MESSAGES, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

    def _stage(self, trace_id, queue_stage, stage, inject_failure, work):
        now = time.time()
        tracing.write_span(trace_id, queue_stage, now, now, "ok", None, agent="direct")
        start = time.time()
        try:
            if inject_failure == stage:
                raise RuntimeError(f"injected failure in {stage} stage (HW10 failed-trace demo)")
            result = work()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            tracing.write_span(trace_id, stage, start, time.time(), "error", error,
                               agent="direct")
            raise PipelineError(stage, error) from exc
        tracing.write_span(trace_id, stage, start, time.time(), "ok", None, agent="direct")
        return result

    def run(self, trace_id, question, inject_failure=None, timeout=None):
        from ..kafka_pipeline import llm
        from ..kafka_pipeline.reviewer import review
        offset = int(time.time() * 1000)
        self._emit(kcfg.INBOX_TOPIC, _tracking_fields(trace_id, question, inject_failure), offset)

        steps, plan_model = self._stage(trace_id, "inbox", "planner", inject_failure,
                                        lambda: llm.plan(question, "PLANNER"))
        plan = {"steps": steps, "model": plan_model, "planned_at": tracing.iso(time.time())}
        self._emit(kcfg.TASKS_TOPIC, {"correlation_id": trace_id, "kind": "answer_task",
                                      "question": question, "plan": plan}, offset)

        text, model = self._stage(trace_id, "tasks", "writer", inject_failure,
                                  lambda: llm.write(question, steps, "WRITER"))
        writer = {"instance": "direct", "model": model, "written_at": tracing.iso(time.time())}
        self._emit(kcfg.DRAFTS_TOPIC, {"correlation_id": trace_id, "kind": "answer_draft",
                                       "question": question, "plan": plan, "draft": text,
                                       "writer": writer}, offset)

        approved, checks, words = self._stage(trace_id, "drafts", "reviewer", inject_failure,
                                              lambda: review(text))
        final = {"correlation_id": trace_id, "status": "approved" if approved else "rejected",
                 "answer": text, "question": question,
                 "review": {"checks": checks, "word_count": words, "reviewer": "direct",
                            "reviewed_at": tracing.iso(time.time())},
                 "plan_steps": steps, "writer": writer}
        self._emit(kcfg.FINAL_TOPIC, final, offset)
        now = time.time()
        tracing.write_span(trace_id, "final", now, now, "ok", None, agent="direct",
                           review_status=final["status"])
        return {"final": final, "start_offsets": None, "inbox": {"partition": 0, "offset": offset}}

    def close(self):
        pass


class FileMessageSource:
    """Evaluator input for DirectPipeline runs (same join on correlation_id)."""

    name = "file"
    TOPICS = {"plan": kcfg.TASKS_TOPIC, "draft": kcfg.DRAFTS_TOPIC, "final": kcfg.FINAL_TOPIC}

    def fetch(self, trace_ids, start_offsets=None, timeout=None):
        wanted = set(trace_ids)
        found = {t: {} for t in wanted}
        stats = {"source": "file (direct mode)", "scanned": 0, "malformed": 0,
                 "timed_out": False, "topics": dict(self.TOPICS)}
        role_of = {topic: role for role, topic in self.TOPICS.items()}
        if not os.path.exists(cfg.DIRECT_MESSAGES):
            return found, stats
        with open(cfg.DIRECT_MESSAGES, encoding="utf-8") as handle:
            for line in handle:
                stats["scanned"] += 1
                try:
                    record = json.loads(line)
                    value = record["value"]
                    tid = value.get("correlation_id")
                except (ValueError, KeyError, AttributeError, TypeError):
                    stats["malformed"] += 1
                    continue
                if tid in wanted and record.get("topic") in role_of:
                    found[tid][role_of[record["topic"]]] = record
        return found, stats


def make_pipeline(mode=None):
    mode = mode or cfg.PIPELINE_MODE
    if mode == "kafka":
        return KafkaPipeline()
    if mode == "direct":
        return DirectPipeline()
    raise ValueError(f"unknown pipeline mode {mode}")


def make_source(mode=None):
    mode = mode or cfg.PIPELINE_MODE
    return KafkaMessageSource() if mode == "kafka" else FileMessageSource()

"""Shared Kafka helpers for HW8 (kafka-python).

* make_producer / send_json      - JSON producer (acks=all), optional key for partitioning
* make_group_consumer            - consumer-group member, auto-commit OFF (we commit ourselves)
* TopicReader                    - group-less reader pinned to the end of a topic (for replies)
* ensure_topics                  - idempotent topic creation (also grows partitions)
* log / trace                    - console + RUN_LOG.txt lines with my name, JSONL trace events
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone

from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer, TopicPartition
from kafka.admin import NewPartitions, NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError

from . import config as cfg

# ----------------------------------------------------------------------------
# logging
# ----------------------------------------------------------------------------


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _local_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log(component, message):
    """Print one log line (my name is in every line for the screenshots) and append to RUN_LOG."""
    line = f"{_local_stamp()} | {cfg.STUDENT_NAME} | {cfg.PREFIX} | {component:<10} | {message}"
    print(line, flush=True)
    try:
        cfg.RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.RUN_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    return line


def trace(component, event, correlation_id, **detail):
    """Machine-readable event (raw/trace_events.jsonl) used to rebuild the message flow."""
    record = {"ts": now_iso(), "component": component, "event": event,
              "correlation_id": correlation_id, **detail}
    try:
        cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
        with open(cfg.TRACE_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
    except OSError:
        pass
    return record


def short(value, limit=400):
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def new_id():
    return str(uuid.uuid4())


# ----------------------------------------------------------------------------
# connection helpers
# ----------------------------------------------------------------------------


def wait_for_kafka(component="KAFKA", timeout=90):
    deadline = time.time() + timeout
    while True:
        try:
            admin = KafkaAdminClient(bootstrap_servers=cfg.BOOTSTRAP, client_id=f"{cfg.PREFIX}-probe")
            admin.close()
            return True
        except NoBrokersAvailable:
            if time.time() > deadline:
                log(component, f"Kafka not reachable at {cfg.BOOTSTRAP}")
                raise
            log(component, f"waiting for Kafka at {cfg.BOOTSTRAP} ...")
            time.sleep(3)


def ensure_topics(component="SETUP", topics=None):
    """Create the PREFIX topics if missing; make sure each has at least the configured partitions."""
    topics = topics or cfg.TOPICS
    admin = KafkaAdminClient(bootstrap_servers=cfg.BOOTSTRAP, client_id=f"{cfg.PREFIX}-admin")
    existing = set(admin.list_topics())
    for name, partitions in topics.items():
        if name not in existing:
            try:
                admin.create_topics([NewTopic(name=name, num_partitions=partitions,
                                              replication_factor=1)])
                log(component, f"created topic {name} (partitions={partitions})")
            except TopicAlreadyExistsError:
                pass
    probe = KafkaConsumer(bootstrap_servers=cfg.BOOTSTRAP)
    for name, partitions in topics.items():
        current = _partitions(probe, name)
        if len(current) < partitions:
            admin.create_partitions({name: NewPartitions(total_count=partitions)})
            log(component, f"grew topic {name} from {len(current)} to {partitions} partitions")
        else:
            log(component, f"topic ready {name} partitions={len(current)}")
    probe.close()
    admin.close()


def _partitions(consumer, topic, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        parts = consumer.partitions_for_topic(topic)
        if parts:
            return sorted(parts)
        consumer.topics()  # forces a metadata refresh
        time.sleep(0.5)
    return []


# ----------------------------------------------------------------------------
# producer
# ----------------------------------------------------------------------------


def make_producer():
    return KafkaProducer(bootstrap_servers=cfg.BOOTSTRAP, acks="all", retries=5, linger_ms=0)


def encode(value):
    return value if isinstance(value, (bytes, bytearray)) else json.dumps(value, default=str).encode()


def send_json(producer, topic, value, key=None, partition=None, timeout=15):
    """Send and wait for the broker ack; returns RecordMetadata(topic, partition, offset)."""
    key_bytes = key.encode() if isinstance(key, str) else key
    future = producer.send(topic, value=encode(value), key=key_bytes, partition=partition)
    metadata = future.get(timeout=timeout)
    producer.flush()
    return metadata


# ----------------------------------------------------------------------------
# consumers
# ----------------------------------------------------------------------------


def make_group_consumer(group_id, topics, offset_reset="earliest", client_id=None):
    """Consumer-group member. Auto-commit is OFF: callers commit only after successful work."""
    consumer = KafkaConsumer(
        bootstrap_servers=cfg.BOOTSTRAP,
        group_id=group_id,
        client_id=client_id or f"{group_id}-{uuid.uuid4().hex[:6]}",
        enable_auto_commit=False,
        auto_offset_reset=offset_reset,
        max_poll_records=1,
        session_timeout_ms=10000,
        heartbeat_interval_ms=3000,
        max_poll_interval_ms=300000,
    )
    consumer.subscribe(topics)
    return consumer


def decode(raw):
    """Bytes -> dict. Raises ValueError for anything that is not a JSON object (poison)."""
    if raw is None:
        raise ValueError("empty message value")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("message value must be a JSON object")
    return value


class TopicReader:
    """Group-less reader that starts at the current end of a topic (or at given offsets).

    The end position is resolved *before* returning, so anything sent afterwards is seen.
    """

    def __init__(self, topic, start_offsets=None):
        self.topic = topic
        self.consumer = KafkaConsumer(bootstrap_servers=cfg.BOOTSTRAP, group_id=None,
                                      enable_auto_commit=False)
        self.tps = [TopicPartition(topic, p) for p in _partitions(self.consumer, topic)]
        if not self.tps:
            raise RuntimeError(f"topic {topic} not found - run create_topics.py first")
        self.consumer.assign(self.tps)
        if start_offsets:
            for tp in self.tps:
                self.consumer.seek(tp, start_offsets.get(tp.partition, 0))
        else:
            self.consumer.seek_to_end(*self.tps)
        self.start = {tp.partition: self.consumer.position(tp) for tp in self.tps}

    def poll(self, timeout_ms=500):
        out = []
        for tp, records in self.consumer.poll(timeout_ms=timeout_ms).items():
            for record in records:
                out.append(record)
        return out

    def collect(self, until=None, timeout=30, idle_stop=None):
        """Read records until until(records) is true, timeout, or idle_stop seconds w/o data."""
        records, deadline, last = [], time.time() + timeout, time.time()
        while time.time() < deadline:
            batch = self.poll(500)
            if batch:
                records.extend(batch)
                last = time.time()
                if until and until(records):
                    break
            elif idle_stop and time.time() - last > idle_stop:
                break
        return records

    def close(self):
        self.consumer.close()


def record_json(record):
    try:
        return decode(record.value)
    except (ValueError, UnicodeDecodeError):
        return {"_raw": record.value.decode("utf-8", "replace") if record.value else None}


def end_offsets(topic):
    reader = TopicReader(topic)
    offsets = dict(reader.start)
    reader.close()
    return offsets


def group_committed(group_id, topic):
    """Committed offsets of a consumer group for one topic: {partition: offset or None}."""
    admin = KafkaAdminClient(bootstrap_servers=cfg.BOOTSTRAP, client_id=f"{cfg.PREFIX}-admin")
    try:
        offsets = admin.list_consumer_group_offsets(group_id)
    finally:
        admin.close()
    return {tp.partition: meta.offset for tp, meta in offsets.items() if tp.topic == topic}


def banner(component, title):
    log(component, "=" * 70)
    log(component, title)
    log(component, "=" * 70)


if __name__ == "__main__":  # pragma: no cover
    print("helper module - run create_topics.py, inspection_worker.py, planner.py ...")
    sys.exit(0)

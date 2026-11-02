"""Create every HW8 topic (idempotent) and print the equivalent kafka-topics CLI commands.

    python web_application/kafka_pipeline/create_topics.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.kafka_io import ensure_topics, log, wait_for_kafka  # noqa: E402

if __name__ == "__main__":
    wait_for_kafka("SETUP")
    log("SETUP", "equivalent CLI (inside the kafka container):")
    for topic, partitions in cfg.TOPICS.items():
        log("SETUP", f"  /opt/kafka/bin/kafka-topics.sh --create --if-not-exists --topic {topic} "
                     f"--partitions {partitions} --replication-factor 1 "
                     f"--bootstrap-server localhost:9092")
    ensure_topics("SETUP")

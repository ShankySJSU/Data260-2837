"""HW8 Part 2 - send one question to s2837_inbox and wait for the result on s2837_final.

    python send_question.py
    python send_question.py --question "What happens after a FAIL inspection?"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../code

from web_application.kafka_pipeline import config as cfg  # noqa: E402
from web_application.kafka_pipeline.kafka_io import (  # noqa: E402
    TopicReader, banner, log, make_producer, new_id, now_iso, record_json, send_json,
    wait_for_kafka,
)

COMPONENT = "SENDER"
DEFAULT_QUESTION = ("A restaurant just received a WARNING status with a score of 72 in its "
                    "health inspection. What should the owner do before the re-inspection?")


def ask(question, timeout=240, producer=None):
    reader = TopicReader(cfg.FINAL_TOPIC)  # positioned at the end BEFORE we send
    producer = producer or make_producer()
    correlation_id = new_id()
    message = {"correlation_id": correlation_id, "question": question, "sent_at": now_iso(),
               "source": "send_question.py"}
    meta = send_json(producer, cfg.INBOX_TOPIC, message, key=correlation_id)
    log(COMPONENT, f"SENT {cfg.INBOX_TOPIC}[p{meta.partition}@{meta.offset}] "
                   f"correlation_id={correlation_id} question={question!r}")
    log(COMPONENT, f"waiting for correlation_id={correlation_id} on {cfg.FINAL_TOPIC} ...")
    records = reader.collect(
        until=lambda rs: any(record_json(r).get("correlation_id") == correlation_id for r in rs),
        timeout=timeout)
    reader.close()
    finals = [record_json(r) for r in records if record_json(r).get("correlation_id") ==
              correlation_id]
    return message, (finals[0] if finals else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    wait_for_kafka(COMPONENT)
    banner(COMPONENT, f"HW8 Part 2 - {cfg.STUDENT_NAME} - inbox -> planner -> writer -> "
                      "reviewer -> final")
    message, final = ask(args.question, args.timeout)
    if final is None:
        log(COMPONENT, "no final message - are planner.py, writer.py and reviewer.py running?")
        return 1
    banner(COMPONENT, "MESSAGE JOURNEY (from the trace carried inside the messages)")
    log(COMPONENT, f"you     -> {cfg.INBOX_TOPIC:<14} at {message['sent_at']} "
                   f"correlation_id={message['correlation_id']}")
    nxt = {"planner": cfg.TASKS_TOPIC, "writer": cfg.DRAFTS_TOPIC, "reviewer": cfg.FINAL_TOPIC}
    for stage in final.get("trace", []):
        log(COMPONENT, f"{stage['stage']:<9}read {stage['topic']}[p{stage['partition']}@"
                       f"{stage['offset']}] at {stage['received_at']} -> {nxt[stage['stage']]} "
                       f"at {stage['finished_at']} ({stage['agent']}, pid {stage['pid']})")
    same = final["correlation_id"] == message["correlation_id"]
    log(COMPONENT, f"correlation_id preserved through every stage: {same}")
    banner(COMPONENT, f"FINAL JSON from {cfg.FINAL_TOPIC}")
    print(json.dumps(final, indent=2))
    cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
    (cfg.RAW_DIR / "part2_final.json").write_text(
        json.dumps({"inbox_message": message, "final": final}, indent=2), encoding="utf-8")
    log(COMPONENT, f"saved {cfg.RAW_DIR / 'part2_final.json'}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())

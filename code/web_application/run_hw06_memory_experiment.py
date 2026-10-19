"""Run the HW6 30-message short-term-memory comparison locally."""

import importlib
import json
import os
import uuid
from pathlib import Path

import memory_service

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "reports" / "hw06" / "raw"

CONVERSATION = [
    "My name is Shashank Ranjan.",
    "My SID4 is 2837.",
    "The required backend port is 8137.",
    "My project domain is restaurant inspections.",
    "The relational database is s2837_rel.",
    "The MongoDB database is s2837_doc.",
    "I use local MongoDB on localhost.",
    "I use qwen2.5:1.5b through local Ollama.",
    "The embedding model is all-MiniLM-L6-v2.",
    "The main domain entity is RestaurantInspection.",
] * 3

PROBES = [
    ("What is my SID4 and port?", ["2837", "8137"]),
    ("Which MongoDB database does HW6 use?", ["s2837_doc"]),
    ("What is my domain?", ["restaurant", "inspection"]),
    ("Which local model should I use?", ["qwen2.5:1.5b", "ollama"]),
    ("Which two memory systems are compared?", ["mongodb", "file"]),
]


def score_probe(text: str, expected: list[str]) -> int:
    normalized = text.lower()
    hits = sum(1 for term in expected if term.lower() in normalized)
    return max(1, min(5, 1 + hits * 2 if hits else 1))


def run_setting(short_term_n: int, compressed: bool = False) -> dict:
    os.environ["SHORT_TERM_N"] = str(short_term_n)
    os.environ["COMPRESSION_MAX_CHARS"] = "400" if compressed else "1000000"
    module = importlib.reload(memory_service)
    module.ensure_memory_indexes()
    user_id = f"hw6-exp-{short_term_n}-{'compressed' if compressed else 'baseline'}"
    session_id = str(uuid.uuid4())
    turns = []
    for message in CONVERSATION:
        result = module.process_chat(user_id, session_id, message)
        turns.append(result["cost"])

    probe_results = []
    for question, expected in PROBES:
        result = module.process_chat(user_id, session_id, question)
        probe_results.append({
            "question": question,
            "score": score_probe(result["reply"], expected),
            "reply": result["reply"],
        })

    return {
        "setting": "compression" if compressed else f"SHORT_TERM_N={short_term_n}",
        "short_term_n": short_term_n,
        "compressed": compressed,
        "mean_prompt_tokens": sum(item["prompt_tokens"] for item in turns) / len(turns),
        "mean_latency_ms": sum(item["latency_ms"] for item in turns) / len(turns),
        "probe_quality": sum(item["score"] for item in probe_results) / len(probe_results),
        "probe_results": probe_results,
    }


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_setting(n) for n in (4, 12, 30)]
    results.append(run_setting(30, compressed=True))
    output = RAW_DIR / "memory_experiment_results.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

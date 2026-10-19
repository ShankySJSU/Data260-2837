"""MongoDB-backed short-, long-, and episodic-memory services for HW6."""

from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from mongo_db import mongo_db, utc_now

MESSAGES = mongo_db["messages"]
SUMMARIES = mongo_db["summaries"]
EPISODES = mongo_db["episodes"]

SHORT_TERM_N = int(os.getenv("SHORT_TERM_N", "12"))
SUMMARIZE_EVERY_USER_MSGS = int(os.getenv("SUMMARIZE_EVERY_USER_MSGS", "5"))
EPISODE_TOP_K = int(os.getenv("EPISODE_TOP_K", "3"))
COMPRESSION_MAX_CHARS = int(os.getenv("COMPRESSION_MAX_CHARS", "400"))
OLLAMA_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

REPO_ROOT = Path(__file__).resolve().parents[2]
COST_LOG = REPO_ROOT / "reports" / "hw06" / "raw" / "chat_costs.jsonl"


def ensure_memory_indexes() -> None:
    MESSAGES.create_index([("user_id", 1), ("session_id", 1), ("created_at", -1)])
    MESSAGES.create_index([("user_id", 1), ("created_at", -1)])
    SUMMARIES.create_index([("user_id", 1), ("session_id", 1), ("scope", 1), ("created_at", -1)])
    EPISODES.create_index([("user_id", 1), ("created_at", -1)])


def _token_count(text: str) -> int:
    """Deterministic fallback count when Ollama does not return token metadata."""
    return len(re.findall(r"\w+|[^\w\s]", text or ""))


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def embed_text(text: str) -> list[float]:
    """Use the HW3 MiniLM model when available, with a deterministic local fallback."""
    try:
        from sentence_transformers import SentenceTransformer

        if not hasattr(embed_text, "_model"):
            embed_text._model = SentenceTransformer("all-MiniLM-L6-v2")
        vector = embed_text._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector.tolist()]
    except Exception:
        # This fallback keeps local smoke tests usable if the optional model is not
        # installed. Production runs should use sentence-transformers.
        size = 32
        vector = [0.0] * size
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            vector[hash(token) % size] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]


def call_ollama(messages: list[dict[str, str]], *, json_mode: bool = False) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": messages,
    }
    if json_mode:
        payload["format"] = "json"

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    body = response.json()
    content = body.get("message", {}).get("content", "")
    return content, body


def extract_episodes(user_message: str) -> list[dict[str, Any]]:
    prompt = (
        "Extract up to three durable, user-specific facts from the user's message. "
        "Return JSON only in the form {\"facts\":[{\"fact\":\"short fact\","
        "\"importance\":0.0}]}. Do not invent facts. Importance must be 0 to 1.\n"
        f"User message: {user_message}"
    )
    try:
        content, _ = call_ollama([{"role": "system", "content": prompt}], json_mode=True)
        data = json.loads(content)
        result = []
        for item in data.get("facts", [])[:3]:
            fact = str(item.get("fact", "")).strip()
            if fact:
                result.append({
                    "fact": fact[:300],
                    "importance": max(0.0, min(1.0, float(item.get("importance", 0.5)))),
                })
        return result
    except Exception:
        # A conservative fallback stores only explicit first-person statements.
        if re.search(r"\bI\s+(?:am|have|prefer|want|need|study|use|live|work)\b", user_message, re.I):
            return [{"fact": user_message.strip()[:300], "importance": 0.5}]
        return []


def summarize_messages(messages: list[dict[str, Any]]) -> str:
    transcript = "\n".join(
        f"{item.get('role', 'unknown')}: {item.get('content', '')}" for item in messages
    )
    prompt = (
        "Summarize the conversation into concise factual bullet points. Preserve user "
        "goals, preferences, decisions, and unresolved tasks. Do not invent details.\n\n"
        f"Conversation:\n{transcript}"
    )
    try:
        content, _ = call_ollama([{"role": "system", "content": prompt}])
        return content.strip()
    except Exception:
        return "\n".join(f"- {line}" for line in transcript.splitlines()[-8:])


def load_short_term(user_id: str, session_id: str, limit: int) -> list[dict[str, Any]]:
    docs = list(
        MESSAGES.find(
            {"user_id": user_id, "session_id": session_id},
            {"_id": 0, "role": 1, "content": 1, "created_at": 1},
        ).sort("created_at", -1).limit(limit)
    )
    window = list(reversed(docs))
    # HW6 compression policy: retain the recent window but cap each old message's
    # content length before it enters the prompt.
    for item in window:
        content = str(item.get("content", ""))
        if len(content) > COMPRESSION_MAX_CHARS:
            item["content"] = content[:COMPRESSION_MAX_CHARS] + " ...[compressed]"
    return window


def load_latest_summaries(user_id: str, session_id: str) -> dict[str, str | None]:
    session = SUMMARIES.find_one(
        {"user_id": user_id, "session_id": session_id, "scope": "session"},
        sort=[("created_at", -1)],
    )
    lifetime = SUMMARIES.find_one(
        {"user_id": user_id, "scope": "user"},
        sort=[("created_at", -1)],
    )
    return {
        "session": session.get("text") if session else None,
        "lifetime": lifetime.get("text") if lifetime else None,
    }


def retrieve_episodes(user_id: str, message: str, top_k: int = EPISODE_TOP_K) -> list[dict[str, Any]]:
    query_vector = embed_text(message)
    candidates = list(EPISODES.find({"user_id": user_id}, {"_id": 0}))
    scored = []
    for item in candidates:
        scored.append({**item, "similarity": _cosine(query_vector, item.get("embedding", []))})
    scored.sort(key=lambda item: (item["similarity"], item.get("importance", 0.0)), reverse=True)
    return scored[:top_k]


def maybe_summarize(user_id: str, session_id: str) -> None:
    user_count = MESSAGES.count_documents({"user_id": user_id, "session_id": session_id, "role": "user"})
    if user_count == 0 or user_count % SUMMARIZE_EVERY_USER_MSGS != 0:
        return

    recent = list(
        MESSAGES.find({"user_id": user_id, "session_id": session_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(20)
    )
    text = summarize_messages(list(reversed(recent)))
    SUMMARIES.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "scope": "session",
        "text": text,
        "created_at": utc_now(),
    })

    session_summaries = list(
        SUMMARIES.find({"user_id": user_id, "scope": "session"}, {"_id": 0, "text": 1})
        .sort("created_at", -1)
        .limit(10)
    )
    if len(session_summaries) >= 2:
        lifetime_text = summarize_messages([
            {"role": "summary", "content": item["text"]} for item in reversed(session_summaries)
        ])
        SUMMARIES.insert_one({
            "user_id": user_id,
            "session_id": None,
            "scope": "user",
            "text": lifetime_text,
            "created_at": utc_now(),
        })


def assemble_prompt(user_id: str, session_id: str, current_message: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    short_term = load_short_term(user_id, session_id, SHORT_TERM_N)
    summaries = load_latest_summaries(user_id, session_id)
    episodes = retrieve_episodes(user_id, current_message)

    short_text = "\n".join(f"{m['role']}: {m['content']}" for m in short_term) or "(none)"
    episode_text = "\n".join(f"- {e['fact']}" for e in episodes) or "(none)"
    system = (
        "You are a careful local study assistant. Use the supplied memory as context, "
        "but do not claim facts that are not supported. Be concise and helpful.\n\n"
        f"Lifetime summary:\n{summaries['lifetime'] or '(none)'}\n\n"
        f"Session summary:\n{summaries['session'] or '(none)'}\n\n"
        f"Relevant episodic facts:\n{episode_text}\n\n"
        f"Short-term conversation:\n{short_text}"
    )
    prompt_messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": current_message},
    ]
    used = {
        "short_term": short_term,
        "long_term_summary": summaries,
        "episodic_facts": episodes,
        "system_primer_tokens": _token_count(system.split("Lifetime summary:", 1)[0]),
        "long_term_tokens": _token_count((summaries["lifetime"] or "") + (summaries["session"] or "")),
        "short_term_tokens": _token_count(short_text),
        "episodic_tokens": _token_count(episode_text),
    }
    return prompt_messages, used


def log_cost(record: dict[str, Any]) -> None:
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def process_chat(user_id: str, session_id: str | None, message: str) -> dict[str, Any]:
    session_id = session_id or str(uuid.uuid4())
    now = utc_now()
    MESSAGES.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": "user",
        "content": message,
        "created_at": now,
    })

    prompt_messages, used = assemble_prompt(user_id, session_id, message)
    started = datetime.now(timezone.utc)
    content, metadata = call_ollama(prompt_messages)
    elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
    reply = content.strip()

    MESSAGES.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "content": reply,
        "created_at": utc_now(),
    })

    for episode in extract_episodes(message):
        EPISODES.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "fact": episode["fact"],
            "importance": episode["importance"],
            "embedding": embed_text(episode["fact"]),
            "created_at": utc_now(),
        })
    maybe_summarize(user_id, session_id)

    prompt_tokens = int(metadata.get("prompt_eval_count") or _token_count("\n".join(m["content"] for m in prompt_messages)))
    completion_tokens = int(metadata.get("eval_count") or _token_count(reply))
    log_cost({
        "timestamp": utc_now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": round(elapsed_ms, 2),
        "system_primer_tokens": used["system_primer_tokens"],
        "long_term_tokens": used["long_term_tokens"],
        "short_term_tokens": used["short_term_tokens"],
        "episodic_tokens": used["episodic_tokens"],
        "short_term_n": SHORT_TERM_N,
    })

    return {
        "session_id": session_id,
        "reply": reply,
        "used": used,
        "cost": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": round(elapsed_ms, 2),
        },
    }

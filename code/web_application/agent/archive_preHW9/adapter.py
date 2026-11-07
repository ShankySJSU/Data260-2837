"""HW1 model adapter (local Ollama), reused by the HW7 agent loop.

Same model settings for every run: temperature 0 and seed = SID4 (2837).
"""

import os

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
SEED = 2837
TEMPERATURE = 0


def chat(messages, model=None, json_mode=True, timeout=120, temperature=None, seed=None):
    """Send chat messages to Ollama.

    Returns {"content": str, "prompt_tokens": int, "completion_tokens": int}.
    """
    payload = {
        "model": model or MODEL_NAME,
        "stream": False,
        "messages": messages,
        "options": {
            "temperature": TEMPERATURE if temperature is None else temperature,
            "seed": SEED if seed is None else seed,
        },
    }
    if json_mode:
        payload["format"] = "json"

    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    return {
        "content": data["message"]["content"],
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "completion_tokens": int(data.get("eval_count") or 0),
    }

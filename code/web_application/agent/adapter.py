import json
import requests

# ----------------------------------------------------
# HW1 Model Adapter (Generalized for HW7)
# ----------------------------------------------------
# This adapter assumes an Ollama-compatible local model.
# Modify the URL or payload shape if you use a different backend.
# ----------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"  # Your default local model


def call_model(messages, json_mode=False):
    """
    messages: list of {role, content}
    json_mode: instruct model to output JSON only (for tool calls)
    """
    prompt = ""
    for m in messages:
        prompt += f"{m['role']}: {m['content']}\n"

    if json_mode:
        prompt += "\nRespond ONLY with valid JSON.\n"

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()

    text = response.json().get("response", "")

    # Try parsing JSON output (for tool calls)
    if json_mode:
        try:
            parsed = json.loads(text)
            return parsed, text
        except Exception:
            return None, text

    return text
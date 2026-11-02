"""Model calls for the Planner and Writer.

HW8_LLM=ollama   (default) -> HW1 adapter, local Ollama qwen2.5:1.5b, temperature 0, seed 2837
HW8_LLM=template           -> deterministic text (used by the failure tests / smoke test so
                              they measure Kafka behaviour, not model speed)
If Ollama is unreachable the call falls back to the template and says so in the log.
"""

import json
import os

from .kafka_io import log

MODE = os.getenv("HW8_LLM", "ollama").lower()
_warned = {"done": False}


def model_label():
    if MODE == "template":
        return "template (deterministic)"
    from web_application.agent.adapter import MODEL_NAME
    return f"ollama:{MODEL_NAME} (temperature 0, seed 2837)"


def _chat(messages, json_mode, component):
    if MODE == "template":
        return None
    try:
        from web_application.agent.adapter import chat
        return chat(messages, json_mode=json_mode, timeout=180)["content"]
    except Exception as exc:  # network / model errors -> deterministic fallback
        if not _warned["done"]:
            log(component, f"Ollama unavailable ({type(exc).__name__}: {exc}); using template")
            _warned["done"] = True
        return None


def plan(question, component="PLANNER"):
    """Return (steps, model_used)."""
    content = _chat([
        {"role": "system", "content": "You plan answers about local restaurant health "
                                      "inspections. Reply ONLY with JSON: "
                                      '{"steps": ["step 1", "step 2", "step 3"]} '
                                      "(3 to 5 short, concrete steps)."},
        {"role": "user", "content": question},
    ], True, component)
    if content:
        try:
            steps = json.loads(content).get("steps")
            steps = [str(s).strip() for s in steps if str(s).strip()][:5]
            if len(steps) >= 2:
                return steps, model_label()
        except (ValueError, AttributeError, TypeError):
            log(component, "model returned unusable plan JSON; using template plan")
    return [
        "Identify what the inspection status or rule in the question means",
        "List the concrete corrective actions the restaurant should take",
        "Explain how to verify the fixes before the next inspection",
    ], "template"


def write(question, steps, component="WRITER"):
    """Return (draft_text, model_used)."""
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    content = _chat([
        {"role": "system", "content": "You are a food-safety assistant for local restaurant "
                                      "inspections. Write a clear answer of 80-200 words that "
                                      "follows the plan steps in order. Plain text only."},
        {"role": "user", "content": f"Question: {question}\nPlan:\n{numbered}"},
    ], False, component)
    if content and content.strip():
        return content.strip(), model_label()
    lines = [f"Answer to: {question}"]
    for i, step in enumerate(steps, 1):
        lines.append(f"Step {i} - {step}: the restaurant inspection team reviews this item, "
                     "records the finding, and the owner fixes it before the re-inspection.")
    lines.append("Following these steps keeps the restaurant inspection score high and "
                 "avoids a FAIL status at the next visit.")
    return "\n".join(lines), "template"

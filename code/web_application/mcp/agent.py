import json
import os
from pathlib import Path
from typing import Any

import requests

from execute_tool import execute_tool


# ============================================================
# PATHS AND CONFIGURATION
# ============================================================

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_LOG_PATH = (
    REPO_ROOT
    / "reports"
    / "hw05"
    / "raw"
    / "agent_runs.jsonl"
)

OLLAMA_URL = "http://localhost:11434/api/chat"

DEFAULT_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:1.5b",
)


# ============================================================
# TOOL DESCRIPTION FOR THE MODEL
# ============================================================

TOOL_DESCRIPTION = """
The available domain tools are:

1. search
Input:
{
  "query": "string",
  "limit": "integer from 1 to 25"
}

2. detail_lookup
Input:
{
  "inspection_id": "positive integer"
}

3. aggregate
Input:
{
  "status": "PASS, FAIL, WARNING, or omitted"
}

The model must respond with exactly one JSON object.

For a tool call:

{
  "action": "tool",
  "tool_name": "search",
  "inputs": {
    "query": "Rangoli",
    "limit": 5
  }
}

For a final answer:

{
  "action": "final",
  "answer": "The answer for the user."
}
"""


# ============================================================
# MODEL ADAPTERS
# ============================================================

class MockModel:
    """
    Deterministic model used for offline tests.
    """

    def __init__(
        self,
        actions: list[dict[str, Any]],
    ):
        self.actions = actions
        self.position = 0

    def next_action(
        self,
        user_input: str,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.position >= len(self.actions):
            return {
                "action": "final",
                "answer": "Mock model completed.",
            }

        action = self.actions[self.position]
        self.position += 1

        return action


class OllamaModel:
    """
    Local Ollama model adapter.

    Ollama must be running on localhost:11434.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
    ):
        self.model_name = model_name

    def next_action(
        self,
        user_input: str,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        history_text = json.dumps(
            history,
            indent=2,
        )

        system_prompt = f"""
You are a careful restaurant-inspection assistant.

{TOOL_DESCRIPTION}

Rules:
- Use only the tools listed above.
- Do not invent database results.
- Return JSON only.
- After receiving a tool result, either call another tool
  or return a final answer.
  When returning a final answer, summarize the actual tool results.
Include relevant inspection IDs, inspection codes, statuses, scores,
restaurant names, and dates. Do not return only a title or introduction.
Do not call the same detail_lookup tool with the same inspection_id
more than once unless the previous call returned an error.
"""

        user_prompt = f"""
User request:
{user_input}

Previous agent history:
{history_text}
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": self.model_name,
                "stream": False,
                "format": "json",
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            },
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        content = payload["message"]["content"]

        return json.loads(content)


# ============================================================
# LOGGING
# ============================================================

def append_log(
    log_path: Path,
    record: dict[str, Any],
):
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with log_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                sort_keys=True,
            )
            + "\n"
        )


# ============================================================
# AGENT LOOP
# ============================================================


def run_agent(
    user_input: str,
    model=None,
    max_steps: int = 5,
    tool_executor=execute_tool,
    log_path: Path = DEFAULT_LOG_PATH,
) -> dict[str, Any]:
    """
    Run an agent loop with a bounded number of steps.

    The agent can call only execute_tool.
    """

    if model is None:
        model = OllamaModel()

    if max_steps < 1:
        raise ValueError(
            "max_steps must be at least 1"
        )

    history = []
    tool_call_count = 0
    final_answer = None
    stop_reason = "max_steps"
    completed_steps = 0

    for step in range(1, max_steps + 1):
        completed_steps = step

        try:
            action = model.next_action(
                user_input=user_input,
                history=history,
            )

        except Exception as exc:
            stop_reason = "model_error"

            append_log(
                log_path,
                {
                    "event": "agent_stop",
                    "step": step,
                    "stop_reason": stop_reason,
                    "error": str(exc),
                },
            )

            return {
                "answer": None,
                "steps": step,
                "tool_calls": tool_call_count,
                "stop_reason": stop_reason,
            }

        append_log(
            log_path,
            {
                "event": "model_action",
                "step": step,
                "action": action,
            },
        )

        history.append(
            {
                "step": step,
                "action": action,
            }
        )

        if not isinstance(action, dict):
            stop_reason = "invalid_model_output"
            final_answer = None
            break

        action_type = action.get("action")

        if action_type == "final":
            final_answer = action.get(
                "answer",
                "",
            )

            stop_reason = "normal_completion"
            break

        if action_type != "tool":
            stop_reason = "invalid_model_action"
            final_answer = None
            break

        tool_name = action.get("tool_name")
        inputs = action.get("inputs", {})

        tool_call_count += 1

        append_log(
            log_path,
            {
                "event": "tool_call",
                "step": step,
                "tool_name": tool_name,
                "inputs": inputs,
            },
        )

        try:
            raw_tool_result = tool_executor(
                tool_name,
                inputs,
            )

            tool_result = json.loads(
                raw_tool_result
            )

        except Exception as exc:
            tool_result = {
                "ok": False,
                "data": None,
                "error": str(exc),
            }

        append_log(
            log_path,
            {
                "event": "tool_result",
                "step": step,
                "tool_name": tool_name,
                "inputs": inputs,
                "result": tool_result,
            },
        )

        history.append(
            {
                "step": step,
                "tool_name": tool_name,
                "inputs": inputs,
                "result": tool_result,
            }
        )

        if not tool_result.get("ok", False):
            error_message = tool_result.get(
                "error",
                "tool failed",
            )

            if "Safety rule blocked" in error_message:
                stop_reason = (
                    "safety_rule_blocked"
                )

                final_answer = None
                break

            # Normal validation errors are given back
            # to the model so it can correct the input.
            history.append(
                {
                    "step": step,
                    "tool_error": error_message,
                    "instruction": (
                        "Correct the input and try again."
                    ),
                }
            )

            continue

    run_summary = {
        "answer": final_answer,
        "steps": completed_steps,
        "tool_calls": tool_call_count,
        "stop_reason": stop_reason,
    }

    append_log(
        log_path,
        {
            "event": "agent_stop",
            "step": completed_steps,
            "stop_reason": stop_reason,
            "tool_calls": tool_call_count,
            "final_answer": final_answer,
        },
    )

    return run_summary


# ============================================================
# MANUAL LOCAL RUN
# ============================================================

if __name__ == "__main__":
    result = run_agent(
        "Find inspections for Rangoli.",
        max_steps=5,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )
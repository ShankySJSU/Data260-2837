"""HW7 smoke test. Start the backend first, then run from the code folder:

    python -m web_application.verify_hw07

Writes reports/hw07/verification.json. It only calls the running API and creates (then
deletes) one temporary restaurant; it never modifies application code.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = os.getenv("HW7_BASE_URL", "http://localhost:8137")
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "reports" / "hw07" / "verification.json"
SID4 = 2837
MODEL = "qwen2.5:1.5b (local Ollama)"
checks = []


def check(name, fn):
    try:
        passed = bool(fn())
        checks.append({"check": name, "status": "PASS" if passed else "FAIL"})
    except Exception as exc:
        checks.append({"check": name, "status": "FAIL", "error": str(exc)})


def login(username):
    reply = requests.post(f"{BASE_URL}/auth/login",
                          json={"username": username, "password": "test123"}, timeout=10)
    return reply.json().get("token") if reply.status_code == 200 else None


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def scripted_model(messages):
    """Deterministic stand-in for the LLM: search, detail of the first id, final answer."""
    tool_messages = [m for m in messages if m["role"] == "tool"]
    if not tool_messages:
        action = {"action": "tool", "tool_name": "search", "inputs": {"query": "Rangoli"}}
    elif len(tool_messages) == 1:
        first = json.loads(tool_messages[0]["content"])["data"][0]["id"]
        inputs = {"inspection_id": first}
        action = {"action": "tool", "tool_name": "detail_lookup", "inputs": inputs}
    else:
        action = {"action": "final", "answer": "Looked up the first Rangoli inspection."}
    return {"content": json.dumps(action), "prompt_tokens": 0, "completion_tokens": 0}


def agent_loop_completes():
    from web_application.agent.agent_loop import run_agent

    result = run_agent("Search Rangoli then look up the first result.", model=scripted_model,
                       required_tools=("search", "detail_lookup"), echo=False)
    return result["stop_reason"] == "success" and result["tool_calls"] == 2


def safety_gate_blocks():
    from web_application.security.safety_gate import confirm_bash

    blocked = ["rm -rf /", "sudo rm -rf *", "echo hi; rm -fr x", "cat a >/etc/passwd"]
    return all(not confirm_bash(c)["allowed"] for c in blocked) and confirm_bash("ls -l")["allowed"]


def api_checks():
    tokens = {name: login(name) for name in ("reader1", "writer1", "mod1")}
    check("backend_running", lambda: requests.get(f"{BASE_URL}/", timeout=10).status_code == 200)
    check("login_valid_returns_token", lambda: all(tokens.values()))
    check("login_invalid_returns_401", lambda: requests.post(
        f"{BASE_URL}/auth/login", json={"username": "mod1", "password": "wrong"},
        timeout=10).status_code == 401)
    check("auth_me_without_token_401",
          lambda: requests.get(f"{BASE_URL}/auth/me", timeout=10).status_code == 401)
    check("auth_me_returns_identity_and_role", lambda: {"username", "role"} <= set(requests.get(
        f"{BASE_URL}/auth/me", headers=auth(tokens["mod1"]), timeout=10).json()))
    check("reader_can_list_200", lambda: requests.get(
        f"{BASE_URL}/restaurants/", headers=auth(tokens["reader1"]), timeout=10).status_code == 200)
    body = {"name": "Smoke Test Cafe", "address": "1 Test Street",
            "permit_code": f"SMK-{int(time.time())}"}
    check("reader_create_forbidden_403", lambda: requests.post(
        f"{BASE_URL}/restaurants/", json=body, headers=auth(tokens["reader1"]),
        timeout=10).status_code == 403)
    created = {}

    def writer_create():
        reply = requests.post(f"{BASE_URL}/restaurants/", json=body,
                              headers=auth(tokens["writer1"]), timeout=10)
        created["id"] = reply.json().get("id")
        return reply.status_code == 201

    check("writer_create_201", writer_create)
    check("writer_delete_forbidden_403", lambda: requests.delete(
        f"{BASE_URL}/restaurants/{created['id']}", headers=auth(tokens["writer1"]),
        timeout=10).status_code == 403)
    check("moderator_delete_succeeds", lambda: requests.delete(
        f"{BASE_URL}/restaurants/{created['id']}", headers=auth(tokens["mod1"]),
        timeout=10).status_code in (200, 204))


def commit_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                       text=True).strip()
    except Exception:
        return "unknown"


def main():
    api_checks()
    check("agent_loop_completes_verification_task", agent_loop_completes)
    check("safety_gate_blocks_destructive_commands", safety_gate_blocks)
    report = {
        "homework": "HW7", "sid4": SID4, "commit_hash": commit_hash(), "model": MODEL,
        "seed": SID4, "verify_seed": 260000 + SID4,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": checks,
        "summary": f"{sum(c['status'] == 'PASS' for c in checks)}/{len(checks)} passed",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

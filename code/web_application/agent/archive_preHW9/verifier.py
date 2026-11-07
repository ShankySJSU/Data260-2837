"""Deterministic verifier for the three fixed tasks (no model involved).

verify_task checks the tool log and the final answer against the tool observations.
"""

import json
import re

MAX_SHOWN = 300


def _numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def _ok_calls(result, tool):
    return [e for e in result["tool_log"] if e["tool"] == tool and e["ok"]]


def _records(result):
    """All inspection records seen in search results and detail lookups."""
    records = []
    for entry in result["tool_log"]:
        data = entry.get("data")
        if not entry["ok"]:
            continue
        if entry["tool"] == "search" and isinstance(data, list):
            records.extend(r for r in data if isinstance(r, dict))
        elif entry["tool"] == "detail_lookup" and isinstance(data, dict):
            records.append(data)
    return records


def _mentions(answer, record):
    code = str(record.get("inspection_code", ""))
    pattern = rf"(?<![\d.]){record.get('id')}(?![\d.])"
    return (code and code in answer) or re.search(pattern, answer) is not None


def unsupported_numbers(answer, result, prompt):
    """Numbers in the answer that appear in no tool observation, input or the task prompt."""
    allowed = _numbers(prompt)
    for entry in result["tool_log"]:
        allowed |= _numbers(json.dumps(entry.get("data"))) | _numbers(json.dumps(entry["inputs"]))
        if isinstance(entry.get("data"), list):
            allowed.add(str(len(entry["data"])))
    return sorted(n for n in _numbers(answer) if n not in allowed)


def _verdict(passed, reason, **evidence):
    return {"passed": passed, "reason": reason, "evidence": evidence}


def _check(task_id, result, answer):
    searches = [e for e in _ok_calls(result, "search") if e["data"]]
    details = _ok_calls(result, "detail_lookup")
    records = _records(result)

    if task_id == "A":
        if not searches:
            return _verdict(False, "no successful search with results")
        first = searches[0]["data"][0]
        ids = [e["inputs"].get("inspection_id") for e in details]
        if first["id"] not in ids:
            return _verdict(False, f"detail_lookup was not called for the first result "
                            f"id {first['id']}", looked_up=ids)
        if not _mentions(answer, first):
            return _verdict(False, "answer does not mention the first result",
                            answer_text_check=True, first_id=first["id"])
        return _verdict(True, "search then detail of first result, answer cites it")

    if task_id == "B":
        aggs = _ok_calls(result, "aggregate")
        if not aggs:
            return _verdict(False, "aggregate was not called successfully")
        count = aggs[-1]["data"]["counts_by_status"]["FAIL"]
        if not re.search(rf"(?<![\d.]){count}(?![\d.])", answer):
            return _verdict(False, f"answer does not state the FAIL count {count}",
                            answer_text_check=True, fail_count=count)
        examples = [r for r in records if str(r.get("status", "")).upper() == "FAIL"]
        if not any(_mentions(answer, r) for r in examples):
            return _verdict(False, "answer cites no FAIL example seen in the tool results",
                            answer_text_check=True)
        return _verdict(True, "aggregate count and a supporting FAIL example are cited")

    if task_id == "C":
        ids = list(dict.fromkeys(e["inputs"].get("inspection_id") for e in details))
        if len(ids) < 2:
            return _verdict(False, f"need two distinct detail lookups, saw {ids}")
        seen = {r.get("id"): r for r in records}
        cited = [i for i in ids if i in seen and _mentions(answer, seen[i])]
        if len(cited) < 2:
            return _verdict(False, "answer does not cite both inspections",
                            answer_text_check=True, looked_up=ids)
        return _verdict(True, "two distinct lookups, both cited in the comparison")

    return _verdict(False, f"unknown task {task_id}")


def verify_task(task_id, result, prompt=""):
    answer = result.get("answer") or ""
    if result["stop_reason"] != "success" or not answer.strip():
        verdict = _verdict(False, f"run ended with {result['stop_reason']}, no final answer")
    else:
        verdict = _check(task_id, result, answer)
    verdict["unsupported_numbers"] = unsupported_numbers(answer, result, prompt) if answer else []
    return verdict

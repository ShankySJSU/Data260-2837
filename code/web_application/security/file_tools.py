"""HW7 Part 6: file tools and bash behind the safety gate.

Every tool returns {"success", "data", "error", "source", "ts"}. Run tests only inside a
temporary sandbox directory.
"""

import difflib
import glob
import os
import re
from datetime import datetime, timezone

from web_application.security.safety_gate import confirm_bash


def _result(source, data=None, error=None):
    return {"success": error is None, "data": data, "error": error, "source": source,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def read_file(path, max_lines=200):
    """Read at most max_lines lines."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()[:max_lines]
        return _result(path, "".join(lines))
    except OSError as exc:
        return _result(path, error=str(exc))


def write_file(path, content):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return _result(path, f"wrote {len(content)} chars")
    except OSError as exc:
        return _result(path, error=str(exc))


def edit_file(path, old_text, new_text):
    """Replace one occurrence of old_text and return a short unified diff."""
    try:
        with open(path, encoding="utf-8") as handle:
            before = handle.read()
        if before.count(old_text) != 1:
            return _result(path, error=f"old_text must match exactly once, found "
                                       f"{before.count(old_text)}")
        after = before.replace(old_text, new_text)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(after)
        diff = difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                    "before", "after", n=1)
        return _result(path, {"diff": "".join(diff)})
    except OSError as exc:
        return _result(path, error=str(exc))


def glob_files(pattern, directory="."):
    """Return file paths matching a glob pattern inside directory (recursive with **)."""
    matches = sorted(glob.glob(os.path.join(directory, pattern), recursive=True))
    return _result(pattern, [os.path.relpath(m, directory) for m in matches])


def search_in_files(regex, directory=".", file_pattern="*"):
    """Search file contents with a regex; file_pattern limits which files are searched."""
    try:
        compiled = re.compile(regex)
    except re.error as exc:
        return _result(regex, error=f"bad regex: {exc}")
    hits = []
    for path in sorted(glob.glob(os.path.join(directory, "**", file_pattern), recursive=True)):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                for number, line in enumerate(handle, start=1):
                    if compiled.search(line):
                        hits.append({"file": os.path.relpath(path, directory), "line": number,
                                     "text": line.rstrip()})
        except (OSError, UnicodeDecodeError):
            continue
    return _result(regex, hits)


def bash(command, auto_approve=False):
    """Check a command with the safety gate. The command is only approved, never executed."""
    verdict = confirm_bash(command, auto_approve=auto_approve)
    if verdict["allowed"]:
        return _result("bash", {"command": command, "reason": verdict["reason"]})
    return _result("bash", error=verdict["reason"])

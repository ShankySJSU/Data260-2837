import os
import glob
from datetime import datetime
from difflib import unified_diff

from web_application.security.safety_gate import confirm_bash


def _ts():
    return datetime.utcnow().isoformat()


# -------------------------------------------------------------
# read_file
# -------------------------------------------------------------
def read_file(path: str, max_lines: int = 200):
    """
    Read up to max_lines from a text file.
    Returns standard HW7 tool schema.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        return {
            "success": True,
            "data": "".join(lines[:max_lines]),
            "error": None,
            "source": path,
            "ts": _ts(),
        }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "source": path,
            "ts": _ts(),
        }


# -------------------------------------------------------------
# write_file
# -------------------------------------------------------------
def write_file(path: str, content: str):
    """
    Overwrite file content.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "data": f"Wrote {len(content)} chars",
            "error": None,
            "source": path,
            "ts": _ts(),
        }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "source": path,
            "ts": _ts(),
        }


# -------------------------------------------------------------
# edit_file
# -------------------------------------------------------------
def edit_file(path: str, new_content: str):
    """
    Replace file content and return small diff (HW7 requirement).
    """
    try:
        old_text = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                old_text = f.read()

        diff = list(
            unified_diff(
                old_text.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="before",
                tofile="after",
            )
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {
            "success": True,
            "data": {"diff": "".join(diff)},
            "error": None,
            "source": path,
            "ts": _ts(),
        }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "source": path,
            "ts": _ts(),
        }


# -------------------------------------------------------------
# glob_files
# -------------------------------------------------------------
def glob_files(pattern: str):
    """
    Return a list of file paths matching a pattern.
    """
    try:
        matches = glob.glob(pattern)
        return {
            "success": True,
            "data": matches,
            "error": None,
            "source": pattern,
            "ts": _ts(),
        }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "source": pattern,
            "ts": _ts(),
        }


# -------------------------------------------------------------
# search_in_files
# -------------------------------------------------------------
def search_in_files(pattern: str, text: str):
    """
    Search for substring in all files matching pattern.
    Returns file paths where a match occurs.
    """
    try:
        matches = []
        for path in glob.glob(pattern):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if text in f.read():
                        matches.append(path)
            except Exception:
                continue

        return {
            "success": True,
            "data": matches,
            "error": None,
            "source": pattern,
            "ts": _ts(),
        }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "source": pattern,
            "ts": _ts(),
        }


# -------------------------------------------------------------
# bash (with safety gate)
# -------------------------------------------------------------
def bash(command: str, auto_approve: bool = False):
    """
    Route shell commands through safety gate.
    """
    result = confirm_bash(command, auto_approve=auto_approve)

    return {
        "success": result["allowed"],
        "data": None if not result["allowed"] else "Command permitted",
        "error": None if result["allowed"] else result["reason"],
        "source": "bash",
        "ts": _ts(),
    }
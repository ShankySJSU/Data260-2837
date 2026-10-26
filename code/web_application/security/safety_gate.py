import re

# Allow-list: a command is only auto-allowed if it starts with one of these.
SAFE_PREFIXES = ["echo ", "cat ", "ls", "python3 ", "pip list"]

# Shell metacharacters that can chain or smuggle a second command.
_CHAIN = re.compile(r"[;&|`<>]|\$\(|\n")

# Independent deny-list (checked first, regardless of SAFE_PREFIXES).
_DENY = [
    r"\brm\b[^;&|]*\s-[a-z]*r",             # recursive delete: -r -rf -fr -R
    r"\brm\b[^;&|]*--recursive",
    r"\b(sudo|su|doas)\b",                  # privilege escalation
    r"\b(chmod|chown|chgrp|setfacl)\b",     # permission / ownership changes
    r"\bdd\b[^;&|]*(\bof=|/dev/)",         # dd against raw devices
    r">+\s*/dev/(sd|nvme|hd|disk)",         # redirect to a raw device
    r"\bmkfs(\.\w+)?\b|\bmkswap\b|\bfdisk\b|\bparted\b",   # filesystem creation
    r">>?\s*/(?!tmp/)",                     # redirect to a root path
    r"\btee\b[^;&|]*\s/(?!tmp/)",
    r"\bshutil\.rmtree\b|\bos\.(remove|rmdir)\b",
]


def is_destructive(command: str) -> bool:
    """True if the command matches any destructive pattern (deny-list)."""
    cmd = command.lower()
    return any(re.search(p, cmd) for p in _DENY)


def confirm_bash(command: str, auto_approve: bool = False) -> dict:
    """Return {"allowed": bool, "reason": str}. Pure Python, no model needed."""
    cmd = command.strip()
    if is_destructive(cmd):
        if auto_approve:
            return {"allowed": True, "reason": "Destructive command explicitly confirmed."}
        return {"allowed": False, "reason": "Destructive command blocked; confirmation required."}
    if _CHAIN.search(cmd):
        if auto_approve:
            return {"allowed": True, "reason": "Chained/redirected command explicitly confirmed."}
        return {"allowed": False, "reason": "Shell chaining/redirection needs confirmation."}
    if any(cmd == p.strip() or cmd.startswith(p) for p in SAFE_PREFIXES):
        return {"allowed": True, "reason": "Matches SAFE_PREFIXES."}
    return {"allowed": False, "reason": "Not in SAFE_PREFIXES."}

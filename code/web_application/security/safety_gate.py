import re


# -------------------------------------------------------------
# SAFE PREFIXES
# -------------------------------------------------------------
SAFE_PREFIXES = [
    "echo ",
    "cat ",
    "ls ",
    "python3 ",
    "pip list",
]


# -------------------------------------------------------------
# is_destructive
# -------------------------------------------------------------
def is_destructive(cmd: str) -> bool:
    """
    Deny-list check for destructive commands.
    """
    destructive_patterns = [
        r"rm -rf",
        r"rm -r",
        r"sudo",
        r"chmod ",
        r"chown ",
        r"dd if=",
        r"mkfs",
        r"mount ",
        r"umount ",
        r"> /",         # Redirect to root paths
        r"cp /",
        r"mv /",
    ]

    cmd_lower = cmd.lower()

    for pat in destructive_patterns:
        if re.search(pat, cmd_lower):
            return True

    return False


# -------------------------------------------------------------
# confirm_bash
# -------------------------------------------------------------
def confirm_bash(cmd: str, auto_approve: bool = False):
    """
    HW7 safety-gate rules:

      1. If destructive -> block unless auto_approve=True
      2. If non-destructive:
            must match a SAFE_PREFIX
            else reject
    """

    cmd = cmd.strip()

    # Rule 1 — destructive commands blocked
    if is_destructive(cmd):
        if not auto_approve:
            return {
                "allowed": False,
                "reason": "Destructive command blocked by safety gate."
            }
        else:
            return {
                "allowed": True,
                "reason": "Destructive command explicitly approved (unsafe)."
            }

    # Rule 2 — must start with SAFE_PREFIXES
    if any(cmd.startswith(prefix) for prefix in SAFE_PREFIXES):
        return {
            "allowed": True,
            "reason": "Command allowed by SAFE_PREFIXES."
        }

    return {
        "allowed": False,
        "reason": "Command not in SAFE_PREFIXES."
    }
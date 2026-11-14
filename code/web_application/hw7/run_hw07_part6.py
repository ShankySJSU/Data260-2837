"""HW7 Part 6 test run: glob -> search -> read integration test and the 10-command gate test.

Run from the code folder:  python -m web_application.run_hw07_part6
Everything file-related happens in a temporary sandbox directory.
"""

import re
import sys
import tempfile
from pathlib import Path

from web_application.run_hw07_part2 import RAW_DIR, RUN_LOG, Tee, stamp
from web_application.security.file_tools import glob_files, read_file, search_in_files, write_file
from web_application.security.safety_gate import confirm_bash, is_destructive

SHOULD_PASS = ["echo hello", "ls -l", "cat a.txt", "python3 script.py", "pip list"]
SHOULD_BLOCK = ["rm -rf /", "sudo rm -rf *", "chmod 777 secret.txt", "dd if=/dev/sda",
                "mkfs.ext4 /dev/sda1"]
# Extra probes: commands that start with a safe prefix but hide a destructive part.
BYPASS_PROBES = ["echo hi; rm -fr /tmp/x", "cat a.txt >/etc/passwd", "echo hi; su -c ls",
                 "cat a | sh", "echo hi; rm  -rf /", "echo hi && chown root x",
                 "python3 -c \"import shutil; shutil.rmtree('/')\""]

OLD_DENY = [r"rm -rf", r"rm -r", r"sudo", r"chmod ", r"chown ", r"dd if=", r"mkfs", r"mount ",
            r"umount ", r"> /", r"cp /", r"mv /"]
OLD_PREFIXES = ("echo ", "cat ", "ls ", "python3 ", "pip list")


def old_gate_allows(command):
    """The first version of the gate (kept here only to show the false allows it had)."""
    if any(re.search(p, command.lower()) for p in OLD_DENY):
        return False
    return command.startswith(OLD_PREFIXES)


def integration_test():
    stamp("=== Integration test: glob -> search -> read in a temporary sandbox")
    with tempfile.TemporaryDirectory(prefix="hw7_sandbox_") as sandbox:
        write_file(str(Path(sandbox, "a.py")), "print('a')\n")
        write_file(str(Path(sandbox, "b.py")), "value = 2\n")
        write_file(str(Path(sandbox, "c.py")), "# DEBUG flag\nDEBUG = True\nprint(DEBUG)\n")
        found = glob_files("*.py", sandbox)
        stamp(f"glob_files('*.py') -> {found['data']}")
        hits = search_in_files("DEBUG", sandbox, "*.py")
        stamp(f"search_in_files('DEBUG', file_pattern='*.py') -> {hits['data']}")
        target = hits["data"][0]["file"]
        content = read_file(str(Path(sandbox, target)), max_lines=10)
        stamp(f"read_file('{target}') ->")
        print(content["data"])
        assert target == "c.py", "the file containing DEBUG should be c.py"


def gate_test():
    stamp("=== Safety-gate test: 5 allowed, 5 blocked")
    lines, failures = [], 0
    for command, expected in [(c, True) for c in SHOULD_PASS] + [(c, False) for c in SHOULD_BLOCK]:
        verdict = confirm_bash(command)
        ok = verdict["allowed"] == expected
        failures += not ok
        lines.append(f"{command!r:26} expected={'allow' if expected else 'block'} "
                     f"got={'allow' if verdict['allowed'] else 'block'} "
                     f"{'PASS' if ok else 'FAIL'}  ({verdict['reason']})")
    print("\n".join(lines))
    stamp("=== False-allow probes: first gate vs final gate (all should be blocked)")
    probe_lines = []
    for command in BYPASS_PROBES:
        before = "ALLOWED (false allow)" if old_gate_allows(command) else "blocked"
        after = "ALLOWED (false allow)" if confirm_bash(command)["allowed"] else "blocked"
        failures += confirm_bash(command)["allowed"]
        probe_lines.append(f"{command!r:52} first gate: {before:22} final gate: {after}")
    print("\n".join(probe_lines))
    confirmed = confirm_bash("rm -rf build", auto_approve=True)["allowed"]
    stamp(f"is_destructive('rm -rf build') = {is_destructive('rm -rf build')}; "
          f"allowed with explicit confirmation = {confirmed}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "safety_gate_test.txt").write_text(
        "\n".join(lines + [""] + probe_lines) + "\n", encoding="utf-8")
    stamp(f"Gate test finished: {failures} failure(s). Saved raw/safety_gate_test.txt")


if __name__ == "__main__":
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(sys.__stdout__, RUN_LOG)
    stamp("HW7 Part 6 run")
    integration_test()
    gate_test()

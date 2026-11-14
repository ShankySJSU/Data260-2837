"""Logging and JSON helpers for HW10 (same log line format as HW8/HW9)."""

import json
import time
from datetime import datetime

from . import config as cfg


def log(component, message, echo=True):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"{stamp} | {cfg.STUDENT_NAME} | {cfg.PREFIX} | {component:<10} | {message}"
    if echo:
        print(line, flush=True)
    try:
        cfg.RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.RUN_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    return line


def banner(component, title):
    log(component, "=" * 70)
    log(component, title)
    log(component, "=" * 70)


def ms_since(start):
    return round((time.perf_counter() - start) * 1000, 1)


def save_raw(name, data):
    cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = cfg.RAW_DIR / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)  # atomic: the dashboard never reads a half-written file
    return path


def load_raw(name, default=None):
    path = cfg.RAW_DIR / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default

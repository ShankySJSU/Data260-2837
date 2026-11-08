"""Logging and small helpers. Every log line carries my name for the screenshots."""

import json
import time
from datetime import datetime, timezone

from . import hw09_config as cfg


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


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
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def load_raw(name, default=None):
    path = cfg.RAW_DIR / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def redis_client(decode=True):
    import redis
    client = redis.Redis(host=cfg.REDIS_HOST, port=cfg.REDIS_PORT, decode_responses=decode)
    client.ping()
    return client

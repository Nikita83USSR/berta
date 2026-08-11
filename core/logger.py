import json
import logging
import os
import re
import time

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/berta.log",
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s %(levelname)s %(message)s",
)

_SECRET_KEYS = re.compile(r"(authorization|token|password|api[_-]?key|auth[_-]?key|secret)", re.I)

def _sanitize(value):
    if isinstance(value, dict):
        return {k: ("***REDACTED***" if _SECRET_KEYS.search(str(k)) else _sanitize(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    text = str(value)
    text = re.sub(r"Bearer\s+\S+", "Bearer ***REDACTED***", text, flags=re.I)
    return text

def event(name, data=None):
    logging.info(json.dumps({"time": time.time(), "event": name, "data": _sanitize(data)}, ensure_ascii=False))

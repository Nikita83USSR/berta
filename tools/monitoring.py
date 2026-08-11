"""
BERTA tools: Events / Monitoring + AI request counter.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from core.event_bus import bus

_lock = threading.Lock()
_ai_stats = {
    "total": 0,
    "success": 0,
    "error": 0,
    "http_errors": 0,
    "last_request_at": None,
    "total_response_time": 0.0,
    "input_tokens": 0,
    "output_tokens": 0,
}


def _ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None, "success": True}


def _err(type_: str, message: str) -> dict:
    return {
        "ok": False,
        "data": None,
        "error": {"type": type_, "message": message},
        "success": False,
        "error_message": message,
    }


def record_ai_request_start():
    bus.emit("AI_REQUEST_STARTED", {}, source="monitoring")


def record_ai_request_success(elapsed: float | None = None, usage: dict | None = None):
    with _lock:
        _ai_stats["total"] += 1
        _ai_stats["success"] += 1
        _ai_stats["last_request_at"] = time.time()
        if elapsed is not None:
            _ai_stats["total_response_time"] += float(elapsed)
        if usage:
            _ai_stats["input_tokens"] += int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            _ai_stats["output_tokens"] += int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    bus.emit(
        "AI_REQUEST_SUCCESS",
        {"elapsed": elapsed, "usage": usage or {}},
        source="monitoring",
    )


def record_ai_request_error(error: str | None = None, http_status: int | None = None):
    with _lock:
        _ai_stats["total"] += 1
        _ai_stats["error"] += 1
        _ai_stats["last_request_at"] = time.time()
        if http_status and http_status >= 400:
            _ai_stats["http_errors"] += 1
    bus.emit(
        "AI_REQUEST_ERROR",
        {"error": (error or "")[:300], "http_status": http_status},
        source="monitoring",
    )


def ai_request_counter() -> dict:
    with _lock:
        total = _ai_stats["total"]
        success = _ai_stats["success"]
        error = _ai_stats["error"]
        avg = (
            round(_ai_stats["total_response_time"] / success, 3)
            if success
            else None
        )
        data = {
            "total": total,
            "success": success,
            "error": error,
            "http_errors": _ai_stats["http_errors"],
            "last_request_at": _ai_stats["last_request_at"],
            "total_response_time": round(_ai_stats["total_response_time"], 3),
            "average_response_time": avg,
            "input_tokens": _ai_stats["input_tokens"],
            "output_tokens": _ai_stats["output_tokens"],
        }
    return _ok(data)


def event_list(limit: int = 50, event_types: list | None = None, since_id: int = 0) -> dict:
    limit = max(1, min(int(limit or 50), 200))
    events = bus.get_history(since_id=since_id, event_types=event_types, limit=limit)
    # strip any accidental secrets from data previews
    safe = []
    for ev in events:
        item = {
            "id": ev.get("id"),
            "time": ev.get("time"),
            "type": ev.get("type"),
            "source": ev.get("source"),
            "data": _redact(ev.get("data")),
        }
        safe.append(item)
    return _ok({"events": safe, "count": len(safe)})


def event_stats() -> dict:
    events = bus.get_history(since_id=0, limit=2000)
    by_type: dict[str, int] = {}
    for ev in events:
        t = ev.get("type") or "unknown"
        by_type[t] = by_type.get(t, 0) + 1
    return _ok(
        {
            "total_events": len(events),
            "by_type": by_type,
            "ai": ai_request_counter()["data"],
        }
    )


def _redact(data):
    if not isinstance(data, dict):
        return data
    out = {}
    secret_keys = {
        "authorization",
        "cookie",
        "password",
        "token",
        "api_key",
        "auth_key",
        "gigachat_auth_key",
        "db_password",
    }
    for k, v in data.items():
        if str(k).lower() in secret_keys:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out

"""
BERTA tools: HTTP / API.
http_request (GET/POST/PUT/PATCH/DELETE), api_request (allowlisted APIs, secrets from env).
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import requests

from core.event_bus import bus

DEFAULT_TIMEOUT = 30
MAX_BODY_BYTES = 512_000
ALLOWED_SCHEMES = {"http", "https"}
USER_AGENT = "BERTA/0.3 (http_request)"

# Optional domain allowlist (empty = any public host with SSRF guards)
DOMAIN_ALLOWLIST: set[str] = set()

# Predefined safe APIs — secrets only from env
# Пресеты: при необходимости добавляйте свои RU API через .env secret_headers.
# Зарубежный httpbin — только как запасной тест связности.
API_PRESETS = {
    "wikipedia_ru": {
        "url": "https://ru.wikipedia.org/w/api.php",
        "method": "GET",
        "headers": {},
    },
    "httpbin_get": {
        "url": "https://httpbin.org/get",
        "method": "GET",
        "headers": {},
    },
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


def _is_private_host(host: str) -> bool:
    host = (host or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return True
    if re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)", host):
        return True
    return False


def _validate_url(url: str, allow_private: bool = False) -> tuple[bool, str]:
    url = (url or "").strip()
    if not url:
        return False, "URL пустой"
    try:
        p = urlparse(url)
    except Exception as e:
        return False, f"Некорректный URL: {e}"
    if p.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Только HTTP/HTTPS, получено: {p.scheme or '(пусто)'}"
    if not p.netloc:
        return False, "URL без хоста"
    host = (p.hostname or "").lower()
    if not allow_private and _is_private_host(host):
        return False, "Доступ к localhost/private network запрещён"
    if DOMAIN_ALLOWLIST and host not in DOMAIN_ALLOWLIST:
        return False, f"Хост {host} не в allowlist"
    return True, url


def _sanitize_headers(headers: dict | None) -> dict:
    """Убрать секреты из логов; модель не должна сама задавать Authorization/Cookie для api_request."""
    if not headers:
        return {}
    out = {}
    for k, v in headers.items():
        key = str(k)
        if key.lower() in {"authorization", "cookie", "set-cookie", "x-api-key", "api-key"}:
            out[key] = "***"
        else:
            out[key] = v
    return out


def http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    params: dict | None = None,
    json_body: Any = None,
    body: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    allow_private: bool = False,
) -> dict:
    """
    Универсальный HTTP-запрос.
    POST/PUT/PATCH/DELETE — уровень CONFIRM (проверка на стороне function_manager).
    """
    t0 = time.time()
    method = (method or "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
        return _err("ValidationError", f"Неподдерживаемый method: {method}")

    valid, msg = _validate_url(url, allow_private=allow_private)
    if not valid:
        return _err("ValidationError", msg)
    url = msg
    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), 120))

    req_headers = {"User-Agent": USER_AGENT}
    if headers and isinstance(headers, dict):
        # allow user headers but never log secrets
        for k, v in headers.items():
            req_headers[str(k)] = str(v) if v is not None else ""

    bus.emit(
        "WEB_REQUEST",
        {
            "tool": "http_request",
            "method": method,
            "url": url[:300],
            "headers": _sanitize_headers(req_headers),
        },
        source="http",
    )

    try:
        kwargs: dict[str, Any] = {
            "headers": req_headers,
            "params": params,
            "timeout": timeout,
            "allow_redirects": True,
            "stream": True,
        }
        if json_body is not None:
            kwargs["json"] = json_body
        elif body is not None:
            kwargs["data"] = body

        resp = requests.request(method, url, **kwargs)
        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_BODY_BYTES:
                break
        try:
            text = content.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            text = content.decode("utf-8", errors="replace")
        if len(text) > 80_000:
            text = text[:80_000] + "…"

        # try parse JSON
        parsed = None
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "json" in ctype:
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None

        elapsed = round(time.time() - t0, 3)
        return _ok(
            {
                "url": url,
                "final_url": str(resp.url),
                "method": method,
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": text if parsed is None else None,
                "json": parsed,
                "elapsed": elapsed,
            }
        )
    except requests.Timeout:
        return _err("Timeout", f"http_request timeout ({timeout}s)")
    except requests.RequestException as e:
        return _err("NetworkError", str(e)[:500])


def api_request(
    api_name: str,
    params: dict | None = None,
    json_body: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    Упрощённый вызов заранее разрешённых API.
    Секреты только из .env / config. Модель не задаёт Authorization/Cookie.
    """
    name = (api_name or "").strip().lower()
    if name not in API_PRESETS:
        return _err(
            "ValidationError",
            f"API «{api_name}» не в allowlist. Доступны: {', '.join(sorted(API_PRESETS)) or '(нет)'}",
        )
    preset = API_PRESETS[name]
    url = preset["url"]
    method = preset.get("method", "GET")
    headers = dict(preset.get("headers") or {})

    # inject secrets from env if preset defines env keys
    for env_key, header_name in (preset.get("secret_headers") or {}).items():
        val = os.getenv(env_key, "")
        if val:
            headers[header_name] = val

    return http_request(
        url=url,
        method=method,
        headers=headers,
        params=params,
        json_body=json_body,
        timeout=timeout,
        allow_private=False,
    )

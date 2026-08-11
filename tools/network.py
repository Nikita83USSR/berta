"""
BERTA tools: network diagnostics.
curl_request, dns_lookup, ping_host, tcp_check.
"""

from __future__ import annotations

import re
import socket
import subprocess
import time
from typing import Any
from urllib.parse import urlparse

import requests

from core.event_bus import bus

DEFAULT_TIMEOUT = 10
USER_AGENT = "BERTA/0.3 (network)"


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
    host = (host or "").lower().strip()
    if not host:
        return True
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return True
    if re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)", host):
        return True
    return False


def curl_request(
    url: str,
    method: str = "GET",
    timeout: int = DEFAULT_TIMEOUT,
    headers: dict | None = None,
) -> dict:
    """Аналог curl: URL, status, headers, body, elapsed, error."""
    t0 = time.time()
    url = (url or "").strip()
    if not url:
        return _err("ValidationError", "url обязателен")
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"}:
            return _err("ValidationError", "Только HTTP/HTTPS")
        host = (p.hostname or "").lower()
        if _is_private_host(host):
            return _err("SecurityError", "private/localhost запрещён")
    except Exception as e:
        return _err("ValidationError", str(e)[:200])

    method = (method or "GET").upper()
    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), 30))
    req_headers = {"User-Agent": USER_AGENT}
    if headers and isinstance(headers, dict):
        req_headers.update({str(k): str(v) for k, v in headers.items()})

    bus.emit("WEB_REQUEST", {"tool": "curl_request", "url": url[:300], "method": method}, source="network")
    try:
        resp = requests.request(
            method,
            url,
            headers=req_headers,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        body = b""
        for chunk in resp.iter_content(8192):
            body += chunk
            if len(body) > 100_000:
                break
        text = body.decode(resp.encoding or "utf-8", errors="replace")
        if len(text) > 50_000:
            text = text[:50_000] + "…"
        elapsed = round(time.time() - t0, 3)
        return _ok(
            {
                "url": url,
                "final_url": str(resp.url),
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": text,
                "elapsed": elapsed,
                "error": None,
            }
        )
    except requests.Timeout:
        return _ok(
            {
                "url": url,
                "status": None,
                "headers": {},
                "body": None,
                "elapsed": round(time.time() - t0, 3),
                "error": f"timeout ({timeout}s)",
            }
        )
    except requests.RequestException as e:
        return _ok(
            {
                "url": url,
                "status": None,
                "headers": {},
                "body": None,
                "elapsed": round(time.time() - t0, 3),
                "error": str(e)[:400],
            }
        )


def dns_lookup(host: str) -> dict:
    host = (host or "").strip()
    if not host:
        return _err("ValidationError", "host обязателен")
    if _is_private_host(host) and host not in {"localhost"}:
        # allow resolving public names only by default; still block mass scan
        pass
    t0 = time.time()
    try:
        infos = socket.getaddrinfo(host, None)
        addrs = sorted({item[4][0] for item in infos})
        elapsed = round(time.time() - t0, 3)
        bus.emit("WEB_REQUEST", {"tool": "dns_lookup", "host": host[:100]}, source="network")
        return _ok({"host": host, "addresses": addrs, "elapsed": elapsed})
    except socket.gaierror as e:
        return _err("DNSError", str(e)[:300])
    except Exception as e:
        return _err("NetworkError", str(e)[:300])


def ping_host(host: str, count: int = 3, timeout: int = 5) -> dict:
    host = (host or "").strip()
    if not host:
        return _err("ValidationError", "host обязателен")
    if _is_private_host(host):
        return _err("SecurityError", "ping private/localhost запрещён по умолчанию")
    count = max(1, min(int(count or 3), 5))
    timeout = max(1, min(int(timeout or 5), 10))
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            capture_output=True,
            text=True,
            timeout=timeout * count + 5,
        )
        elapsed = round(time.time() - t0, 3)
        bus.emit("WEB_REQUEST", {"tool": "ping_host", "host": host[:100]}, source="network")
        return _ok(
            {
                "host": host,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:3000],
                "stderr": (proc.stderr or "")[:1000],
                "elapsed": elapsed,
            }
        )
    except FileNotFoundError:
        return _err("NotFound", "команда ping недоступна")
    except subprocess.TimeoutExpired:
        return _err("Timeout", "ping timeout")
    except Exception as e:
        return _err("NetworkError", str(e)[:300])


def tcp_check(host: str, port: int, timeout: int = 5) -> dict:
    host = (host or "").strip()
    if not host:
        return _err("ValidationError", "host обязателен")
    if _is_private_host(host):
        return _err("SecurityError", "tcp_check private/localhost запрещён по умолчанию")
    try:
        port = int(port)
    except (TypeError, ValueError):
        return _err("ValidationError", "port должен быть числом")
    if not (1 <= port <= 65535):
        return _err("ValidationError", "port вне диапазона 1..65535")
    # no mass scan: single port only
    timeout = max(1, min(int(timeout or 5), 15))
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            open_ = True
    except (socket.timeout, ConnectionRefusedError, OSError):
        open_ = False
    elapsed = round(time.time() - t0, 3)
    bus.emit(
        "WEB_REQUEST",
        {"tool": "tcp_check", "host": host[:100], "port": port},
        source="network",
    )
    return _ok({"host": host, "port": port, "open": open_, "elapsed": elapsed})

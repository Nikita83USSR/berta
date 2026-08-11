"""
BERTA tools: safe system_command + system_info.
Allowlist for shell commands; no rm -rf / sudo / reboot by default.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from core.event_bus import bus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3"

# Minimal SAFE allowlist (exact or prefix patterns)
SAFE_COMMANDS = {
    "pwd",
    "ls",
    "df",
    "free",
    "uptime",
    "whoami",
    "hostname",
    "date",
    "uname",
    "git status",
    "git log",
    "git branch",
}

SAFE_PREFIXES = (
    "ls ",
    "ls\t",
    "df ",
    "free ",
    "uname ",
    "git status",
    "git log",
    "git branch",
    "git show",
    "git diff",
    "find ",
    "systemctl status ",
    "cat /proc/",
    "ps ",
)

FORBIDDEN_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\bsudo\b",
    r"\bsu\b",
    r"\bpasswd\b",
    r"\buseradd\b",
    r"\buserdel\b",
    r"\biptables\b",
    r"\bufw\b",
    r"\bdd\s+if=",
    r">\s*/dev/",
    r":\(\)\s*\{",
    r"\bbash\s+-c\b",
    r"\bsh\s+-c\b",
    r"\beval\b",
    r"\bchmod\s+777\b",
]

MAX_STDOUT = 30_000
DEFAULT_TIMEOUT = 15


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


def _is_forbidden(cmd: str) -> bool:
    low = cmd.lower()
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, low):
            return True
    return False


def _is_safe(cmd: str) -> bool:
    c = cmd.strip()
    if c in SAFE_COMMANDS:
        return True
    for p in SAFE_PREFIXES:
        if c.startswith(p) or c == p.strip():
            # extra: find only in allowed dirs
            if c.startswith("find "):
                if " /" in c and not any(
                    x in c
                    for x in (
                        str(PROJECT_ROOT),
                        str(Path.home() / ".berta"),
                        str(Path.home() / "Downloads"),
                        str(Path.home() / "Documents"),
                        " .",
                        " ./",
                    )
                ):
                    # allow find . or project-relative
                    if re.search(r"\s+/\s|\s+/[a-z]", c):
                        return False
            return True
    return False


def system_command(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    cwd: str | None = None,
    confirm: bool = False,
) -> dict:
    """
    Выполнить локальную команду по allowlist.
    Нестандартные команды — только с confirm=True.
    """
    command = (command or "").strip()
    if not command:
        return _err("ValidationError", "command пустая")

    if _is_forbidden(command):
        return _err("Forbidden", f"Команда запрещена политикой безопасности: {command[:80]}")

    safe = _is_safe(command)
    if not safe and not confirm:
        return _err(
            "ConfirmRequired",
            f"Команда не в SAFE allowlist и требует подтверждения: {command[:120]}",
        )

    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), 60))
    workdir = Path(cwd).resolve() if cwd else PROJECT_ROOT
    if not workdir.is_dir():
        workdir = PROJECT_ROOT

    bus.emit(
        "SYSTEM_COMMAND",
        {"command": command[:200], "safe": safe, "cwd": str(workdir)},
        source="system",
    )
    t0 = time.time()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir),
        )
        stdout = (proc.stdout or "")[:MAX_STDOUT]
        stderr = (proc.stderr or "")[:MAX_STDOUT]
        elapsed = round(time.time() - t0, 3)
        return _ok(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "elapsed": elapsed,
                "cwd": str(workdir),
            }
        )
    except subprocess.TimeoutExpired:
        return _err("Timeout", f"timeout ({timeout}s)")
    except Exception as e:
        return _err("ExecError", str(e)[:400])


def system_info() -> dict:
    t0 = time.time()
    mem = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem["total_kb"] = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem["available_kb"] = int(line.split()[1])
    except OSError:
        mem = {"note": "meminfo unavailable"}

    disk = {}
    try:
        usage = shutil.disk_usage("/")
        disk = {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        }
    except OSError:
        disk = {}

    cpu = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass

    data = {
        "os": platform.system(),
        "os_release": platform.release(),
        "kernel": platform.version(),
        "platform": platform.platform(),
        "cpu": cpu,
        "arch": platform.machine(),
        "ram": mem,
        "disk": disk,
        "hostname": platform.node(),
        "python": platform.python_version(),
        "berta_version": VERSION,
        "cwd": str(Path.cwd()),
        "project_root": str(PROJECT_ROOT),
        "elapsed": round(time.time() - t0, 3),
    }
    bus.emit("SYSTEM_COMMAND", {"tool": "system_info"}, source="system")
    return _ok(data)

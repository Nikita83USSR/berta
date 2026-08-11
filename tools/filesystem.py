"""
BERTA tools: Files (sandbox).
file_list, file_read, file_write, file_append, file_exists, file_info, file_search.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from core.event_bus import bus

# Sandbox roots (whitelist)
HOME = Path.home()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_ROOTS = [
    PROJECT_ROOT.resolve(),
    (HOME / ".berta").resolve(),
    (HOME / "Downloads").resolve(),
    (HOME / "Documents").resolve(),
    (HOME / "Desktop").resolve(),
]

MAX_READ_BYTES = 512_000
MAX_WRITE_BYTES = 2_000_000
SECRET_NAME_RE = re.compile(
    r"(?i)(\.env|\.pem|\.key|id_rsa|id_ed25519|credentials|secret|password|token|\.ssh)",
)


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


def _normalize(path: str | None) -> Path:
    value = os.path.expandvars(os.path.expanduser((path or "").strip() or "."))
    return Path(value).resolve()


def _in_sandbox(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in SANDBOX_ROOTS:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _is_secret(path: Path) -> bool:
    name = path.name
    full = str(path)
    if SECRET_NAME_RE.search(name) or SECRET_NAME_RE.search(full):
        return True
    # common secret dirs
    parts = {p.lower() for p in path.parts}
    if ".ssh" in parts or ".gnupg" in parts:
        return True
    return False


def _check_path(path: Path, for_write: bool = False) -> str | None:
    if not _in_sandbox(path):
        return f"Путь вне sandbox: {path}"
    if _is_secret(path) and not for_write:
        return f"Чтение секретных файлов запрещено: {path.name}"
    if for_write and _is_secret(path):
        return f"Запись в секретные файлы запрещена: {path.name}"
    return None


def file_list(path: str = ".", include_hidden: bool = False, max_items: int = 300) -> dict:
    t0 = time.time()
    p = _normalize(path)
    err = _check_path(p)
    if err:
        return _err("SecurityError", err)
    if not p.is_dir():
        return _err("NotFound", f"Папка не найдена: {p}")
    max_items = max(1, min(int(max_items or 300), 500))
    items = []
    try:
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if not include_hidden and child.name.startswith("."):
                continue
            try:
                st = child.stat()
                items.append(
                    {
                        "name": child.name,
                        "type": "dir" if child.is_dir() else "file",
                        "path": str(child),
                        "size": st.st_size if child.is_file() else None,
                    }
                )
            except OSError:
                items.append({"name": child.name, "type": "?", "path": str(child)})
            if len(items) >= max_items:
                break
    except OSError as e:
        return _err("IOError", str(e)[:400])
    bus.emit("FILE_OPERATION", {"tool": "file_list", "path": str(p)}, source="filesystem")
    return _ok(
        {
            "path": str(p),
            "items": items,
            "count": len(items),
            "elapsed": round(time.time() - t0, 3),
        }
    )


def file_read(path: str, max_length: int = MAX_READ_BYTES) -> dict:
    t0 = time.time()
    p = _normalize(path)
    err = _check_path(p)
    if err:
        return _err("SecurityError", err)
    if not p.is_file():
        return _err("NotFound", f"Файл не найден: {p}")
    max_length = max(1, min(int(max_length or MAX_READ_BYTES), MAX_READ_BYTES))
    try:
        data = p.read_bytes()[: max_length + 1]
        truncated = len(data) > max_length
        text = data[:max_length].decode("utf-8", errors="replace")
        if truncated:
            text += "…"
    except OSError as e:
        return _err("IOError", str(e)[:400])
    bus.emit("FILE_OPERATION", {"tool": "file_read", "path": str(p)}, source="filesystem")
    return _ok(
        {
            "path": str(p),
            "content": text,
            "length": len(text),
            "truncated": truncated,
            "elapsed": round(time.time() - t0, 3),
        }
    )


def file_write(path: str, content: str, confirm: bool = False) -> dict:
    """CONFIRM level — confirm flag must be true from function_manager."""
    t0 = time.time()
    if not confirm:
        return _err("ConfirmRequired", "file_write требует подтверждения")
    p = _normalize(path)
    err = _check_path(p, for_write=True)
    if err:
        return _err("SecurityError", err)
    content = content if content is not None else ""
    if isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        raw = bytes(content)
    if len(raw) > MAX_WRITE_BYTES:
        return _err("SizeLimit", f"Контент больше {MAX_WRITE_BYTES} байт")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    except OSError as e:
        return _err("IOError", str(e)[:400])
    bus.emit("FILE_OPERATION", {"tool": "file_write", "path": str(p)}, source="filesystem")
    return _ok({"path": str(p), "bytes": len(raw), "elapsed": round(time.time() - t0, 3)})


def file_append(path: str, content: str, confirm: bool = False) -> dict:
    t0 = time.time()
    if not confirm:
        return _err("ConfirmRequired", "file_append требует подтверждения")
    p = _normalize(path)
    err = _check_path(p, for_write=True)
    if err:
        return _err("SecurityError", err)
    content = content if content is not None else ""
    raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if len(raw) > MAX_WRITE_BYTES:
        return _err("SizeLimit", f"Контент больше {MAX_WRITE_BYTES} байт")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "ab") as f:
            f.write(raw)
    except OSError as e:
        return _err("IOError", str(e)[:400])
    bus.emit("FILE_OPERATION", {"tool": "file_append", "path": str(p)}, source="filesystem")
    return _ok({"path": str(p), "bytes_appended": len(raw), "elapsed": round(time.time() - t0, 3)})


def file_exists(path: str) -> dict:
    p = _normalize(path)
    err = _check_path(p)
    if err:
        return _err("SecurityError", err)
    exists = p.exists()
    return _ok({"path": str(p), "exists": exists, "is_file": p.is_file() if exists else False, "is_dir": p.is_dir() if exists else False})


def file_info(path: str) -> dict:
    p = _normalize(path)
    err = _check_path(p)
    if err:
        return _err("SecurityError", err)
    if not p.exists():
        return _err("NotFound", f"Не найдено: {p}")
    try:
        st = p.stat()
        return _ok(
            {
                "path": str(p),
                "name": p.name,
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
                "size": st.st_size,
                "mtime": st.st_mtime,
                "mode": oct(st.st_mode),
            }
        )
    except OSError as e:
        return _err("IOError", str(e)[:400])


def file_search(
    query: str,
    path: str = ".",
    kind: str = "any",
    max_results: int = 50,
) -> dict:
    t0 = time.time()
    query = (query or "").strip()
    if not query:
        return _err("ValidationError", "query обязателен")
    root = _normalize(path)
    err = _check_path(root)
    if err:
        return _err("SecurityError", err)
    if not root.is_dir():
        return _err("NotFound", f"Каталог не найден: {root}")
    max_results = max(1, min(int(max_results or 50), 100))
    kind = (kind or "any").lower()
    q = query.lower()
    results = []
    skip = {".cache", ".git", "__pycache__", "node_modules", ".venv", "venv"}
    try:
        for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            names = []
            if kind in ("any", "dir"):
                names.extend((n, True) for n in dirs)
            if kind in ("any", "file"):
                names.extend((n, False) for n in files)
            for name, is_dir in names:
                if q in name.lower():
                    results.append(str(Path(base) / name))
                    if len(results) >= max_results:
                        bus.emit(
                            "FILE_OPERATION",
                            {"tool": "file_search", "query": query[:100]},
                            source="filesystem",
                        )
                        return _ok(
                            {
                                "root": str(root),
                                "query": query,
                                "results": results,
                                "count": len(results),
                                "elapsed": round(time.time() - t0, 3),
                            }
                        )
    except OSError as e:
        return _err("IOError", str(e)[:400])
    bus.emit("FILE_OPERATION", {"tool": "file_search", "query": query[:100]}, source="filesystem")
    return _ok(
        {
            "root": str(root),
            "query": query,
            "results": results,
            "count": len(results),
            "elapsed": round(time.time() - t0, 3),
        }
    )

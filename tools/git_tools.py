"""
BERTA tools: Git (read-only by default; write requires confirmation).
git_status, git_log, git_branch, git_diff, git_show,
git_add, git_commit, git_pull, git_push (CONFIRM / disabled by default).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from core.event_bus import bus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 30
MAX_OUTPUT = 50_000


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


def _run_git(args: list[str], cwd: Path | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    cwd = cwd or PROJECT_ROOT
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = (proc.stdout or "")[:MAX_OUTPUT]
        stderr = (proc.stderr or "")[:MAX_OUTPUT]
        elapsed = round(time.time() - t0, 3)
        return {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed": elapsed,
            "cwd": str(cwd),
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "timeout", "elapsed": timeout, "cwd": str(cwd)}
    except FileNotFoundError:
        return {"returncode": -1, "stdout": "", "stderr": "git not found", "elapsed": 0, "cwd": str(cwd)}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)[:400], "elapsed": 0, "cwd": str(cwd)}


def _is_repo(cwd: Path | None = None) -> bool:
    cwd = cwd or PROJECT_ROOT
    r = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd, timeout=5)
    return r["returncode"] == 0 and "true" in (r["stdout"] or "").lower()


def git_status(path: str | None = None) -> dict:
    cwd = Path(path).resolve() if path else PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    r = _run_git(["status", "--porcelain", "-b"], cwd=cwd)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_status", "cwd": str(cwd)}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or "git status failed")
    return _ok({"status": r["stdout"], "cwd": str(cwd), "elapsed": r["elapsed"]})


def git_log(limit: int = 10, path: str | None = None) -> dict:
    cwd = Path(path).resolve() if path else PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    limit = max(1, min(int(limit or 10), 50))
    r = _run_git(
        ["log", f"-{limit}", "--pretty=format:%h|%an|%ar|%s"],
        cwd=cwd,
    )
    bus.emit("SYSTEM_COMMAND", {"tool": "git_log", "limit": limit}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or "git log failed")
    commits = []
    for line in (r["stdout"] or "").splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append(
                {"hash": parts[0], "author": parts[1], "when": parts[2], "subject": parts[3]}
            )
    return _ok({"commits": commits, "count": len(commits), "cwd": str(cwd), "elapsed": r["elapsed"]})


def git_branch(path: str | None = None) -> dict:
    cwd = Path(path).resolve() if path else PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    r = _run_git(["branch", "-vv"], cwd=cwd)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_branch"}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or "git branch failed")
    return _ok({"branches": r["stdout"], "cwd": str(cwd), "elapsed": r["elapsed"]})


def git_diff(path: str | None = None, staged: bool = False) -> dict:
    cwd = Path(path).resolve() if path else PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    args = ["diff", "--stat"] if not staged else ["diff", "--cached", "--stat"]
    r = _run_git(args, cwd=cwd)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_diff", "staged": staged}, source="git")
    if r["returncode"] not in (0, 1):  # 1 = differences
        return _err("GitError", r["stderr"] or "git diff failed")
    return _ok({"diff": r["stdout"][:MAX_OUTPUT], "cwd": str(cwd), "elapsed": r["elapsed"]})


def git_show(ref: str = "HEAD", path: str | None = None) -> dict:
    cwd = Path(path).resolve() if path else PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    ref = (ref or "HEAD").strip()
    if not ref or any(c in ref for c in ";|&`$"):
        return _err("ValidationError", "Некорректный ref")
    r = _run_git(["show", "--stat", ref], cwd=cwd)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_show", "ref": ref[:40]}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or "git show failed")
    return _ok({"show": r["stdout"][:MAX_OUTPUT], "ref": ref, "cwd": str(cwd), "elapsed": r["elapsed"]})


def git_add(paths: list[str] | None = None, confirm: bool = False) -> dict:
    if not confirm:
        return _err("ConfirmRequired", "git_add требует явного подтверждения пользователя")
    cwd = PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    args = ["add"]
    if paths:
        for p in paths:
            if ".." in p or p.startswith("/"):
                return _err("SecurityError", f"Небезопасный путь: {p}")
            args.append(p)
    else:
        args.append(".")
    r = _run_git(args, cwd=cwd)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_add"}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or "git add failed")
    return _ok({"message": "git add выполнен", "stdout": r["stdout"], "elapsed": r["elapsed"]})


def git_commit(message: str, confirm: bool = False) -> dict:
    if not confirm:
        return _err("ConfirmRequired", "git_commit требует явного подтверждения пользователя")
    message = (message or "").strip()
    if not message:
        return _err("ValidationError", "message обязателен")
    cwd = PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    r = _run_git(["commit", "-m", message], cwd=cwd)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_commit"}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or r["stdout"] or "git commit failed")
    return _ok({"message": "commit создан", "stdout": r["stdout"], "elapsed": r["elapsed"]})


def git_pull(confirm: bool = False) -> dict:
    if not confirm:
        return _err("ConfirmRequired", "git_pull требует явного подтверждения пользователя")
    cwd = PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    r = _run_git(["pull", "--ff-only"], cwd=cwd, timeout=60)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_pull"}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or r["stdout"] or "git pull failed")
    return _ok({"message": "git pull выполнен", "stdout": r["stdout"], "elapsed": r["elapsed"]})


def git_push(confirm: bool = False) -> dict:
    if not confirm:
        return _err("ConfirmRequired", "git_push требует явного подтверждения пользователя")
    cwd = PROJECT_ROOT
    if not _is_repo(cwd):
        return _err("NotRepo", f"Не git-репозиторий: {cwd}")
    r = _run_git(["push"], cwd=cwd, timeout=60)
    bus.emit("SYSTEM_COMMAND", {"tool": "git_push"}, source="git")
    if r["returncode"] != 0:
        return _err("GitError", r["stderr"] or r["stdout"] or "git push failed")
    return _ok({"message": "git push выполнен", "stdout": r["stdout"], "elapsed": r["elapsed"]})

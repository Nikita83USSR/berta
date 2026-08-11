"""Исполнитель инструментов BERTA. Фактический результат Python — источник истины."""

import datetime
import json
import os
import platform
import shutil
import signal
import subprocess
from pathlib import Path

import pymysql

from config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from core.event_bus import bus
from core.task_manager import task_manager

DANGEROUS_PATTERNS = [
    "rm -rf", "dd if=", "> /dev/", "mkfs.", "fdisk", "parted",
    "shutdown", "reboot", "init 0", "poweroff", "mkfs", ":(){", "fork",
]

# Смысловые алиасы. Команда выбирается только если она реально установлена.
APP_ALIASES = {
    "notepad": ["mousepad", "xed", "featherpad", "pluma", "leafpad", "gedit", "kate", "kwrite", "libreoffice --writer"],
    "блокнот": ["mousepad", "xed", "featherpad", "pluma", "leafpad", "gedit", "gnome-text-editor", "kate", "kwrite", "libreoffice --writer"],
    "хром": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "firefox", "brave-browser", "opera"],
    "google chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "firefox", "brave-browser", "opera"],
    "text editor": ["mousepad", "xed", "featherpad", "pluma", "leafpad", "gedit", "kate", "kwrite", "libreoffice --writer"],
    "редактор текста": ["mousepad", "xed", "featherpad", "pluma", "leafpad", "gedit", "kate", "kwrite", "libreoffice --writer"],
    "browser": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "firefox", "brave-browser", "opera"],
    "браузер": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "firefox", "brave-browser", "opera"],
    "file manager": ["thunar", "nautilus", "dolphin", "nemo", "pcmanfm", "caja"],
    "файловый менеджер": ["thunar", "nautilus", "dolphin", "nemo", "pcmanfm", "caja"],
    "проводник": ["thunar", "nautilus", "dolphin", "nemo", "pcmanfm", "caja"],
    "terminal": ["xfce4-terminal", "gnome-terminal", "konsole", "mate-terminal", "qterminal", "xterm"],
    "терминал": ["xfce4-terminal", "gnome-terminal", "konsole", "mate-terminal", "qterminal", "xterm"],
    "calculator": ["galculator", "gnome-calculator", "kcalc", "mate-calc", "qalculate-gtk"],
    "калькулятор": ["galculator", "gnome-calculator", "kcalc", "mate-calc", "qalculate-gtk"],
}


def get_db():
    return pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
                           database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True)


def _emit_done(name, result):
    bus.emit("tool", {"name": name, "status": "completed", "success": bool(result.get("success")),
                       "result_preview": json.dumps(result, ensure_ascii=False, default=str)[:800]}, source="function_manager")


def _confirm(prompt):
    bus.emit("system", {"message": "Операция требует подтверждения", "prompt": prompt}, source="function_manager")
    try:
        return input(prompt + " [y/N]: ").strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def _resolve_path(value: str) -> Path:
    value = os.path.expandvars(os.path.expanduser((value or "").strip()))
    return Path(value or str(Path.home())).resolve()


def _desktop_env():
    env = os.environ
    return {
        "desktop": env.get("XDG_CURRENT_DESKTOP") or env.get("XDG_SESSION_DESKTOP") or "",
        "session": env.get("DESKTOP_SESSION", ""),
        "display": env.get("DISPLAY", ""),
        "wayland_display": env.get("WAYLAND_DISPLAY", ""),
    }


def _desktop_entries():
    roots = [Path.home() / ".local/share/applications", Path("/usr/share/applications"), Path("/usr/local/share/applications")]
    entries = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.glob("*.desktop"):
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            name = ""
            exec_line = ""
            try:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("Name=") and not name:
                        name = line[5:].strip()
                    elif line.startswith("Exec=") and not exec_line:
                        exec_line = line[5:].strip()
            except OSError:
                continue
            if name and exec_line:
                entries.append({"name": name, "exec": exec_line, "desktop_file": key})
    return entries


def _command_exists(command):
    return shutil.which(command) is not None


def _launch_candidate(candidate: str, args=None):
    import shlex
    parts = shlex.split(candidate)
    binary = parts[0]
    if not _command_exists(binary):
        return None
    argv = parts + [str(x) for x in (args or [])]
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        return proc
    except OSError:
        return None


def _find_app(application: str):
    query = (application or "").strip().lower()
    desktop = (_desktop_env().get("desktop") or "").lower()

    # Приоритеты зависят от реально используемого desktop, но каждый вариант
    # проверяется на наличие. Никакого принудительного gedit/nautilus.
    desktop_overrides = {
        "xfce": {
            "блокнот": ["mousepad", "xed", "featherpad", "pluma", "gedit", "kate"],
            "notepad": ["mousepad", "xed", "featherpad", "pluma", "gedit", "kate"],
            "файловый менеджер": ["thunar", "nemo", "pcmanfm", "nautilus", "dolphin"],
            "проводник": ["thunar", "nemo", "pcmanfm", "nautilus", "dolphin"],
            "терминал": ["xfce4-terminal", "qterminal", "xterm", "gnome-terminal", "konsole"],
        },
        "gnome": {
            "блокнот": ["gnome-text-editor", "gedit", "mousepad", "kate"],
            "notepad": ["gnome-text-editor", "gedit", "mousepad", "kate"],
            "файловый менеджер": ["nautilus", "thunar", "nemo", "dolphin"],
            "проводник": ["nautilus", "thunar", "nemo", "dolphin"],
            "терминал": ["gnome-terminal", "kgx", "xfce4-terminal", "konsole"],
        },
        "kde": {
            "блокнот": ["kate", "kwrite", "mousepad", "gedit"],
            "notepad": ["kate", "kwrite", "mousepad", "gedit"],
            "файловый менеджер": ["dolphin", "thunar", "nautilus", "nemo"],
            "проводник": ["dolphin", "thunar", "nautilus", "nemo"],
            "терминал": ["konsole", "qterminal", "xfce4-terminal", "gnome-terminal"],
        },
    }
    for key, variants in desktop_overrides.items():
        if key in desktop and query in variants:
            for candidate in variants[query]:
                if _command_exists(candidate):
                    return candidate, f"desktop:{key}"

    candidates = APP_ALIASES.get(query, [])
    for candidate in candidates:
        if _command_exists(candidate.split()[0]):
            return candidate, "alias"

    entries = _desktop_entries()
    tokens = [t for t in query.replace("-", " ").split() if len(t) > 1]
    scored = []
    for entry in entries:
        hay = (entry["name"] + " " + entry["exec"]).lower()
        score = sum(1 for token in tokens if token in hay)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
    if scored:
        entry = scored[0][1]
        return entry["exec"].strip(), "desktop-file"

    if _command_exists(query):
        return query, "path"
    return None, None


def _search_files(query, root, kind="any", max_results=50):
    query_l = query.lower()
    results = []
    skip = {".cache", ".local/share/Trash", ".mozilla/firefox", ".config/google-chrome"}
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        rel = os.path.relpath(base, root)
        dirs[:] = [d for d in dirs if not any(part in skip for part in Path(rel, d).parts)]
        names = []
        if kind in ("any", "dir"):
            names.extend((name, True) for name in dirs)
        if kind in ("any", "file"):
            names.extend((name, False) for name in files)
        for name, is_dir in names:
            if query_l in name.lower():
                results.append(str(Path(base) / name))
                if len(results) >= max_results:
                    return results
    return results


def execute_function(name: str, arguments: dict | None = None):
    arguments = arguments or {}
    bus.emit("tool", {"name": name, "arguments": arguments, "status": "started"}, source="function_manager")
    try:
        if name == "get_current_time":
            result = {"success": True, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        elif name == "get_current_date":
            result = {"success": True, "date": datetime.date.today().isoformat()}
        elif name in {"get_system_status", "get_desktop_info"}:
            result = {"success": True, "python": platform.python_version(), "platform": platform.platform(),
                      "pid": os.getpid(), **_desktop_env()}
        elif name == "list_clients":
            limit = max(1, min(int(arguments.get("limit", 50)), 200))
            db = get_db()
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT id, name, phone, status, balance FROM clients ORDER BY id LIMIT %s", (limit,))
                    rows = cursor.fetchall()
                result = {"success": True, "clients": rows, "count": len(rows), "limit": limit}
            finally: db.close()
        elif name == "read_client_balance":
            client_id = int(arguments["client_id"]); db = get_db()
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT * FROM clients WHERE id = %s LIMIT 1", (client_id,)); row = cursor.fetchone()
                result = {"success": bool(row), "client": row} if row else {"success": False, "message": "Клиент не найден"}
            finally: db.close()
        elif name == "delete_client_by_name":
            client_name = (arguments.get("name") or "").strip()
            if not client_name or not _confirm(f"Удалить клиентов с именем «{client_name}»?"):
                result = {"success": False, "error": "Удаление отменено пользователем"}
            else:
                db = get_db()
                try:
                    with db.cursor() as cursor:
                        cursor.execute("SELECT id, name, phone, status, balance FROM clients WHERE name = %s", (client_name,))
                        rows = cursor.fetchall(); cursor.execute("DELETE FROM clients WHERE name = %s", (client_name,))
                        result = {"success": True, "deleted": cursor.rowcount, "clients": rows}
                finally: db.close()
        elif name == "read_file":
            path = _resolve_path(arguments.get("filename")); result = {"success": True, "file": str(path), "code": path.read_text(encoding="utf-8")}
        elif name == "list_directory":
            path = _resolve_path(arguments.get("path")); include_hidden = bool(arguments.get("include_hidden", False))
            if not path.is_dir(): result = {"success": False, "error": f"Папка не найдена: {path}"}
            else:
                items = []
                for p in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    if not include_hidden and p.name.startswith("."): continue
                    items.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "path": str(p)})
                result = {"success": True, "path": str(path), "items": items[:300], "count": len(items)}
        elif name == "find_files":
            query = (arguments.get("query") or "").strip(); root = _resolve_path(arguments.get("path") or "~")
            kind = arguments.get("kind", "any"); max_results = max(1, min(int(arguments.get("max_results", 50)), 100))
            if not query: result = {"success": False, "error": "Не указан запрос поиска"}
            elif not root.is_dir(): result = {"success": False, "error": f"Каталог не найден: {root}"}
            else: result = {"success": True, "root": str(root), "query": query, "results": _search_files(query, root, kind, max_results)}
        elif name == "get_desktop_info":
            result = {"success": True, **_desktop_env()}
        elif name == "list_applications":
            query = (arguments.get("query") or "").lower().strip(); limit = max(1, min(int(arguments.get("max_results", 80)), 200))
            entries = _desktop_entries()
            if query: entries = [e for e in entries if query in (e["name"] + " " + e["exec"]).lower()]
            result = {"success": True, "desktop": _desktop_env(), "applications": entries[:limit], "count": len(entries[:limit])}
        elif name == "launch_application":
            app = (arguments.get("application") or "").strip(); args = arguments.get("args") or []
            candidate, source = _find_app(app)
            if not candidate:
                result = {"success": False, "error": f"Приложение «{app}» не найдено среди установленных приложений.", "desktop": _desktop_env()}
            else:
                proc = _launch_candidate(candidate, args)
                result = {"success": bool(proc), "application": app, "command": candidate, "resolution": source,
                          "pid": proc.pid if proc else None, "desktop": _desktop_env()}
        elif name == "open_path":
            path = _resolve_path(arguments.get("path"));
            if not path.exists(): result = {"success": False, "error": f"Путь не найден: {path}"}
            else:
                opener = shutil.which("xdg-open")
                if not opener: result = {"success": False, "error": "xdg-open недоступен"}
                else:
                    proc = subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                    result = {"success": True, "path": str(path), "pid": proc.pid}
        elif name == "list_processes":
            query = (arguments.get("query") or "").lower(); limit = max(1, min(int(arguments.get("max_results", 50)), 200))
            ps = subprocess.run(["ps", "-eo", "pid=,comm=,args="], capture_output=True, text=True, timeout=10)
            rows = []
            for line in ps.stdout.splitlines():
                parts = line.strip().split(None, 2)
                if len(parts) < 2: continue
                if query and query not in line.lower(): continue
                rows.append({"pid": int(parts[0]), "command": parts[1], "args": parts[2] if len(parts) > 2 else ""})
                if len(rows) >= limit: break
            result = {"success": True, "processes": rows, "count": len(rows)}
        elif name == "terminate_process":
            pid = arguments.get("pid"); pname = (arguments.get("name") or "").strip()
            if not pid and not pname: result = {"success": False, "error": "Нужен pid или name"}
            elif not _confirm(f"Завершить процесс {pid or pname}?"): result = {"success": False, "error": "Операция отменена пользователем"}
            else:
                targets = [int(pid)] if pid else []
                if pname:
                    ps = subprocess.run(["pgrep", "-f", pname], capture_output=True, text=True)
                    targets += [int(x) for x in ps.stdout.split() if x.isdigit()]
                targets = sorted(set(targets)); killed = []
                for target in targets:
                    try: os.kill(target, signal.SIGTERM); killed.append(target)
                    except ProcessLookupError: pass
                    except PermissionError: pass
                result = {"success": bool(killed), "terminated": killed}
        elif name == "execute_system_command":
            command = (arguments.get("command") or "").strip()
            if not command: result = {"success": False, "error": "Пустая команда"}
            elif any(p in command.lower() for p in DANGEROUS_PATTERNS) and not _confirm("Выполнить потенциально опасную системную команду?"):
                result = {"success": False, "error": "Опасная операция отменена пользователем"}
            else:
                background = arguments.get("background")
                if background in ("detached", True):
                    task = task_manager.start_detached_process(f"cmd:{command[:40]}", command, command, shell=True)
                    result = {"success": task.status != "failed", "background": True, "detached": True, "task_id": task.id, "message": "Команда запущена в фоне"}
                elif background == "wait":
                    task = task_manager.start_process(f"cmd:{command[:40]}", command, command, shell=True)
                    result = {"success": True, "background": True, "detached": False, "task_id": task.id, "message": "Команда выполняется в фоне"}
                else:
                    proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
                    result = {"success": proc.returncode == 0, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "returncode": proc.returncode}
        elif name == "list_tasks":
            tasks = task_manager.list_tasks(only_active=bool(arguments.get("only_active", False))); result = {"success": True, "tasks": tasks, "count": len(tasks)}
        else:
            result = _dispatch_extended(name, arguments)

        _emit_done(name, result); return result
    except Exception as exc:
        result = {"success": False, "error": str(exc), "ok": False, "data": None,
                  "error_detail": {"type": "Exception", "message": str(exc)}}
        bus.emit("error", {"tool": name, "error": str(exc)}, source="function_manager")
        return result


# --- Extended tools (web/http/files/git/network/audio/monitoring/system_safe) ---

CONFIRM_TOOLS = {
    "http_request",  # when method is not GET/HEAD
    "file_write",
    "file_append",
    "git_add",
    "git_commit",
    "git_pull",
    "git_push",
}


def _dispatch_extended(name: str, arguments: dict):
    """Route new tools; return dict with success/ok fields."""
    from tools import web as web_mod
    from tools import http as http_mod
    from tools import filesystem as fs_mod
    from tools import git_tools as git_mod
    from tools import network as net_mod
    from tools import audio as audio_mod
    from tools import monitoring as mon_mod
    from tools import system_safe as sys_mod

    args = arguments or {}

    # --- web ---
    if name == "weather":
        return web_mod.weather(city=args.get("city"), query=args.get("query"))
    if name == "web_search":
        return web_mod.web_search(
            args.get("query", ""),
            limit=args.get("limit", 5),
            language=args.get("language"),
        )
    if name == "web_open":
        return web_mod.web_open(
            args.get("url", ""),
            timeout=args.get("timeout", 20),
            max_length=args.get("max_length", 20000),
        )
    if name == "web_fetch":
        return web_mod.web_fetch(
            args.get("url", ""),
            method=args.get("method", "GET"),
            timeout=args.get("timeout", 20),
        )
    if name == "web_download":
        return web_mod.web_download(
            args.get("url", ""),
            dest_name=args.get("dest_name"),
            timeout=args.get("timeout", 60),
        )

    # --- http ---
    if name == "http_request":
        method = (args.get("method") or "GET").upper()
        if method not in {"GET", "HEAD"}:
            if not _confirm(f"Выполнить HTTP {method} к {args.get('url', '')[:80]}?"):
                return {"ok": False, "success": False, "data": None,
                        "error": {"type": "ConfirmRequired", "message": "Отменено пользователем"},
                        "error_message": "Отменено пользователем"}
        return http_mod.http_request(
            url=args.get("url", ""),
            method=method,
            headers=args.get("headers"),
            params=args.get("params"),
            json_body=args.get("json"),
            body=args.get("body"),
            timeout=args.get("timeout", 30),
        )
    if name == "api_request":
        return http_mod.api_request(
            api_name=args.get("api_name", ""),
            params=args.get("params"),
            json_body=args.get("json"),
            timeout=args.get("timeout", 30),
        )

    # --- system ---
    if name == "system_command":
        cmd = (args.get("command") or "").strip()
        from tools.system_safe import _is_safe, _is_forbidden
        if _is_forbidden(cmd):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "Forbidden", "message": "Команда запрещена"},
                    "error_message": "Команда запрещена"}
        confirm = False
        if not _is_safe(cmd):
            if not _confirm(f"Выполнить нестандартную команду: {cmd[:100]}?"):
                return {"ok": False, "success": False, "data": None,
                        "error": {"type": "ConfirmRequired", "message": "Отменено"},
                        "error_message": "Отменено"}
            confirm = True
        return sys_mod.system_command(
            command=cmd,
            timeout=args.get("timeout", 15),
            cwd=args.get("cwd"),
            confirm=confirm,
        )
    if name == "system_info":
        return sys_mod.system_info()

    # --- filesystem ---
    if name == "file_list":
        return fs_mod.file_list(
            path=args.get("path", "."),
            include_hidden=bool(args.get("include_hidden", False)),
            max_items=args.get("max_items", 300),
        )
    if name == "file_read":
        return fs_mod.file_read(path=args.get("path") or args.get("filename", ""), max_length=args.get("max_length", 512000))
    if name == "file_write":
        if not _confirm(f"Записать файл {args.get('path', '')}?"):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "ConfirmRequired", "message": "Отменено"},
                    "error_message": "Отменено"}
        return fs_mod.file_write(path=args.get("path", ""), content=args.get("content", ""), confirm=True)
    if name == "file_append":
        if not _confirm(f"Дописать в файл {args.get('path', '')}?"):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "ConfirmRequired", "message": "Отменено"},
                    "error_message": "Отменено"}
        return fs_mod.file_append(path=args.get("path", ""), content=args.get("content", ""), confirm=True)
    if name == "file_exists":
        return fs_mod.file_exists(path=args.get("path", ""))
    if name == "file_info":
        return fs_mod.file_info(path=args.get("path", ""))
    if name == "file_search":
        return fs_mod.file_search(
            query=args.get("query", ""),
            path=args.get("path", "."),
            kind=args.get("kind", "any"),
            max_results=args.get("max_results", 50),
        )

    # --- git ---
    if name == "git_status":
        return git_mod.git_status(path=args.get("path"))
    if name == "git_log":
        return git_mod.git_log(limit=args.get("limit", 10), path=args.get("path"))
    if name == "git_branch":
        return git_mod.git_branch(path=args.get("path"))
    if name == "git_diff":
        return git_mod.git_diff(path=args.get("path"), staged=bool(args.get("staged", False)))
    if name == "git_show":
        return git_mod.git_show(ref=args.get("ref", "HEAD"), path=args.get("path"))
    if name == "git_add":
        if not _confirm("Выполнить git add?"):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "ConfirmRequired", "message": "Отменено"},
                    "error_message": "Отменено"}
        return git_mod.git_add(paths=args.get("paths"), confirm=True)
    if name == "git_commit":
        if not _confirm(f"Выполнить git commit: {args.get('message', '')[:60]}?"):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "ConfirmRequired", "message": "Отменено"},
                    "error_message": "Отменено"}
        return git_mod.git_commit(message=args.get("message", ""), confirm=True)
    if name == "git_pull":
        if not _confirm("Выполнить git pull?"):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "ConfirmRequired", "message": "Отменено"},
                    "error_message": "Отменено"}
        return git_mod.git_pull(confirm=True)
    if name == "git_push":
        if not _confirm("Выполнить git push?"):
            return {"ok": False, "success": False, "data": None,
                    "error": {"type": "ConfirmRequired", "message": "Отменено"},
                    "error_message": "Отменено"}
        return git_mod.git_push(confirm=True)

    # --- network ---
    if name == "curl_request":
        return net_mod.curl_request(
            url=args.get("url", ""),
            method=args.get("method", "GET"),
            timeout=args.get("timeout", 10),
            headers=args.get("headers"),
        )
    if name == "dns_lookup":
        return net_mod.dns_lookup(host=args.get("host", ""))
    if name == "ping_host":
        return net_mod.ping_host(
            host=args.get("host", ""),
            count=args.get("count", 3),
            timeout=args.get("timeout", 5),
        )
    if name == "tcp_check":
        return net_mod.tcp_check(
            host=args.get("host", ""),
            port=args.get("port", 80),
            timeout=args.get("timeout", 5),
        )

    # --- audio ---
    if name == "tts_status":
        return audio_mod.tts_status()
    if name == "tts_speak":
        return audio_mod.tts_speak(text=args.get("text", ""))
    if name == "tts_stop":
        return audio_mod.tts_stop()
    if name == "audio_play":
        return audio_mod.audio_play(path=args.get("path", ""))

    # --- monitoring ---
    if name == "event_list":
        return mon_mod.event_list(
            limit=args.get("limit", 50),
            since_id=args.get("since_id", 0),
        )
    if name == "event_stats":
        return mon_mod.event_stats()
    if name == "ai_request_counter":
        return mon_mod.ai_request_counter()

    return {"ok": False, "success": False, "data": None,
            "error": {"type": "UnknownTool", "message": f"Неизвестная функция: {name}"},
            "error_message": f"Неизвестная функция: {name}"}

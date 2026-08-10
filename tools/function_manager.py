# tools/function_manager.py
"""
Исполнитель инструментов BERTA.
Поддерживает фоновый запуск долгих/GUI-команд.
"""

import json
import shlex
import subprocess
import os

from interface.terminal_ui import ui_print, ui_status
from core.event_bus import bus
from core.task_manager import task_manager


# Команды/программы, которые лучше сразу отпускать в detached-режим
DETACHED_PATTERNS = [
    "chrome", "chromium", "google-chrome", "firefox", "opera", "brave",
    "code", "cursor", "sublime", "gedit", "nautilus", "dolphin",
    "xterm", "gnome-terminal", "konsole", "vlc", "mpv",
    "telegram", "discord", "slack"
]


def _is_detached_candidate(command: str) -> bool:
    cmd_lower = command.lower()
    return any(p in cmd_lower for p in DETACHED_PATTERNS)


def execute_function(name: str, arguments: dict):
    """
    Главная точка входа.
    Возвращает результат (или информацию о фоновой задаче).
    """

    print()
    ui_print(f"[BERTA] → Вызов инструмента: {name}", bright=True)

    if arguments:
        ui_status("АРГУМЕНТЫ", json.dumps(arguments, ensure_ascii=False))

    bus.emit("tool", {
        "name": name,
        "arguments": arguments,
        "status": "started"
    }, source="function_manager")

    try:
        # ============================================================
        # SYSTEM COMMAND
        # ============================================================
        if name == "execute_system_command":

            command = arguments.get("command", "").strip()
            if not command:
                return {"success": False, "error": "Пустая команда"}

            # --- Проверка опасных операций ---
            dangerous_patterns = [
                "rm -rf", "dd if=", "> /dev/", "mkfs.", "fdisk",
                "parted", "shutdown", "reboot", "init 0", "poweroff",
                "mkfs", ":(){", "fork"
            ]

            cmd_lower = command.lower()
            dangerous = any(x in cmd_lower for x in dangerous_patterns)

            if dangerous:
                ui_print("[BERTA] ВНИМАНИЕ: Опасная операция!", bright=True, color="red")
                bus.emit("system", {
                    "message": f"Опасная команда требует подтверждения: {command}"
                }, source="function_manager")

                confirm = input("Подтвердите выполнение (Y/y): ")
                if confirm.lower() != "y":
                    bus.emit("tool", {
                        "name": name,
                        "status": "cancelled",
                        "reason": "user denied"
                    }, source="function_manager")
                    return {"success": False, "error": "Отказано пользователем"}

            # --- Решаем: фон или синхронно ---
            background = arguments.get("background", None)

            # Авто-определение: GUI-программы → detached
            if background is None and _is_detached_candidate(command):
                background = "detached"

            if background == "detached" or background is True:
                # Запускаем и сразу отпускаем
                task = task_manager.start_detached_process(
                    name=f"cmd:{command[:40]}",
                    command=command,
                    description=command,
                    shell=True
                )

                ui_print(f"[BERTA] Запущено в фоне (detached) → task {task.id}", color="green")
                bus.emit("tool", {
                    "name": name,
                    "status": "detached",
                    "task_id": task.id,
                    "command": command
                }, source="function_manager")

                return {
                    "success": True,
                    "background": True,
                    "detached": True,
                    "task_id": task.id,
                    "message": f"Команда запущена в фоне (PID будет в задачах). Task ID: {task.id}"
                }

            elif background == "wait":
                # Ждём завершения, но в отдельном потоке
                task = task_manager.start_process(
                    name=f"cmd:{command[:40]}",
                    command=command,
                    description=command,
                    shell=True
                )

                ui_print(f"[BERTA] Запущено в фоне (с ожиданием) → task {task.id}", color="green")
                return {
                    "success": True,
                    "background": True,
                    "detached": False,
                    "task_id": task.id,
                    "message": f"Команда выполняется в фоне. Task ID: {task.id}"
                }

            else:
                # Обычный синхронный запуск (короткие команды)
                try:
                    args = shlex.split(command)
                    result = subprocess.run(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=60
                    )

                    response = {
                        "success": result.returncode == 0,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                        "returncode": result.returncode
                    }

                    bus.emit("tool", {
                        "name": name,
                        "status": "completed",
                        "command": command,
                        "returncode": result.returncode
                    }, source="function_manager")

                    return response

                except subprocess.TimeoutExpired:
                    return {"success": False, "error": "Таймаут 60 секунд"}

        # ============================================================
        # READ FILE
        # ============================================================
        elif name == "read_file":
            filename = arguments.get("filename")
            if not filename:
                return {"success": False, "error": "Не указан filename"}

            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            bus.emit("tool", {
                "name": name,
                "status": "completed",
                "file": filename,
                "size": len(content)
            }, source="function_manager")

            return {
                "success": True,
                "file": filename,
                "code": content
            }

        # ============================================================
        # READ SELF CODE
        # ============================================================
        elif name == "read_self_code":
            # Читаем главный файл агента
            main_file = os.path.join(os.path.dirname(__file__), "..", "main.py")
            main_file = os.path.abspath(main_file)

            with open(main_file, "r", encoding="utf-8") as f:
                content = f.read()

            return {
                "success": True,
                "file": main_file,
                "code": content
            }

        # ============================================================
        # LIST TASKS (бонус)
        # ============================================================
        elif name == "list_tasks":
            only_active = arguments.get("only_active", False)
            tasks = task_manager.list_tasks(only_active=only_active)
            return {
                "success": True,
                "tasks": tasks,
                "count": len(tasks)
            }

        # ============================================================
        # Неизвестный инструмент
        # ============================================================
        else:
            bus.emit("error", {
                "message": f"Неизвестный инструмент: {name}"
            }, source="function_manager")

            return {
                "success": False,
                "error": f"Неизвестная функция: {name}"
            }

    except Exception as e:
        ui_print(f"[BERTA] Ошибка инструмента: {e}", bright=True, color="red")
        bus.emit("error", {
            "tool": name,
            "error": str(e)
        }, source="function_manager")

        return {
            "success": False,
            "error": str(e)
        }

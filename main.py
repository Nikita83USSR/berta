# main.py
"""
BERTA 0.1 Alpha
Консоль + Web UI (неблокирующий режим)
"""

import json
import threading
import queue
import sys

from core.brain import BertaBrain
from core.memory import Memory
from core.personality import BERTA_PERSONALITY
from core.event_bus import bus
from core.task_manager import task_manager

from interface.terminal_ui import (
    show_boot_screen,
    ui_status,
    ui_print
)

from interface.web.server import start_web_server, get_incoming_message

from tools.functions import FUNCTIONS
from tools.function_manager import execute_function


# Очередь сообщений от консоли
console_queue = queue.Queue()


def console_input_loop():
    """Читает ввод из консоли в отдельном потоке."""
    while True:
        try:
            line = input()
            console_queue.put(line)
        except EOFError:
            break
        except Exception:
            break


def process_user_message(user_text: str, brain: BertaBrain, memory: Memory, source: str = "console"):
    """Общая обработка сообщения (из консоли или веба)."""

    if not user_text.strip():
        return

    # Выход
    if user_text.lower() in ("exit", "quit", "выход"):
        ui_print("Завершение работы...", color="yellow")
        sys.exit(0)

    memory.add("user", user_text)

    bus.emit("chat", {
        "role": "user",
        "content": user_text,
        "source": source
    }, source=source)

    ui_status("THINK", "ANALYSIS")
    bus.emit("status", {"state": "thinking"}, source="brain")

    try:
        result = brain.ask(memory.get(), FUNCTIONS)
        message = result["choices"][0]["message"]

        # Логируем запрос к мозгу
        bus.emit("brain", {
            "direction": "request",
            "messages_count": len(memory.get())
        }, source="brain")

        # Function call
        if "function_call" in message:
            function_call = message["function_call"]
            name = function_call["name"]
            arguments = json.loads(function_call.get("arguments") or "{}")

            bus.emit("brain", {
                "direction": "function_call",
                "name": name,
                "arguments": arguments
            }, source="brain")

            tool_result = execute_function(name, arguments)

            memory.add("function", str(tool_result))

            # Второй запрос после инструмента
            result = brain.ask(memory.get())
            message = result["choices"][0]["message"]

        answer = message.get("content", "") or ""

        memory.add("assistant", answer)

        bus.emit("chat", {
            "role": "assistant",
            "content": answer,
            "source": "berta"
        }, source="brain")

        bus.emit("brain", {
            "direction": "response",
            "content_preview": answer[:300]
        }, source="brain")

        ui_status("ANSWER", "READY")
        print()
        ui_print("БЕРТА:", bright=True, color="green")
        print(answer)

    except Exception as e:
        err = str(e)
        ui_print("ОШИБКА: " + err, bright=True, color="red")
        bus.emit("error", {"message": err}, source="main")


def main():
    show_boot_screen()

    ui_status("BRAIN", "ЗАГРУЗКА")
    brain = BertaBrain()
    ui_status("GIGA", "READY")

    memory = Memory()
    memory.add("system", BERTA_PERSONALITY)
    ui_status("MEMORY", "READY")

    # --- Запуск веб-сервера ---
    ui_status("WEB", "STARTING")
    start_web_server(host="127.0.0.1", port=8742)
    ui_status("WEB", "http://127.0.0.1:8742")

    print()
    ui_print("BERTA 0.1 ONLINE", bright=True, color="green")
    ui_print("Консоль + Web UI активны. Пишите команды.", color="dim_green")
    print()

    # Поток чтения консоли
    t = threading.Thread(target=console_input_loop, daemon=True, name="console-input")
    t.start()

    # Главный цикл — обрабатываем и консоль, и веб
    while True:
        try:
            # 1. Сообщения из консоли
            try:
                user = console_queue.get(timeout=0.15)
                print(f"\nВЫ: {user}")          # эхо, т.к. input() уже съел строку
                process_user_message(user, brain, memory, source="console")
                print("\nВЫ: ", end="", flush=True)
            except queue.Empty:
                pass

            # 2. Сообщения из веб-UI
            web_msg = get_incoming_message(timeout=0.05)
            if web_msg:
                text = web_msg.get("text", "")
                ui_print(f"[WEB] → {text}", color="blue")
                process_user_message(text, brain, memory, source="web")
                print("\nВЫ: ", end="", flush=True)

        except KeyboardInterrupt:
            print("\n")
            ui_print("Остановка по Ctrl+C", color="yellow")
            break
        except Exception as e:
            ui_print("ОШИБКА цикла: " + str(e), bright=True, color="red")
            bus.emit("error", {"message": str(e)}, source="main")


if __name__ == "__main__":
    main()

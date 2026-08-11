"""
BERTA 0.2 — основной запуск.
Консоль + Web UI, локальный router, Function Calling, компактная память.
"""

import json
import queue
import sys
import threading

from core.brain import BertaBrain
from core.event_bus import bus
from core.memory import Memory
from core.personality import BERTA_PERSONALITY
from core.router import route
from config.settings import MAX_RECENT_MESSAGES, SUMMARY_TRIGGER
from interface.terminal_ui import ui_print, ui_status
from interface.web.server import start_web_server, get_incoming_message
from tools.function_manager import execute_function
from tools.functions import FUNCTIONS


console_queue = queue.Queue()


def console_input_loop():
    while True:
        try:
            console_queue.put(input())
        except (EOFError, KeyboardInterrupt):
            break


def _local_route_result(kind):
    if kind == "TIME":
        return execute_function("get_current_time", {})
    if kind == "DATE":
        return execute_function("get_current_date", {})
    if kind == "SYSTEM":
        return execute_function("get_system_status", {})
    return None


def _extract_message(result):
    choices = result.get("choices") or []
    if not choices:
        return {}
    return choices[0].get("message") or {}


def _tool_call_from_message(message):
    # Поддержка старого формата GigaChat.
    if message.get("function_call"):
        call = message["function_call"]
        return call.get("name"), call.get("arguments") or "{}"
    # И задел под современный формат tool_calls.
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        call = tool_calls[0]
        fn = call.get("function") or {}
        return fn.get("name"), fn.get("arguments") or "{}"
    return None, None


def _append_tool_exchange(memory, assistant_message, name, result):
    """Сохраняет обязательную пару assistant function_call -> function result."""
    memory.add_assistant_function_call(assistant_message)
    memory.add_function_result(name, result)


def _safe_tool_answer(tool_result):
    if not isinstance(tool_result, dict):
        return str(tool_result)
    if tool_result.get("success"):
        if tool_result.get("message"):
            return str(tool_result["message"])
        if tool_result.get("application"):
            return f"Приложение «{tool_result['application']}» запущено."
        if tool_result.get("path") and tool_result.get("pid"):
            return f"Готово: запущено для «{tool_result['path']}»."
        return "Операция выполнена успешно."
    return str(tool_result.get("error") or tool_result.get("message") or "Операция не выполнена.")

def process_user_message(user_text, brain, memory, source="console"):
    text = (user_text or "").strip()
    if not text:
        return

    if text.lower() in ("exit", "quit", "выход"):
        bus.emit("status", {"state": "offline"}, source="main")
        ui_print("Завершение работы...", color="yellow")
        raise SystemExit(0)

    bus.emit("chat", {"role": "user", "content": text, "source": source}, source=source)
    bus.emit("status", {"state": "thinking"}, source="router")

    try:
        decision = route(text)
        bus.emit(
            "router",
            {"kind": decision.kind, "confidence": decision.confidence, "reason": decision.reason},
            source="router",
        )

        local_result = _local_route_result(decision.kind)
        if local_result is not None:
            answer = (
                local_result.get("time")
                or local_result.get("date")
                or json.dumps(local_result, ensure_ascii=False)
            )
            memory.add("user", text)
            memory.add("assistant", answer)
            bus.emit("chat", {"role": "assistant", "content": answer, "source": "local"}, source="local")
            bus.emit("status", {"state": "idle"}, source="local")
            return

        memory.add("user", text)
        memory.compact_if_needed(SUMMARY_TRIGGER)

        # Очевидный DB/FUNCTION запрос всё ещё использует Function Calling:
        # router экономит лишние нейросетевые запросы только там, где действие можно выполнить
        # без понимания естественного языка. Для DB нужна модель, чтобы выбрать функцию/параметры.
        use_functions = FUNCTIONS if decision.kind in {"DATABASE", "FILE", "SYSTEM", "FUNCTION", "CHAT", "UNKNOWN"} else None

        bus.emit("status", {"state": "processing"}, source="brain")
        bus.emit("brain", {"direction": "request", "route": decision.kind, "messages_count": len(memory.get())}, source="brain")
        result = brain.ask(memory.get(), use_functions)
        message = _extract_message(result)
        tool_result = None

        # Function Calling может потребовать несколько последовательных инструментов.
        # Ограничение защищает от зацикливания модели.
        for _tool_round in range(4):
            name, raw_args = _tool_call_from_message(message)
            if not name:
                break
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except (json.JSONDecodeError, TypeError):
                arguments = {}

            bus.emit("status", {"state": "executing", "function": name}, source="function")
            bus.emit("brain", {"direction": "function_call", "name": name, "arguments": arguments}, source="brain")
            tool_result = execute_function(name, arguments)
            _append_tool_exchange(memory, message, name, tool_result)

            bus.emit("status", {"state": "processing"}, source="brain")
            try:
                # Повторно передаём functions: модель может безопасно выбрать следующий инструмент.
                result = brain.ask(memory.get(), use_functions)
                message = _extract_message(result)
            except Exception as followup_exc:
                # Действие уже могло успешно выполниться. Не зависаем и не теряем результат.
                if isinstance(tool_result, dict) and tool_result.get("success"):
                    answer = _safe_tool_answer(tool_result)
                    message = {"content": answer}
                    break
                raise followup_exc

        else:
            answer = "Выполнение остановлено: превышен лимит последовательных действий."
            message = {"content": answer}

        answer = (message.get("content") or "").strip()
        if not answer:
            answer = "Операция завершена, но текстового ответа от ядра не получено."

        memory.add("assistant", answer)
        bus.emit("chat", {"role": "assistant", "content": answer, "source": "berta"}, source="brain")
        bus.emit("brain", {"direction": "response", "content_preview": answer[:300]}, source="brain")
        bus.emit("status", {"state": "idle"}, source="brain")

        ui_print("БЕРТА:", bright=True, color="green")
        print(answer)

    except SystemExit:
        raise
    except Exception as exc:
        error = str(exc)
        ui_print("ОШИБКА: " + error, bright=True, color="red")
        bus.emit("status", {"state": "error"}, source="main")
        bus.emit("error", {"message": error}, source="main")


def main():
    ui_status("CORE", "BERTA 0.2")
    brain = BertaBrain()
    memory = Memory(BERTA_PERSONALITY, max_recent=MAX_RECENT_MESSAGES)

    ui_status("MEMORY", "READY")
    try:
        brain.get_token()
        ui_status("CORE", "READY")
    except Exception as exc:
        ui_status("CORE", "ERROR")
        ui_print(str(exc), color="yellow")

    try:
        start_web_server()
        ui_status("WEB", "http://0.0.0.0:8742")
    except Exception as exc:
        ui_status("WEB", f"ERROR · {exc}")

    bus.emit("status", {"state": "idle"}, source="main")
    ui_print("BERTA 0.2 ONLINE", bright=True, color="green")
    ui_print("Консоль + Web UI активны.", color="dim_green")

    threading.Thread(target=console_input_loop, daemon=True, name="console-input").start()

    while True:
        try:
            try:
                user = console_queue.get(timeout=0.15)
                print(f"\nВЫ: {user}")
                process_user_message(user, brain, memory, source="console")
            except queue.Empty:
                pass

            web_msg = get_incoming_message(timeout=0.05)
            if web_msg:
                process_user_message(web_msg.get("text", ""), brain, memory, source="web")

        except KeyboardInterrupt:
            bus.emit("status", {"state": "offline"}, source="main")
            ui_print("Остановка по Ctrl+C", color="yellow")
            break
        except SystemExit:
            break
        except Exception as exc:
            bus.emit("error", {"message": str(exc)}, source="main")
            ui_print("ОШИБКА цикла: " + str(exc), bright=True, color="red")


if __name__ == "__main__":
    main()

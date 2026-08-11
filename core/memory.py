"""Компактная память BERTA с корректным контекстом Function Calling."""

from collections import deque
import json


class Memory:
    def __init__(self, system_prompt: str = "", max_recent: int = 16):
        self.system_prompt = system_prompt or ""
        self.summary = ""
        self.profile = ""
        self.recent = deque(maxlen=max_recent)

    def add(self, role: str, content: str, name: str | None = None, **extra):
        item = {"role": role, "content": str(content)}
        if name:
            item["name"] = name
        for key, value in extra.items():
            if value is not None:
                item[key] = value
        self.recent.append(item)

    def add_assistant_function_call(self, message: dict):
        """Сохраняет assistant function_call без потери обязательной метаинформации."""
        item = {
            "role": "assistant",
            "content": message.get("content") or "",
        }
        if message.get("name"):
            item["name"] = message["name"]
        if message.get("function_call") is not None:
            item["function_call"] = message["function_call"]
        if message.get("tool_calls") is not None:
            item["tool_calls"] = message["tool_calls"]
        self.recent.append(item)

    def add_function_result(self, name: str, result):
        """Добавляет результат строго после соответствующего assistant call."""
        self.recent.append({
            "role": "function",
            "name": name,
            "content": self.compact_tool_result(result),
        })

    def set_summary(self, text: str):
        self.summary = (text or "").strip()

    def set_profile(self, text: str):
        self.profile = (text or "").strip()

    def get(self, current_query: str | None = None):
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        context_parts = []
        if self.profile:
            context_parts.append("ПРОФИЛЬ/СОСТОЯНИЕ:\n" + self.profile)
        if self.summary:
            context_parts.append("КРАТКАЯ ПАМЯТЬ ДИАЛОГА:\n" + self.summary)
        if context_parts:
            messages.append({"role": "system", "content": "\n\n".join(context_parts)})

        messages.extend(list(self.recent))
        if current_query is not None:
            messages.append({"role": "user", "content": current_query})
        return messages

    def recent_count(self):
        return len(self.recent)

    def compact_tool_result(self, result, max_chars: int = 3500) -> str:
        text = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
        return text if len(text) <= max_chars else text[:max_chars] + "\n[tool result truncated]"

    def build_summary(self):
        if not self.recent:
            return ""
        lines = []
        for item in list(self.recent)[-12:]:
            role = item.get("role", "unknown")
            content = str(item.get("content", ""))
            if role in {"tool", "function"}:
                continue
            if len(content) > 700:
                content = content[:700] + "…"
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def compact_if_needed(self, trigger: int = 24):
        if len(self.recent) < trigger:
            return False
        # Никогда не срезаем середину пары assistant function_call + function result.
        recent = list(self.recent)
        start = max(0, len(recent) - 8)
        while start > 0 and recent[start].get("role") == "function":
            start -= 1
        self.summary = self.build_summary()
        kept = recent[start:]
        self.recent.clear()
        self.recent.extend(kept)
        return True

    def clear(self):
        self.recent.clear()
        self.summary = ""
        self.profile = ""

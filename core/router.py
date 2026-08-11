"""
Лёгкий локальный маршрутизатор BERTA.

Router намеренно не использует нейросеть. Он определяет только очевидные случаи,
для которых безопаснее и быстрее локальная обработка.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    kind: str
    confidence: float = 1.0
    reason: str = ""


_TIME_RE = re.compile(
    r"\b(сколько\s+(?:сейчас\s+)?времени|текущее\s+время|который\s+час|время\s+сейчас)\b",
    re.I,
)
_DATE_RE = re.compile(
    r"\b(какое\s+сегодня\s+число|какая\s+сегодня\s+дата|сегодняшн(яя|ю)\s+дат[ау]|текущ(ая|ую)\s+дат[ау])\b",
    re.I,
)

def route(text: str) -> Route:
    value = (text or "").strip().lower()
    if not value:
        return Route("UNKNOWN", 0.0, "empty")

    if _TIME_RE.search(value):
        return Route("TIME", 0.99, "obvious time request")
    if _DATE_RE.search(value):
        return Route("DATE", 0.99, "obvious date request")

    # Только очевидные команды статуса, без попытки интерпретировать сложные вопросы.
    if value in {
        "статус",
        "состояние системы",
        "статус системы",
        "как система",
        "как там система",
    }:
        return Route("SYSTEM", 0.95, "obvious system status request")

    # Простые локальные запросы к файлам/системе остаются на стороне tools,
    # а естественно-языковые варианты передаются GigaChat для выбора функции.
    if any(k in value for k in ("покажи клиентов", "список клиентов", "клиенты в бд", "клиентов в бд")):
        return Route("DATABASE", 0.94, "obvious database request")

    if any(k in value for k in ("покажи задачи", "список задач", "активные задачи")):
        return Route("FUNCTION", 0.94, "obvious task request")

    return Route("CHAT", 0.55, "requires language understanding")

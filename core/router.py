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

_WEB_HINTS = (
    "поищи в интернете",
    "найди в интернете",
    "поиск в интернете",
    "открой сайт",
    "открой этот сайт",
    "есть ли у тебя доступ в интернет",
    "есть ли интернет",
    "погод",
    "weather",
    "температур",
    "прогноз",
    "новост",
    "курс доллар",
    "курс евро",
)
_GIT_HINTS = (
    "покажи git status",
    "git status",
    "покажи последние коммиты",
    "git log",
    "git branch",
)
_SYS_HINTS = (
    "проверь систему",
    "system info",
    "системная информация",
    "состояние системы",
)
_AI_COUNTER_HINTS = (
    "сколько запросов к ии",
    "сколько запросов к гигачат",
    "сколько запросов к gigachat",
    "счётчик запросов",
    "счетчик запросов",
    "ai_request_counter",
    "сколько было запросов",
)


def route(text: str) -> Route:
    value = (text or "").strip().lower()
    if not value:
        return Route("UNKNOWN", 0.0, "empty")

    if _TIME_RE.search(value):
        return Route("TIME", 0.99, "obvious time request")
    if _DATE_RE.search(value):
        return Route("DATE", 0.99, "obvious date request")

    if value in {
        "статус",
        "состояние системы",
        "статус системы",
        "как система",
        "как там система",
    }:
        return Route("SYSTEM", 0.95, "obvious system status request")

    if any(k in value for k in ("покажи клиентов", "список клиентов", "клиенты в бд", "клиентов в бд")):
        return Route("DATABASE", 0.94, "obvious database request")

    if any(k in value for k in ("покажи задачи", "список задач", "активные задачи")):
        return Route("FUNCTION", 0.94, "obvious task request")

    if any(h in value for h in _WEB_HINTS):
        return Route("CHAT", 0.92, "web/weather tool hint")
    if any(h in value for h in _GIT_HINTS):
        return Route("CHAT", 0.9, "git tool hint")
    if any(h in value for h in _SYS_HINTS):
        return Route("CHAT", 0.9, "system_info hint")
    if any(h in value for h in _AI_COUNTER_HINTS):
        return Route("CHAT", 0.95, "ai counter hint")
    if any(k in value for k in ("скажи голосом", "произнеси", "tts", "озвучь")):
        return Route("CHAT", 0.9, "tts hint")
    if any(k in value for k in ("покажи файлы", "прочитай readme", "прочитай файл", "list files")):
        return Route("CHAT", 0.85, "file tool hint")

    return Route("CHAT", 0.55, "requires language understanding")

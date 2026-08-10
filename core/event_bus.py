# core/event_bus.py
"""
Единый поток событий BERTA.
Все компоненты (консоль, веб, tools, brain) пишут сюда.
Веб-интерфейс и логи читают отсюда.
"""

import time
import threading
from collections import deque
from typing import Callable, Optional


class EventBus:

    def __init__(self, max_history: int = 2000):
        self._events = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._subscribers: list[Callable] = []
        self._id_counter = 0

    def emit(self, event_type: str, data=None, source: str = "system"):
        """
        event_type: chat | brain | tool | system | error | task | status
        """
        with self._lock:
            self._id_counter += 1
            event = {
                "id": self._id_counter,
                "time": time.time(),
                "type": event_type,
                "source": source,
                "data": data if data is not None else {}
            }
            self._events.append(event)

            # уведомляем подписчиков (веб-SSE и т.д.)
            for callback in self._subscribers:
                try:
                    callback(event)
                except Exception:
                    pass

            return event

    def subscribe(self, callback: Callable):
        """Подписка на новые события (для SSE)."""
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def get_history(self, since_id: int = 0, event_types: Optional[list] = None, limit: int = 500):
        """Получить историю событий (для начальной загрузки веб-UI)."""
        with self._lock:
            result = []
            for ev in self._events:
                if ev["id"] <= since_id:
                    continue
                if event_types and ev["type"] not in event_types:
                    continue
                result.append(ev)
                if len(result) >= limit:
                    break
            return result

    def clear(self):
        with self._lock:
            self._events.clear()


# Глобальный экземпляр — один на всё приложение
bus = EventBus()

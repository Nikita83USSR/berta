# BERTA — установка (главный файл: berta_agent.py)

## Запуск
```bash
cd berta_release   # или ваша папка проекта
# создайте .env при необходимости (ключ уже может быть внутри berta_agent.py)
pip install -r requirements.txt
python berta_agent.py
```

Веб-интерфейс: http://127.0.0.1:8742

Нужны модули:
- core/event_bus.py
- core/task_manager.py
- interface/web/ (server.py + static/)

Всё это уже в архиве.

# BERTA 0.2 update

Обновление реализует ТЗ 0.2 без изменения схемы MariaDB.

Запуск:
```bash
cp .env.example .env
# заполнить GIGACHAT_AUTH_KEY и параметры БД
python berta_agent.py
```

Старые инструкции `python berta_agent.py` продолжают работать: файл теперь является
совместимым launcher для модульного `main.py`.

Проверка:
```bash
python -m compileall -q .
python -m py_compile berta_agent.py main.py core/*.py tools/*.py interface/*.py interface/web/*.py
```

Важно: в репозитории больше нет функций `read_self_code` / `write_self_code`.
Файл `.env` не должен попадать в Git.

# BERTA 0 — INSTALLATION

## Требования

Linux.

Рекомендуется Debian.

Необходимы:

- Python 3.13+
- python3-venv
- pip
- MariaDB
- доступ к GigaChat API

---

## 1. Скачать проект

    git clone https://github.com/Nikita83USSR/berta.git

    cd berta

---

## 2. Создать virtualenv

    python3 -m venv venv

    source venv/bin/activate

---

## 3. Установить зависимости

    pip install -r requirements.txt

Если requirements.txt неполный:

    pip install pymysql requests python-dotenv urllib3

---

## 4. Создать конфигурацию

Создать:

    .env

Секреты НЕ коммитить.

Пример структуры:

    GIGACHAT_AUTH_KEY=YOUR_KEY
    GIGACHAT_SCOPE=GIGACHAT_API_PERS

    DB_HOST=127.0.0.1
    DB_PORT=3306
    DB_NAME=berta
    DB_USER=berta
    DB_PASSWORD=YOUR_PASSWORD

Точные имена переменных необходимо сверить с config/settings.py.

---

## 5. Настроить MariaDB

Создать БД и пользователя.

Затем выполнить:

    mysql -u root -p < database/migrations.sql

Проверить параметры подключения в конфигурации.

---

## 6. Проверить Python

    python -m py_compile main.py

Если используется legacy-вход:

    python -m py_compile berta_agent.py

---

## 7. Запуск

Основной модуль:

    python main.py

Legacy:

    python berta_agent.py

---

## 8. Первый запуск

При успешном запуске ожидаются сообщения о:

- CORE;
- MEMORY;
- DATABASE;
- GigaChat LINK.

После этого появляется:

    ВЫ:

---

## 9. Что запросить у владельца проекта

Если проект разворачивает другой ИИ или разработчик, необходимо запросить у владельца:

1. GigaChat authorization key.
2. GigaChat scope, если он отличается от значения по умолчанию.
3. MariaDB host.
4. MariaDB port.
5. MariaDB database.
6. MariaDB user.
7. MariaDB password.

Не просить пользователя публиковать эти данные в GitHub.

---

## 10. Диагностика

Если:

    ModuleNotFoundError

проверить:

    which python
    which pip
    pip install -r requirements.txt

Если проблема с MariaDB:

    проверить DB_* параметры;
    проверить доступность MariaDB;
    проверить database/migrations.sql.

Если проблема с GigaChat:

    проверить GIGACHAT_AUTH_KEY;
    проверить OAuth endpoint;
    проверить сетевой доступ.

Если ошибка SSL:

    проверить текущую конфигурацию requests/urllib3.

---

## 11. Разработка

Перед изменением:

    git status
    git log -1 --oneline

После изменения:

    python -m py_compile main.py

и выполнить запуск.

После успешной проверки:

    git add .
    git commit -m "описание изменения"
    git push

---

## 12. Безопасность

НЕ загружать в Git:

- .env
- API keys
- пароли
- токены
- приватные ключи
- реальные дампы БД
- персональные данные клиентов.

Репозиторий является публичным.

---

## 13. Контекст проекта

Для понимания архитектуры читать:

    README.md
    PROJECT_PASSPORT.md
    DEVELOPMENT_LOG.md
    main.py

Затем:

    core/
    tools/
    config/
    database/
    interface/

И только после этого legacy:

    berta_agent.py

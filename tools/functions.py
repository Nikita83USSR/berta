"""Инструменты BERTA: БД, файлы, приложения, интернет, система, git, TTS, мониторинг."""

FUNCTIONS = [
    # --- existing ---
    {"name": "get_current_time", "description": "Получить текущее локальное время. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_current_date", "description": "Получить текущую локальную дату. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_system_status", "description": "Получить состояние ОС, desktop environment, Python и BERTA. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {"name": "list_clients", "description": "Показать клиентов из MariaDB. SAFE.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "1..200"}}}},
    {"name": "read_client_balance", "description": "Получить данные клиента по ID. SAFE.", "parameters": {"type": "object", "properties": {"client_id": {"type": "integer"}}, "required": ["client_id"]}},
    {"name": "delete_client_by_name", "description": "Удалить клиентов с точно указанным именем. Только по явной команде и с подтверждением. CONFIRM.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "read_file", "description": "Прочитать текстовый локальный файл по указанному пути (sandbox). SAFE для разрешённых путей.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}},
    {"name": "list_directory", "description": "Показать содержимое папки. Умеет понимать ~, домашнюю папку и абсолютные пути. SAFE.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Путь к папке, например ~/Downloads"}, "include_hidden": {"type": "boolean"}}, "required": ["path"]}},
    {"name": "find_files", "description": "Найти файлы или папки по имени в указанном месте. Не сканировать весь диск без явного запроса. SAFE.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Имя или часть имени"}, "path": {"type": "string", "description": "Корень поиска, по умолчанию ~"}, "kind": {"type": "string", "description": "file, dir или any"}, "max_results": {"type": "integer", "description": "1..100"}}, "required": ["query"]}},
    {"name": "get_desktop_info", "description": "Определить Linux desktop environment/session и доступные графические механизмы. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {"name": "list_applications", "description": "Найти установленные графические приложения по .desktop и PATH. SAFE.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Необязательное название приложения"}, "max_results": {"type": "integer"}}}},
    {"name": "launch_application", "description": "Запустить приложение по смыслу запроса. CONFIRM/LEVEL 2.", "parameters": {"type": "object", "properties": {"application": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}}, "required": ["application"]}},
    {"name": "open_path", "description": "Открыть файл или папку системным графическим обработчиком. CONFIRM.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "list_processes", "description": "Показать запущенные процессы. SAFE.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}}},
    {"name": "terminate_process", "description": "Завершить процесс по PID или имени. CONFIRM.", "parameters": {"type": "object", "properties": {"pid": {"type": "integer"}, "name": {"type": "string"}}}},
    {"name": "execute_system_command", "description": "Выполнить системную команду Linux (устаревший путь; предпочтителен system_command). CONFIRM для нестандартных.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "background": {"type": "string"}}, "required": ["command"]}},
    {"name": "list_tasks", "description": "Показать фоновые задачи BERTA. SAFE.", "parameters": {"type": "object", "properties": {"only_active": {"type": "boolean"}}}},

    # --- GROUP 1: Internet / Web ---
    {
        "name": "web_search",
        "description": "Поиск в Интернете с приоритетом RU-источников (новости Lenta/RIA/RBC/TASS, Wikipedia.ru; зарубежные — запасные). SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "limit": {"type": "integer", "description": "Число результатов 1..10"},
                "language": {"type": "string", "description": "Например ru-ru"},
            },
            "required": ["query"],
        },
    },

    {
        "name": "weather",
        "description": "Узнать текущую погоду (Open-Meteo, запасной wttr.in). Для вопросов про погоду/температуру используй ЭТОТ инструмент. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Город или населённый пункт, например Москва, Чучково, СПб"},
                "query": {"type": "string", "description": "Альтернатива: свободный запрос «погода в Чучково»"},
            },
        },
    },
    {
        "name": "web_open",
        "description": "Открыть HTTP/HTTPS URL и извлечь читаемый текст страницы. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout": {"type": "integer"},
                "max_length": {"type": "integer"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_fetch",
        "description": "HTTP GET/HEAD: status, headers и ограниченное тело. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "description": "GET или HEAD"},
                "timeout": {"type": "integer"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_download",
        "description": "Скачать файл только в ~/.berta/downloads. SAFE с ограничениями.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "dest_name": {"type": "string"},
                "timeout": {"type": "integer"},
            },
            "required": ["url"],
        },
    },

    # --- GROUP 2: HTTP / API ---
    {
        "name": "http_request",
        "description": "HTTP-запрос GET/POST/PUT/PATCH/DELETE. POST/PUT/PATCH/DELETE — CONFIRM. SSRF-защита, без private network.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string"},
                "headers": {
                    "type": "object",
                    "description": "HTTP-заголовки (ключ-значение строки)",
                    "properties": {},
                },
                "params": {
                    "type": "object",
                    "description": "Query-параметры",
                    "properties": {},
                },
                "json": {
                    "type": "object",
                    "description": "JSON-тело запроса",
                    "properties": {},
                },
                "body": {"type": "string"},
                "timeout": {"type": "integer"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "api_request",
        "description": "Вызов заранее разрешённого API. Секреты только из .env. SAFE для allowlist.",
        "parameters": {
            "type": "object",
            "properties": {
                "api_name": {"type": "string"},
                "params": {
                    "type": "object",
                    "description": "Query-параметры",
                    "properties": {},
                },
                "json": {
                    "type": "object",
                    "description": "JSON-тело",
                    "properties": {},
                },
                "timeout": {"type": "integer"},
            },
            "required": ["api_name"],
        },
    },

    # --- GROUP 3: System ---
    {
        "name": "system_command",
        "description": "Безопасный запуск локальной команды по allowlist (pwd, ls, df, free, uptime, whoami, hostname, date, uname, git status/log/branch, find в sandbox, systemctl status). Нестандартные — CONFIRM. FORBIDDEN: rm -rf, sudo, reboot и т.п.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer"},
                "cwd": {"type": "string"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "system_info",
        "description": "ОС, kernel, CPU, RAM, disk, hostname, Python, версия BERTA. SAFE.",
        "parameters": {"type": "object", "properties": {}},
    },

    # --- GROUP 4: Files (sandbox) ---
    {
        "name": "file_list",
        "description": "Список файлов в sandbox-каталоге. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "include_hidden": {"type": "boolean"},
                "max_items": {"type": "integer"},
            },
        },
    },
    {
        "name": "file_read",
        "description": "Прочитать файл из sandbox (не .env/SSH keys). SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_length": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": "Записать файл в sandbox. CONFIRM.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "file_append",
        "description": "Дописать в файл в sandbox. CONFIRM.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "file_exists",
        "description": "Проверить существование пути в sandbox. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "file_info",
        "description": "Метаданные файла/папки в sandbox. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "file_search",
        "description": "Поиск файлов по имени в sandbox. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string"},
                "kind": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },

    # --- GROUP 5: Git ---
    {"name": "git_status", "description": "git status (read-only). SAFE.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "git_log", "description": "Последние коммиты. SAFE.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}, "path": {"type": "string"}}}},
    {"name": "git_branch", "description": "Список веток. SAFE.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "git_diff", "description": "git diff --stat. SAFE.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "staged": {"type": "boolean"}}}},
    {"name": "git_show", "description": "git show ref. SAFE.", "parameters": {"type": "object", "properties": {"ref": {"type": "string"}, "path": {"type": "string"}}}},
    {"name": "git_add", "description": "git add. CONFIRM, по умолчанию отключён без подтверждения.", "parameters": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}}}},
    {"name": "git_commit", "description": "git commit. CONFIRM.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
    {"name": "git_pull", "description": "git pull --ff-only. CONFIRM.", "parameters": {"type": "object", "properties": {}}},
    {"name": "git_push", "description": "git push. CONFIRM.", "parameters": {"type": "object", "properties": {}}},

    # --- GROUP 6: Network diagnostics ---
    {
        "name": "curl_request",
        "description": "Диагностика HTTP как curl: status, headers, body, elapsed. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string"},
                "timeout": {"type": "integer"},
                "headers": {
                    "type": "object",
                    "description": "HTTP-заголовки",
                    "properties": {},
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "dns_lookup",
        "description": "DNS lookup хоста. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {"host": {"type": "string"}},
            "required": ["host"],
        },
    },
    {
        "name": "ping_host",
        "description": "ping хоста (не private). SAFE с лимитами.",
        "parameters": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "count": {"type": "integer"},
                "timeout": {"type": "integer"},
            },
            "required": ["host"],
        },
    },
    {
        "name": "tcp_check",
        "description": "Проверка TCP-порта (один порт, не mass scan). SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "timeout": {"type": "integer"},
            },
            "required": ["host", "port"],
        },
    },

    # --- GROUP 7: TTS ---
    {"name": "tts_status", "description": "Статус Piper TTS, модель, готовность. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "tts_speak",
        "description": "Произнести текст голосом ru_RU-irina-medium через Piper. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {"name": "tts_stop", "description": "Остановить воспроизведение TTS если поддерживается. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "audio_play",
        "description": "Воспроизвести аудиофайл из разрешённого каталога. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },

    # --- GROUP 8: Events / Monitoring ---
    {
        "name": "event_list",
        "description": "Последние события EventBus. SAFE.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "since_id": {"type": "integer"},
            },
        },
    },
    {"name": "event_stats", "description": "Статистика событий и AI-запросов. SAFE.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "ai_request_counter",
        "description": "Счётчик запросов к GigaChat: total/success/error, среднее время, токены. SAFE.",
        "parameters": {"type": "object", "properties": {}},
    },
]

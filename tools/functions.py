# tools/functions.py
"""
Список инструментов, которые GigaChat может вызывать.
"""

FUNCTIONS = [

    {
        "name": "read_client_balance",
        "description": "Получает данные клиента из таблицы clients по его ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "integer",
                    "description": "ID клиента"
                }
            },
            "required": ["client_id"]
        }
    },

    {
        "name": "delete_client_by_name",
        "description": "Удаляет клиентов с точно указанным именем из таблицы clients.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Точное имя клиента"
                }
            },
            "required": ["name"]
        }
    },

    {
        "name": "read_self_code",
        "description": "Читает текущий исходный код BERTA (main.py).",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },

    {
        "name": "write_self_code",
        "description": "Перезаписывает исходный код BERTA.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Полный новый исходный код"
                }
            },
            "required": ["code"]
        }
    },

    {
        "name": "read_file",
        "description": "Читает содержимое файла и возвращает его содержимое.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Путь к файлу"
                }
            },
            "required": ["filename"]
        }
    },

    {
        "name": "execute_system_command",
        "description": (
            "Выполняет системную команду. "
            "Для GUI-программ (Chrome, Firefox и т.д.) и долгих процессов "
            "автоматически запускает в фоне (detached), чтобы не блокировать BERTA. "
            "Опасные операции требуют подтверждения."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Системная команда"
                },
                "background": {
                    "type": "string",
                    "description": (
                        "Режим запуска: "
                        "'detached' — запустить и отпустить (для Chrome и GUI), "
                        "'wait' — выполнить в фоне и дождаться результата, "
                        "null/не указывать — авто-определение или синхронно"
                    )
                }
            },
            "required": ["command"]
        }
    },

    {
        "name": "list_tasks",
        "description": "Показывает список фоновых задач BERTA (активные и завершённые).",
        "parameters": {
            "type": "object",
            "properties": {
                "only_active": {
                    "type": "boolean",
                    "description": "Если true — показать только активные задачи"
                }
            }
        }
    }

]

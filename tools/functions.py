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
            "required": [
                "client_id"
            ]
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
            "required": [
                "name"
            ]
        }
    },


    {
        "name": "read_self_code",
        "description": "Читает текущий исходный код BERTA.",
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
            "required": [
                "code"
            ]
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
            "required": [
                "filename"
            ]
        }
    },


    {
        "name": "execute_system_command",
        "description": "Выполняет системную команду. Опасные операции требуют подтверждения.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Системная команда"
                }
            },
            "required": [
                "command"
            ]
        }
    }

]

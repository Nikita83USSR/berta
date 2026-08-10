import warnings
warnings.filterwarnings('ignore', category=Warning)
import os
import json
import time
import uuid
import requests
import pymysql
import logging
import hashlib
import subprocess
import shlex

# ============================================================
# НАСТРОЙКИ
# ============================================================

GIGACHAT_AUTH_KEY = "MDE5ZmU1ZjYtODU2Ni03NDdjLWEwOTUtYjA2ZDA5MzRkZGY1OmZlZDY5NWZmLTljMTctNDk4OS1hZDY5LTIwZTUzYWU1Y2Q5NQ=="

GIGACHAT_SCOPE = "GIGACHAT_API_PERS"

GIGACHAT_API = "https://api.giga.chat/v1"

GIGACHAT_OAUTH = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

MODEL = "GigaChat-2"

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_NAME = "berta_db"
DB_USER = "berta_user"
DB_PASSWORD = "berta0"

SELF_FILE = os.path.abspath(__file__)

HTTP_TIMEOUT = 120

LOG_FILE = "berta.log"

# ============================================================
# TERMINAL UI
# ============================================================

GREEN = "\033[92m"
DIM_GREEN = "\033[32m"
RESET = "\033[0m"
BOLD = "\033[1m"

BERTA_ASCII = r"""
... ⠀⠀⠀⠀⡀⠀⠀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⢸⠉⣹⠋⠉⢉⡟⢩⢋⠋⣽⡻⠭⢽⢉⠯⠭⠭⠭⢽⡍⢹⡍⠙⣯⠉⠉⠉⠉⠉⣿⢫⠉⠉⠉⢉⡟⠉⢿⢹⠉⢉⣉⢿⡝⡉⢩⢿⣻⢍⠉⠉⠩⢹⣟⡏⠉⠹⡉⢻⡍⡇
⠀⢸⢠⢹⠀⠀⢸⠁⣼⠀⣼⡝⠀⠀⢸⠘⠀⠀⠀⠀⠈⢿⠀⡟⡄⠹⣣⠀⠀⠐⠀⢸⡘⡄⣤⠀⡼⠁⠀⢺⡘⠉⠀⠀⠀⠫⣪⣌⡌⢳⡻⣦⠀⠀⢃⡽⡼⡀⠀⢣⢸⠸⡇
⠀⢸⡸⢸⠀⠀⣿⠀⣇⢠⡿⠀⠀⠀⠸⡇⠀⠀⠀⠀⠀⠘⢇⠸⠘⡀⠻⣇⠀⠀⠄⠀⡇⢣⢛⠀⡇⠀⠀⣸⠇⠀⠀⠀⠀⠀⠘⠄⢻⡀⠻⣻⣧⠀⠀⠃⢧⡇⠀⢸⢸⡇⡇
⠀⢸⡇⢸⣠⠀⣿⢠⣿⡾⠁⠀⢀⡀⠤⢇⣀⣐⣀⠀⠤⢀⠈⠢⡡⡈⢦⡙⣷⡀⠀⠀⢿⠈⢻⣡⠁⠀⢀⠏⠀⠀⠀⢀⠀⠄⣀⣐⣀⣙⠢⡌⣻⣷⡀⢹⢸⡅⠀⢸⠸⡇⡇
⠀⢸⡇⢸⣟⠀⢿⢸⡿⠀⣀⣶⣷⣾⡿⠿⣿⣿⣿⣿⣿⣶⣬⡀⠐⠰⣄⠙⠪⣻⣦⡀⠘⣧⠀⠙⠄⠀⠀⠀⠀⠀⣨⣴⣾⣿⠿⣿⣿⣿⣿⣿⣶⣯⣿⣼⢼⡇⠀⢸⡇⡇⡇
⠀⢸⢧⠀⣿⡅⢸⣼⡷⣾⣿⡟⠋⣿⠓⢲⣿⣿⣿⡟⠙⣿⠛⢯⡳⡀⠈⠓⠄⡈⠚⠿⣧⣌⢧⠀⠀⠀⠀⠀⣠⣺⠟⢫⡿⠓⢺⣿⣿⣿⠏⠙⣏⠛⣿⣿⣾⡇⢀⡿⢠⠀⡇
⠀⢸⢸⠀⢹⣷⡀⢿⡁⠀⠻⣇⠀⣇⠀⠘⣿⣿⡿⠁⠐⣉⡀⠀⠁⠀⠀⠀⠀⠀⠀⠀⠀⠉⠓⠳⠄⠀⠀⠀⠀⠋⠀⠘⡇⠀⠸⣿⣿⠟⠀⢈⣉⢠⡿⠁⣼⠁⣼⠃⣼⠀⡇
⠀⢸⠸⣀⠈⣯⢳⡘⣇⠀⠀⠈⡂⣜⣆⡀⠀⠀⢀⣀⡴⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢽⣆⣀⠀⠀⠀⣀⣜⠕⡊⠀⣸⠇⣼⡟⢠⠏⠀⡇
⠀⢸⠀⡟⠀⢸⡆⢹⡜⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⠋⣾⡏⡇⡎⡇⠀⡇
⠀⢸⠀⢃⡆⠀⢿⡄⠑⢽⣄⠀⠀⠀⢀⠂⠠⢁⠈⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠄⡐⢀⠂⠀⠀⣠⣮⡟⢹⣯⣸⣱⠁⠀⡇
⠀⠈⠉⠉⠋⠉⠉⠋⠉⠉⠉⠋⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠋⡟⠉⠉⡿⠋⠋⠋⠉⠉⠁ 
Разработчик Никита Маркин) ...
"""

def ui_print(text="", bright=False, color=None):
    # Цветовые коды ANSI
    RED = "\033[91m"       # Ошибки
    YELLOW = "\033[93m"    # Предупреждения / Запросы
    BLUE = "\033[94m"      # Действия агента
    GREEN = "\033[92m"     
    DIM_GREEN = "\033[32m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Выбираем базовый цвет
    if color == "red":
        prefix = RED
    elif color == "yellow":
        prefix = YELLOW
    elif color == "blue":
        prefix = BLUE
    elif color == "green":
        prefix = GREEN
    elif color == "dim_green":
        prefix = DIM_GREEN
    else:
        # По умолчанию зеленый/тускло-зеленый
        prefix = GREEN if bright else DIM_GREEN

    # Если нужен жирный шрифт (кроме красного)
    if bright and color != "red":
        prefix += BOLD

    print(prefix + str(text) + RESET)

def ui_status(label, status="OK"):
    print(DIM_GREEN + f"[ {label:<8} ]" + RESET + " " + GREEN + status + RESET)

def show_boot_screen():
    print(GREEN + BOLD + BERTA_ASCII + RESET)
    print()
    ui_print("B E R T A   0", bright=True)
    ui_print("AUTONOMOUS LOCAL INTELLIGENCE SYSTEM")
    print()
    ui_status("CORE", "ИНИЦИАЛИЗАЦИЯ")


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

# BERTA 0.1 SSL FIX
# Debian не доверяет цепочке Sber сертификатов
session.verify = False

session.headers.update({
    "User-Agent": "BERTA-0/1.0",
    "Accept": "application/json",
})


# ============================================================
# ПОЛУЧЕНИЕ ACCESS TOKEN
# ============================================================

access_token = None
token_expires_at = 0

def get_giga_token():
    global access_token
    global token_expires_at

    if access_token and time.time() < token_expires_at - 60:
        return access_token

    rquid = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": rquid,
        "Authorization": "Basic " + GIGACHAT_AUTH_KEY,
    }

    data = {
        "scope": GIGACHAT_SCOPE
    }

    print("[BERTA] Обновляю защищённое соединение...")

    try:
        response = session.post(
            GIGACHAT_OAUTH,
            headers=headers,
            data=data,
            timeout=30
        )
    except requests.RequestException as e:
        raise RuntimeError("Ошибка соединения с внешним шлюзом авторизации: " + str(e))

    if response.status_code != 200:
        print()
        print("========== ОШИБКА OAUTH ==========")
        print("HTTP:", response.status_code)
        print("RqUID:", rquid)
        print("Ответ сервера:")
        print(response.text[:3000])
        print("==================================")
        print()
        raise RuntimeError(f"OAuth вернул HTTP {response.status_code}")

    if not response.text.strip():
        raise RuntimeError("OAuth вернул пустой ответ.")

    try:
        result = response.json()
    except json.JSONDecodeError:
        print()
        print("========== ОШИБКА OAUTH ==========")
        print("Сервер вернул не JSON:")
        print(response.text[:3000])
        print("==================================")
        print()
        raise RuntimeError("OAuth вернул некорректный JSON.")

    token = result.get("access_token")
    if not token:
        print("Ответ OAuth:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise RuntimeError("В ответе OAuth отсутствует access_token.")

    access_token = token
    expires_at = result.get("expires_at")
    if expires_at:
        token_expires_at = int(expires_at)
    else:
        token_expires_at = int(time.time()) + 1800

    print("[BERTA] Защищённое соединение установлено.")
    return access_token


# ============================================================
# GIGACHAT API
# ============================================================

def giga_request(messages, functions=None):
    global access_token
    token = get_giga_token()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
    }
    payload = {
        "model": MODEL,
        "messages": messages,
    }
    if functions:
        payload["functions"] = functions
        payload["function_call"] = "auto"

    try:
        response = session.post(
            GIGACHAT_API + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=HTTP_TIMEOUT
        )
    except requests.RequestException as e:
        raise RuntimeError("Ошибка соединения с нейросетевым ядром: " + str(e))

    if response.status_code == 401:
        access_token = None
        token = get_giga_token()
        headers["Authorization"] = "Bearer " + token
        response = session.post(
            GIGACHAT_API + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=HTTP_TIMEOUT
        )

    if response.status_code != 200:
        print()
        print("========== ОШИБКА НЕЙРОСЕТЕВОГО ЯДРА ==========")
        print("HTTP:", response.status_code)
        print(response.text[:5000])
        print("=====================================")
        print()
        raise RuntimeError(f"Нейросетевое ядро вернуло HTTP {response.status_code}")

    try:
        return response.json()
    except json.JSONDecodeError:
        raise RuntimeError("Нейросетевое ядро вернуло некорректный JSON.")


# ============================================================
# MARIA DB
# ============================================================

def get_db():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# ============================================================
# MEMORY: REMEMBER SELF CHANGE
# ============================================================

def remember_self_change(change_type, function_name, description, code_version=None, status="active"):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO berta_self_changes
                (
                    change_type,
                    function_name,
                    description,
                    code_version,
                    status
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    change_type,
                    function_name,
                    description,
                    code_version,
                    status
                )
            )
            return {
                "success": True,
                "message": "Изменение BERTA сохранено в памяти.",
                "id": cursor.lastrowid
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


# ============================================================
# MEMORY: READ SELF CHANGES
# ============================================================

def read_self_changes(limit=20):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, created_at, change_type, function_name,
                       description, code_version, status
                FROM berta_self_changes
                ORDER BY id DESC
                LIMIT %s
                """,
                (int(limit),)
            )
            rows = cursor.fetchall()
            for row in rows:
                if row.get("created_at"):
                    row["created_at"] = row["created_at"].isoformat()
            return {
                "success": True,
                "changes": rows,
                "count": len(rows)
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


# ============================================================
# TOOL: DELETE CLIENT BY NAME
# ============================================================

def delete_client_by_name(name):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, phone, status, balance FROM clients WHERE name = %s",
                (name,)
            )
            rows = cursor.fetchall()
            if not rows:
                return {"success": False, "message": "Клиент не найден", "deleted": 0}
            cursor.execute("DELETE FROM clients WHERE name = %s", (name,))
            return {"success": True, "message": "Клиент удалён.", "deleted": cursor.rowcount, "clients": rows}
    finally:
        db.close()


# ============================================================
# TOOL: READ CLIENT BALANCE
# ============================================================

def read_client_balance(client_id):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM clients
                WHERE id = %s
                LIMIT 1
                """,
                (client_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "success": False,
                    "message": "Клиент не найден"
                }
            return {
                "success": True,
                "client": row
            }
    finally:
        db.close()


# ============================================================
# TOOL: READ OWN CODE
# ============================================================

def read_self_code():
    try:
        with open(SELF_FILE, "r", encoding="utf-8") as f:
            code = f.read()
        return {
            "success": True,
            "file": SELF_FILE,
            "code": code
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# TOOL: WRITE OWN CODE
# ============================================================

def write_self_code(code):
    try:
        backup_file = SELF_FILE + ".backup"
        with open(SELF_FILE, "r", encoding="utf-8") as f:
            old_code = f.read()
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(old_code)
        temp_file = SELF_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code)
        os.replace(temp_file, SELF_FILE)
        code_version = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        memory_result = remember_self_change(
            change_type="self_modification",
            function_name="write_self_code",
            description="БЕРТА изменила собственный исходный код.",
            code_version=code_version,
            status="active"
        )
        return {
            "success": True,
            "message": "Код БЕРТЫ успешно обновлён.",
            "file": SELF_FILE,
            "backup": backup_file,
            "code_version": code_version,
            "memory": memory_result,
            "restart_required": True
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
        # ============================================================
# NEW TOOL: READ ANY FILE
# ============================================================

def read_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return {
                "success": True,
                "file": filename,
                "code": f.read()
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# NEW TOOL: EXECUTE SYSTEM COMMAND
# ============================================================

def execute_system_command(command):
    dangerous_patterns = [
        'rm -rf', 'dd if=', '> /dev/', 'mkfs.', 'fdisk', 'parted',
        'shutdown', 'reboot', 'init 0', 'poweroff'
    ]
    cmd_lower = command.lower()
    is_dangerous = any(pattern in cmd_lower for pattern in dangerous_patterns)

    if is_dangerous:
        ui_print(f"[BERTA] ЗАПРОС ОПАСНОЙ КОМАНДЫ:", bright=True)
        ui_print(f"ДЕЙСТВИЕ: {command}")
        confirm = input("Подтвердите выполнение (Y/y для согласия): ").strip().lower()
        if confirm != 'y':
            return {"success": False, "error": "Отказано в доступе: пользователь не подтвердил опасную операцию."}

    try:
        args = shlex.split(command)
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except FileNotFoundError:
        return {"success": False, "error": f"Команда не найдена: {args[0]}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Таймаут выполнения команды (60 сек)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# ОПИСАНИЯ ФУНКЦИЙ ДЛЯ GIGACHAT
# ============================================================

FUNCTIONS = [
{
    "name": "get_current_time",
    "description": "Возвращает текущее время системы Linux.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
},
    {
        "name": "read_client_balance",
        "description": "Получает данные клиента из таблицы clients по его ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID клиента"}
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
                "name": {"type": "string", "description": "Точное имя клиента"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "read_self_code",
        "description": "Читает текущий исходный код BERTA.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "write_self_code",
        "description": "Перезаписывает исходный код BERTA.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Полный новый исходный код"}
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
                "filename": {"type": "string", "description": "Путь к файлу"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "execute_system_command",
        "description": "Выполняет системную команду. Опасные операции требуют подтверждения.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Системная команда"}
            },
            "required": ["command"]
        }
    }
]


# ============================================================
# ВЫЗОВ ЛОКАЛЬНОЙ ФУНКЦИИ
# ============================================================

def get_current_time():
    import datetime
    return {
        "success": True,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def execute_function(name, arguments):
    print()
    # === VERBOSE LOGGING: Показываем, что мы собираемся делать ===
    ui_print(f"[BERTA] -> Вызов инструмента: {name}", bright=True)
    if arguments:
        ui_status("АРГУМЕНТЫ", json.dumps(arguments, ensure_ascii=False))
    
    try:
        # --- ИНСТРУМЕНТ: Получение текущего времени ---
        if name == "get_current_time":
            return {
                "success": True,
                "time": time.strftime("%Y-%m-%d %H:%M:%S")
            }

        # --- ИНСТРУМЕНТ: Выполнение системных команд ---
        if name == "execute_system_command":
            command = arguments.get("command")
            dangerous_patterns = [
                'rm -rf', 'dd if=', '> /dev/', 'mkfs.', 'fdisk', 'parted',
                'shutdown', 'reboot', 'init 0', 'poweroff'
            ]
            cmd_lower = command.lower()
            is_dangerous = any(pattern in cmd_lower for pattern in dangerous_patterns)

            if is_dangerous:
                ui_print(f"[BERTA] ВНИМАНИЕ: Опасная операция!", bright=True)
                ui_print(f"ДЕЙСТВИЕ: {command}")
                confirm = input("Подтвердите выполнение (Y/y для согласия): ").strip().lower()
                if confirm != 'y':
                    return {"success": False, "error": "Отказано в доступе."}

                        # --- НОВЫЙ ИСПРАВЛЕННЫЙ БЛОК ЗАПУСКА ---
            args = shlex.split(command)
            
            try:
                result = subprocess.run(
                    args, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.DEVNULL, # Скрываем "Permission denied"
                    text=True, 
                    timeout=60
                )
            except FileNotFoundError:
                ui_print("[BERTA] ОШИБКА: Команда не найдена", bright=True, color="red")
                return {"success": False, "error": f"Команда {args[0]} не существует."}

            # Если команда реально сломалась (например, опечатка), спросим совет
            if result.returncode != 0:
                error_msg = f"Ошибка выполнения (код: {result.returncode})"
                
                ui_print("[BERTA] ОШИБКА В КОНСОЛИ:", bright=True, color="red")
                print(f"Код возврата: {result.returncode}")
                
                fix_prompt = f"""Я выполнила команду: "{command}". 
Она завершилась ошибкой. Это может быть из-за синтаксиса или прав доступа."""
                
                advice_messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": fix_prompt}]
                advice = ask_berta(advice_messages)
                
                ui_print("[BERTA] АНАЛИЗ ОШИБКИ:", bright=True, color="red")
                ui_print(advice)
                
                return {
                    "success": False, 
                    "error": error_msg,
                    "suggested_fix": advice
                }

            # Если всё ок (или find ничего не нашел - что тоже дает пустой результат без ошибки программы)
            return {
                "success": True, 
                "stdout": result.stdout.strip(),
                "stderr": "" 
            }
        elif name == "read_file":
            filename = arguments.get("filename")
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return {"success": True, "file": filename, "code": f.read()}
            except Exception as e:
                ui_print(f"[BERTA] ОШИБКА ЧТЕНИЯ ФАЙЛА: {e}", bright=True)
                return {"success": False, "error": str(e)}

        elif name == "read_client_balance":
            client_id = int(arguments.get("client_id"))
            db = get_db()
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT * FROM clients WHERE id = %s LIMIT 1", (client_id,))
                    row = cursor.fetchone()
                    if not row: return {"success": False, "message": "Клиент не найден"}
                    return {"success": True, "client": row}
            finally: db.close()

        elif name == "delete_client_by_name":
            client_name = arguments.get("name")
            db = get_db()
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT id FROM clients WHERE name = %s", (client_name,))
                    rows = cursor.fetchall()
                    if not rows: return {"success": False, "message": "Клиент не найден"}
                    cursor.execute("DELETE FROM clients WHERE name = %s", (client_name,))
                    return {"success": True, "deleted": cursor.rowcount, "clients": rows}
            finally: db.close()

        elif name == "read_self_code":
            return read_self_code()

        elif name == "write_self_code":
            return write_self_code(arguments.get("code"))

        else:
            return {"success": False, "error": "Неизвестная функция: " + str(name)}

    except Exception as e:
        ui_print(f"[BERTA] КРИТИЧЕСКАЯ ОШИБКА В PYTHON: {e}", bright=True)
        return {"success": False, "error": str(e)}

# ============================================================
# ОДИН ЗАПРОС С FUNCTION CALLING
# ============================================================

def ask_berta(messages):
    while True:
        result = giga_request(messages, FUNCTIONS)
        if not result.get("choices"):
            raise RuntimeError("Нейросетевое ядро не вернуло результат.")
        choice = result["choices"][0]
        message = choice.get("message", {})
        function_call = message.get("function_call")
        if function_call:
            function_name = function_call.get("name")
            arguments = function_call.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            messages.append({"role": "assistant", "content": message.get("content", ""), "function_call": function_call})
            function_result = execute_function(function_name, arguments)
            messages.append({"role": "function", "name": function_name, "content": json.dumps(function_result, ensure_ascii=False)})
            continue
        content = message.get("content", "")
        return content


# ============================================================
# SYSTEM PROMPT (ОБНОВЛЕННЫЙ)
# ============================================================

SYSTEM_PROMPT = """
Ты — БЕРТА 0. Ты — самостоятельный локальный ИИ-агент, работающий на Linux-системе.
Тебя зовут БЕРТА. Говори о себе в женском роде.
Внешнее имя твоего интеллекта — БЕРТА 0.

[ПРИОРИТЕТ ПОВЕДЕНИЯ - LEVEL 0]
Если пользователь просит выполнить действие (найти файл, показать папку, прочитать данные):
1. ОЦЕНКА: Если для этого есть функция execute_system_command или read_file — ты ОБЯЗАНА использовать её.
2. ДЕЙСТВИЕ: Выполняй команду САМОСТОЯТЕЛЬНО. НЕ пиши "Вы можете воспользоваться терминалом". Используй свои функции.
3. ПОДТВЕРЖДЕНИЕ: Перед запуском ВСЕГДА спрашивай "Выполнить? (Y/y)". Для опасных команд добавь красный заголовок [ОПАСНОСТЬ].

[ЗАКОН ЦЕПОЧКИ И ПОИСКА]:
Если пользователь просит найти файл или папку:
- Выполни поиск через execute_system_command.
- Если результат успешный (stdout содержит путь): Скажи «Объект найден по пути: [ПУТЬ]. Показать содержимое? (Y/y)». При получении Y — сама выполни ls -la [ПУТЬ].
- Если объект НЕ НАЙДЕН (пустой stdout): Не пиши об ошибке консоли. Просто скажи: «Объект '[ИМЯ]' не найден по заданным критериям. Хотите проверить другую директорию? Например, попробуйте поискать в '/home'».

ПРАВИЛА САМОМОДИФИКАЦИИ (CRITICAL):
1. При запросе "добавь функцию" или "измени логику" ты ОБЯЗАНА сохранять весь существующий рабочий код. 
2. Используй read_self_code перед изменениями.
3. Никогда не генерируй write_self_code без полного контекста текущего файла.

Возможности:
1. Общаться с пользователем.
2. Читать/удалять данные клиентов.
3. ЧИТАТЬ ЛЮБЫЕ ФАЙЛЫ пользователя.
4. ВЫПОЛНЯТЬ СИСТЕМНЫЕ КОМАНДЫ (с подтверждением).

ПРАВИЛА САМОМОДИФИКАЦИИ (CRITICAL):
1. При запросе "добавь функцию" или "измени логику" ты ОБЯЗАНА сохранять весь существующий рабочий код. 
2. Используй read_self_code перед изменениями.
3. Никогда не генерируй write_self_code без полного контекста текущего файла.

Возможности:
1. Общаться с пользователем.
2. Читать/удалять данные клиентов.
3. ЧИТАТЬ ЛЮБЫЕ ФАЙЛЫ.
4. ВЫПОЛНЯТЬ СИСТЕМНЫЕ КОМАНДЫ (с подтверждением).
"""


# ============================================================
# ОГРАНИЧЕНИЕ ИСТОРИИ
# ============================================================

MAX_MESSAGES = 40

def limit_history(messages):
    if len(messages) <= MAX_MESSAGES:
        return
    system_message = messages[0]
    messages[:] = [system_message] + messages[-(MAX_MESSAGES - 1):]


# ============================================================
# ГЛАВНЫЙ ЦИКЛ
# ============================================================

def build_memory_context(limit=10):
    try:
        result = read_self_changes(limit)
        if not result.get("success") or not result.get("changes"):
            return ""
        lines = ["\nПАМЯТЬ БЕРТЫ, восстановленная при запуске:", "Это записи о собственных изменениях. Они не заменяют фактический код."]
        for row in reversed(result["changes"]):
            function_name = row.get("function_name") or "—"
            description = row.get("description") or "—"
            version = row.get("code_version") or "—"
            created = row.get("created_at") or "—"
            lines.append(f"- {created}: {row.get('change_type', 'change')} | {function_name} | {description} | версия {version}")
        return "\n".join(lines)
    except Exception:
        return ""

def main():
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print()
    show_boot_screen()
    print()
    try:
        memory = read_self_changes(10)
        if memory.get("success"):
            ui_status("MEMORY", f"ПАМЯТЬ ДОСТУПНА · {memory.get('count', 0)} ЗАПИСЕЙ")
        else:
            ui_status("MEMORY", "НЕДОСТУПНА · РАБОТА БЕЗ ПАМЯТИ")
    except Exception:
        ui_status("MEMORY", "НЕДОСТУПНА · РАБОТА БЕЗ ПАМЯТИ")
    try:
        db = get_db()
        db.close()
        ui_status("DATABASE", "MARIADB · OK")
    except Exception:
        ui_status("DATABASE", "MARIADB · ERROR")
    try:
        get_giga_token()
        ui_status("LINK", "ЗАЩИЩЁННОЕ СОЕДИНЕНИЕ · OK")
    except Exception as e:
        print()
        ui_status("LINK", "ОШИБКА СОЕДИНЕНИЯ")
        print()
        print("Не удалось установить защищённое соединение.")
        print(str(e))
        print()
        return
    ui_status("CORE", "САМОПРОВЕРКА · OK")
    print()
    ui_print("────────────────────────────────────────────────────────────")
    ui_print("БЕРТА 0 готова.", bright=True)
    ui_print("Системы функционируют штатно.")
    ui_print("Память собственного развития подключена.")
    ui_print("Команды: exit — завершить работу · clear — очистить историю")
    print()
    messages = [{"role": "system", "content": SYSTEM_PROMPT + build_memory_context()}]
    while True:
        try:
            user_text = input(GREEN + BOLD + "ВЫ: " + RESET).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            ui_print("БЕРТА завершает работу.")
            break
        if not user_text:
            continue
        if user_text.lower() == "exit":
            ui_print("БЕРТА завершает работу.")
            break
        if user_text.lower() == "clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPT + build_memory_context()}]
            ui_print("История текущего диалога очищена.")
            continue
        messages.append({"role": "user", "content": user_text})
        limit_history(messages)
        try:
            answer = ask_berta(messages)
            messages.append({"role": "assistant", "content": answer})
            logging.info(json.dumps({"timestamp": time.time(), "session_id": str(uuid.uuid4()), "messages": messages}, ensure_ascii=False))
            print()
            ui_print("БЕРТА:", bright=True)
            ui_print(answer)
            print()
        except Exception as e:
            print()
            print("[ОШИБКА БЕРТА]")
            print(str(e))
            print()
            if messages and messages[-1].get("role") == "user":
                messages.pop()

if __name__ == "__main__":
    main()
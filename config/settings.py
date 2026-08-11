import os
from dotenv import load_dotenv

load_dotenv()

GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_API = os.getenv("GIGACHAT_API", "https://api.giga.chat/v1")
GIGACHAT_OAUTH = os.getenv(
    "GIGACHAT_OAUTH",
    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
)
MODEL = os.getenv("MODEL", "GigaChat-2")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "berta_db")
DB_USER = os.getenv("DB_USER", "berta_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

WEB_HOST = os.getenv("BERTA_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("BERTA_WEB_PORT", "8742"))

HTTP_TIMEOUT = int(os.getenv("BERTA_HTTP_TIMEOUT", "120"))
MAX_RECENT_MESSAGES = int(os.getenv("BERTA_MAX_RECENT_MESSAGES", "16"))
SUMMARY_TRIGGER = int(os.getenv("BERTA_SUMMARY_TRIGGER", "24"))

VERSION = "0.3"

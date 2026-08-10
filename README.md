# BERTA 0.2

Локальный AI-оркестратор и Action Agent на базе GigaChat.

Управляет ОС, серверами и внешними системами через tool-use.  
Консоль + Web UI. Локальный женский голос (Piper / Irina).

## Запуск

```bash
# рекомендуется venv (Debian 13+)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# голос (один раз)
bash scripts/install_piper_voice.sh

python berta_agent.py
```

Web UI: **http://0.0.0.0:8742** (или IP хоста при пробросе порта)

## Возможности 0.2

- Консоль и Web UI работают параллельно
- Неблокирующие системные команды (Chrome/GUI → detached)
- EventBus + TaskManager
- Web UI: чат, мозг, система, задачи, ошибки
- **TTS**: Piper + Irina (medium), озвучка только в браузере
- Кнопка «ГОЛОС» во Web UI

## Структура

```
berta_agent.py              # главный файл
core/
  event_bus.py
  task_manager.py
  voice.py                  # Piper TTS
interface/web/              # HTTP + SSE + UI
scripts/install_piper_voice.sh
```

## Зависимости

- requests, python-dotenv, pymysql
- piper-tts (для голоса)

Веб-сервер — stdlib (`http.server`).

## Команды

- `exit` / `quit` / `выход` — выход
- `clear` — очистить историю

---

Версия: **0.2**  
Разработчик: Никита Маркин

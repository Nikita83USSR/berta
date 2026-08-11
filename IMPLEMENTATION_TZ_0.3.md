# BERTA 0.3 — реализация ТЗ «Internet Tools / System / Monitoring»

## Изменённые и новые файлы

### Новые модули
- `tools/web.py` — web_search, web_open, web_fetch, web_download
- `tools/http.py` — http_request, api_request
- `tools/filesystem.py` — file_list/read/write/append/exists/info/search (sandbox)
- `tools/git_tools.py` — git_status/log/branch/diff/show + confirm git_add/commit/pull/push
- `tools/network.py` — curl_request, dns_lookup, ping_host, tcp_check
- `tools/system_safe.py` — system_command (allowlist), system_info
- `tools/audio.py` — tts_status, tts_speak, tts_stop, audio_play
- `tools/monitoring.py` — event_list, event_stats, ai_request_counter + record_* helpers

### Обновлённые
- `tools/functions.py` — JSON schema всех tools для Function Calling
- `tools/function_manager.py` — диспетчер extended tools + CONFIRM
- `core/personality.py` — SYSTEM_PROMPT под tools / интернет / безопасность
- `core/router.py` — хинты web/git/system/tts/ai_counter → CHAT+tools
- `core/brain.py` — счётчик AI-запросов (success/error/elapsed/tokens)
- `config/settings.py` — VERSION = 0.3
- `interface/web/server.py` — `/api/monitoring` (AI, events, TTS, system)

### Сохранены без удаления
- `tools/system.py` (legacy execute_system_command / read_file)
- все существующие tools (DB, desktop, processes, …)

---

## Список всех новых tools

| Tool | Группа |
|------|--------|
| web_search | Internet |
| web_open | Internet |
| web_fetch | Internet |
| web_download | Internet |
| http_request | HTTP |
| api_request | HTTP |
| system_command | System |
| system_info | System |
| file_list | Files |
| file_read | Files |
| file_write | Files |
| file_append | Files |
| file_exists | Files |
| file_info | Files |
| file_search | Files |
| git_status | Git |
| git_log | Git |
| git_branch | Git |
| git_diff | Git |
| git_show | Git |
| git_add | Git |
| git_commit | Git |
| git_pull | Git |
| git_push | Git |
| curl_request | Network |
| dns_lookup | Network |
| ping_host | Network |
| tcp_check | Network |
| tts_status | Audio |
| tts_speak | Audio |
| tts_stop | Audio |
| audio_play | Audio |
| event_list | Monitoring |
| event_stats | Monitoring |
| ai_request_counter | Monitoring |

---

## SAFE / CONFIRM / FORBIDDEN

### SAFE (по умолчанию)
- web_search, web_open, web_fetch, web_download
- http_request GET/HEAD, api_request (allowlist)
- system_info
- system_command по allowlist: pwd, ls, df, free, uptime, whoami, hostname, date, uname, git status/log/branch, find в sandbox, systemctl status …
- file_list, file_read, file_exists, file_info, file_search (sandbox, без секретов)
- git_status, git_log, git_branch, git_diff, git_show
- curl_request, dns_lookup, ping_host, tcp_check (без private/mass-scan)
- tts_status, tts_speak, tts_stop, audio_play (разрешённые каталоги)
- event_list, event_stats, ai_request_counter

### CONFIRM
- http_request POST/PUT/PATCH/DELETE
- file_write, file_append
- git_add, git_commit, git_pull, git_push
- system_command вне SAFE allowlist
- terminate_process, delete_client_by_name (как и раньше)

### FORBIDDEN by default
- rm -rf, mkfs, shutdown/reboot/poweroff
- sudo / su / useradd / userdel / passwd
- iptables / ufw
- чтение .env, SSH keys, secrets
- localhost / private network (SSRF-защита)
- mass port/network scan
- произвольный bash -c / eval

---

## Результаты тестов (локально, без GigaChat key)

```
system_info     → ok, berta_version=0.3
system_command  → pwd → /home/workdir/artifacts/berta
git_status      → ok (modified + untracked new tools)
git_log         → ok, 1+ commits
file_list       → ok
file_read README→ ok
dns_lookup example.com → ok
web_search "Python programming language" → 5 results (DDG API)
web_open https://example.com → status 200, readable text
http_request httpbin GET → status 200
ai_request_counter → total/success после record_ai_request_success
py_compile всех модулей → OK
```

Полный прогон с GigaChat (web UI + реальные function calls) требует `GIGACHAT_AUTH_KEY` в `.env`.

---

## Примеры ответов

### web_search
```json
{
  "ok": true,
  "data": {
    "query": "Python programming language",
    "count": 5,
    "results": [
      {"title": "Python (programming language)", "url": "https://en.wikipedia.org/...", "snippet": "...", "source": "Wikipedia"}
    ]
  }
}
```

### system_info
```json
{
  "ok": true,
  "data": {
    "os": "Linux",
    "kernel": "...",
    "cpu": "...",
    "ram": {"total_kb": ..., "available_kb": ...},
    "hostname": "...",
    "python": "3.12.x",
    "berta_version": "0.3"
  }
}
```

### git_status
```json
{
  "ok": true,
  "data": {
    "status": "## main...origin/main\n M ...\n?? tools/web.py\n...",
    "cwd": "/.../berta"
  }
}
```

### ai_request_counter
```json
{
  "ok": true,
  "data": {
    "total": 1,
    "success": 1,
    "error": 0,
    "average_response_time": 0.5,
    "input_tokens": 0,
    "output_tokens": 0
  }
}
```

---

## Запуск

```bash
cd /path/to/berta
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env: GIGACHAT_AUTH_KEY=...
python berta_agent.py
# Web UI: http://0.0.0.0:8742
# Monitoring API: GET /api/monitoring
```

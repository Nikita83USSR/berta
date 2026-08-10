# interface/web/server.py
"""
Лёгкий веб-сервер BERTA (stdlib only).
- Раздаёт статику
- API для чата и задач
- Server-Sent Events (SSE) для живых логов
"""

import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from queue import Queue, Empty

from core.event_bus import bus
from core.task_manager import task_manager

try:
    from core.voice import synthesize, model_status
except Exception:
    synthesize = None
    model_status = lambda: {"ready": False, "error": "voice module missing"}


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HOST = "0.0.0.0"
PORT = 8742

# Кэш последних TTS-аудио: id → wav bytes
_tts_cache: dict = {}
_tts_cache_lock = threading.Lock()
_tts_counter = 0


class SSEClient:
    """Один подписчик SSE."""
    def __init__(self):
        self.queue = Queue(maxsize=200)
        self.active = True

    def send(self, event: dict):
        if not self.active:
            return
        try:
            self.queue.put_nowait(event)
        except Exception:
            self.active = False


class BertaHandler(SimpleHTTPRequestHandler):
    # Список активных SSE-клиентов
    sse_clients: list[SSEClient] = []
    sse_lock = threading.Lock()

    # Очередь входящих сообщений от веб-UI → агент
    incoming_messages: Queue = Queue()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Тихий лог, чтобы не засорять консоль
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # --- SSE поток событий ---
        if path == "/api/events":
            self._handle_sse()
            return

        # --- История событий ---
        if path == "/api/history":
            qs = parse_qs(parsed.query)
            since = int(qs.get("since", ["0"])[0])
            history = bus.get_history(since_id=since, limit=300)
            self._send_json({"events": history})
            return

        # --- Список задач ---
        if path == "/api/tasks":
            only_active = parse_qs(parsed.query).get("active", ["0"])[0] == "1"
            tasks = task_manager.list_tasks(only_active=only_active)
            self._send_json({"tasks": tasks})
            return

        # --- Статус TTS ---
        if path == "/api/tts/status":
            self._send_json(model_status())
            return

        # --- Отдать готовый WAV ---
        if path.startswith("/api/tts/") and path.endswith(".wav"):
            audio_id = path[len("/api/tts/"):-len(".wav")]
            with _tts_cache_lock:
                data = _tts_cache.get(audio_id)
            if not data:
                self._send_json({"error": "not found"}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        # --- Статика ---
        if path == "/" or path == "":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        # --- Сообщение от пользователя из веб-UI ---
        if path == "/api/chat":
            text = (data.get("message") or "").strip()
            if not text:
                self._send_json({"error": "Empty message"}, 400)
                return

            BertaHandler.incoming_messages.put({
                "text": text,
                "source": "web",
                "time": time.time()
            })

            bus.emit("chat", {
                "role": "user",
                "content": text,
                "source": "web"
            }, source="web")

            self._send_json({"ok": True})
            return

        # --- TTS: синтез текста → URL на WAV ---
        if path == "/api/speak":
            text = (data.get("text") or "").strip()
            if not text:
                self._send_json({"error": "Empty text"}, 400)
                return

            if synthesize is None:
                self._send_json({"error": "TTS module not available"}, 503)
                return

            wav = synthesize(text)
            if not wav:
                self._send_json({"error": "Synthesis failed", "status": model_status()}, 500)
                return

            global _tts_counter
            with _tts_cache_lock:
                _tts_counter += 1
                audio_id = str(_tts_counter)
                _tts_cache[audio_id] = wav
                # не раздуваем кэш
                if len(_tts_cache) > 30:
                    oldest = sorted(_tts_cache.keys(), key=lambda x: int(x) if x.isdigit() else 0)
                    for k in oldest[:10]:
                        _tts_cache.pop(k, None)

            self._send_json({
                "ok": True,
                "id": audio_id,
                "url": f"/api/tts/{audio_id}.wav",
                "bytes": len(wav)
            })
            return

        self._send_json({"error": "Not found"}, 404)

    def _handle_sse(self):
        """Server-Sent Events endpoint."""
        client = SSEClient()

        with BertaHandler.sse_lock:
            BertaHandler.sse_clients.append(client)

        def on_event(event):
            client.send(event)

        bus.subscribe(on_event)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            # Сразу отправляем keepalive
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()

            while client.active:
                try:
                    event = client.queue.get(timeout=15)
                    payload = json.dumps(event, ensure_ascii=False)
                    msg = f"data: {payload}\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Empty:
                    # keepalive ping
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            client.active = False
            bus.unsubscribe(on_event)
            with BertaHandler.sse_lock:
                if client in BertaHandler.sse_clients:
                    BertaHandler.sse_clients.remove(client)


def start_web_server(host: str = HOST, port: int = PORT):
    """Запускает веб-сервер в отдельном потоке."""
    server = ThreadingHTTPServer((host, port), BertaHandler)

    def run():
        print(f"\n[WEB] BERTA Web UI → http://{host}:{port}\n")
        try:
            server.serve_forever()
        except Exception:
            pass

    thread = threading.Thread(target=run, daemon=True, name="berta-web")
    thread.start()
    return server, thread


def get_incoming_message(timeout: float = 0.1):
    """Забирает сообщение из веб-UI (вызывается из main loop)."""
    try:
        return BertaHandler.incoming_messages.get(timeout=timeout)
    except Empty:
        return None

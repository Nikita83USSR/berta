"""
BERTA tools: TTS / audio (Piper).
tts_status, tts_speak, tts_stop, audio_play.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from core.event_bus import bus

try:
    from core.voice import (
        check_piper,
        model_status,
        synthesize,
        voices_ready,
        MODEL_ONNX,
        MODEL_JSON,
        DEFAULT_MODEL_NAME,
        VOICES_DIR,
    )
except Exception:  # pragma: no cover
    check_piper = lambda: False  # noqa: E731
    model_status = lambda: {"ready": False, "error": "voice module missing"}  # noqa: E731
    synthesize = None
    voices_ready = lambda: False  # noqa: E731
    MODEL_ONNX = Path.home() / ".berta" / "voices" / "ru_RU-irina-medium.onnx"
    MODEL_JSON = Path.home() / ".berta" / "voices" / "ru_RU-irina-medium.onnx.json"
    DEFAULT_MODEL_NAME = "ru_RU-irina-medium"
    VOICES_DIR = Path.home() / ".berta" / "voices"

ALLOWED_AUDIO_ROOTS = [
    (Path.home() / ".berta").resolve(),
    Path(__file__).resolve().parents[1].resolve(),
]


def _ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None, "success": True}


def _err(type_: str, message: str) -> dict:
    return {
        "ok": False,
        "data": None,
        "error": {"type": type_, "message": message},
        "success": False,
        "error_message": message,
    }


def tts_status() -> dict:
    status = model_status() if callable(model_status) else {"ready": False}
    piper_ok = check_piper() if callable(check_piper) else False
    ready = bool(status.get("ready")) or (piper_ok and voices_ready())
    data = {
        "piper": piper_ok,
        "model": DEFAULT_MODEL_NAME,
        "model_path": str(MODEL_ONNX),
        "model_json": str(MODEL_JSON),
        "voices_dir": str(VOICES_DIR),
        "voices_ready": voices_ready() if callable(voices_ready) else False,
        "ready": ready,
        "details": status,
    }
    bus.emit("TTS_REQUEST", {"tool": "tts_status", "ready": ready}, source="audio")
    return _ok(data)


def tts_speak(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return _err("ValidationError", "text обязателен")
    if len(text) > 2000:
        text = text[:2000]
    if synthesize is None:
        return _err("NotAvailable", "Piper/voice module недоступен")
    t0 = time.time()
    bus.emit("TTS_REQUEST", {"tool": "tts_speak", "text_len": len(text)}, source="audio")
    try:
        # core.voice.synthesize returns path or bytes depending on implementation
        result = synthesize(text)
        elapsed = round(time.time() - t0, 3)
        if isinstance(result, dict):
            if result.get("error"):
                return _err("TTSError", str(result["error"])[:400])
            return _ok({**result, "elapsed": elapsed})
        return _ok({"result": str(result)[:500], "elapsed": elapsed, "text_len": len(text)})
    except Exception as e:
        return _err("TTSError", str(e)[:400])


def tts_stop() -> dict:
    """Остановка воспроизведения, если поддерживается."""
    bus.emit("TTS_REQUEST", {"tool": "tts_stop"}, source="audio")
    # Piper one-shot; no persistent player in base architecture
    return _ok({"message": "Остановка не требуется (Piper one-shot) или не поддерживается"})


def audio_play(path: str) -> dict:
    """Воспроизведение только файлов из разрешённого каталога."""
    p = Path(path).expanduser().resolve()
    allowed = False
    for root in ALLOWED_AUDIO_ROOTS:
        try:
            p.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        return _err("SecurityError", f"Файл вне разрешённых каталогов: {p}")
    if not p.is_file():
        return _err("NotFound", f"Файл не найден: {p}")
    if p.suffix.lower() not in {".wav", ".mp3", ".ogg", ".flac"}:
        return _err("ValidationError", "Поддерживаются wav/mp3/ogg/flac")

    bus.emit("TTS_REQUEST", {"tool": "audio_play", "path": str(p)}, source="audio")
    # try aplay / paplay
    import subprocess

    for player in ("aplay", "paplay", "ffplay"):
        try:
            if player == "ffplay":
                proc = subprocess.Popen(
                    [player, "-nodisp", "-autoexit", str(p)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc = subprocess.Popen(
                    [player, str(p)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return _ok({"path": str(p), "player": player, "pid": proc.pid})
        except FileNotFoundError:
            continue
        except Exception as e:
            return _err("PlayError", str(e)[:300])
    return _err("NotAvailable", "Нет aplay/paplay/ffplay")

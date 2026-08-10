# core/voice.py
"""
Локальный TTS для BERTA через Piper (голос Irina, русский).
Синтез на CPU, аудио отдаётся в Web UI (не в консоль ВМ).
"""

import os
import io
import wave
import struct
import threading
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from core.event_bus import bus


# Каталог моделей (рядом с проектом или в home)
VOICES_DIR = Path(os.environ.get(
    "BERTA_VOICES_DIR",
    Path.home() / ".berta" / "voices"
))

# Модель по умолчанию: Piper ru_RU-irina-medium
DEFAULT_MODEL_NAME = "ru_RU-irina-medium"
MODEL_ONNX = VOICES_DIR / f"{DEFAULT_MODEL_NAME}.onnx"
MODEL_JSON = VOICES_DIR / f"{DEFAULT_MODEL_NAME}.onnx.json"

# Куда класть временные wav (можно в /tmp)
TMP_DIR = Path(tempfile.gettempdir()) / "berta_tts"
TMP_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_piper_available: Optional[bool] = None


def voices_ready() -> bool:
    """Проверка, что модель на месте."""
    return MODEL_ONNX.is_file() and MODEL_JSON.is_file()


def check_piper() -> bool:
    """Проверка, что piper установлен (CLI или python-пакет)."""
    global _piper_available
    if _piper_available is not None:
        return _piper_available

    # 1) CLI
    try:
        r = subprocess.run(
            ["piper", "--help"],
            capture_output=True,
            timeout=5
        )
        if r.returncode == 0 or b"usage" in (r.stdout + r.stderr).lower():
            _piper_available = True
            return True
    except Exception:
        pass

    # 2) Python-пакет
    try:
        import piper  # noqa: F401
        _piper_available = True
        return True
    except ImportError:
        pass

    _piper_available = False
    return False


def synthesize(text: str, max_chars: int = 1200) -> Optional[bytes]:
    """
    Синтезирует речь, возвращает WAV (bytes) или None при ошибке.
    Не воспроизводит звук локально — только данные для Web UI.
    """
    text = (text or "").strip()
    if not text:
        return None

    # Обрезаем слишком длинные ответы, чтобы не грузить ВМ
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"

    if not voices_ready():
        bus.emit("error", {
            "message": f"Модель Piper не найдена: {MODEL_ONNX}"
        }, source="voice")
        return None

    if not check_piper():
        bus.emit("error", {
            "message": "Piper не установлен. pip install piper-tts"
        }, source="voice")
        return None

    with _lock:
        try:
            wav_bytes = _synthesize_cli(text)
            if wav_bytes:
                bus.emit("system", {
                    "message": f"TTS: {len(text)} символов → {len(wav_bytes)} bytes"
                }, source="voice")
            return wav_bytes
        except Exception as e:
            bus.emit("error", {"message": f"TTS error: {e}"}, source="voice")
            return None


def _synthesize_cli(text: str) -> Optional[bytes]:
    """Синтез через CLI piper (предпочтительно)."""
    out_path = TMP_DIR / f"tts_{os.getpid()}_{threading.get_ident()}.wav"
    try:
        proc = subprocess.run(
            [
                "piper",
                "--model", str(MODEL_ONNX),
                "--output_file", str(out_path),
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60
        )
        if proc.returncode != 0:
            # fallback: python API
            return _synthesize_python(text)

        if not out_path.is_file():
            return None

        data = out_path.read_bytes()
        return data if data else None
    finally:
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass


def _synthesize_python(text: str) -> Optional[bytes]:
    """Fallback через пакет piper-tts."""
    try:
        from piper import PiperVoice
    except ImportError:
        return None

    voice = PiperVoice.load(str(MODEL_ONNX))
    # Собираем PCM и упаковываем в WAV
    frames = []
    sample_rate = 22050
    sample_width = 2  # 16-bit

    for chunk in voice.synthesize(text):
        # chunk.audio_int16_array или float
        if hasattr(chunk, "audio_int16_bytes"):
            frames.append(chunk.audio_int16_bytes)
        elif hasattr(chunk, "audio_int16_array"):
            frames.append(chunk.audio_int16_array.tobytes())
        elif hasattr(chunk, "audio_float_array"):
            import array
            floats = chunk.audio_float_array
            ints = array.array("h", (max(-32767, min(32767, int(x * 32767))) for x in floats))
            frames.append(ints.tobytes())
        if hasattr(chunk, "sample_rate") and chunk.sample_rate:
            sample_rate = chunk.sample_rate

    if not frames:
        return None

    pcm = b"".join(frames)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def model_status() -> dict:
    return {
        "ready": voices_ready() and check_piper(),
        "piper": check_piper(),
        "model_path": str(MODEL_ONNX),
        "model_exists": MODEL_ONNX.is_file(),
        "config_exists": MODEL_JSON.is_file(),
        "voice": DEFAULT_MODEL_NAME,
    }

# core/voice.py
"""Локальный TTS через Piper и голос ru_RU-irina-medium."""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path
from typing import Optional

from core.event_bus import bus

VOICES_DIR = Path(os.environ.get("BERTA_VOICES_DIR", Path.home() / ".berta" / "voices"))
DEFAULT_MODEL_NAME = "ru_RU-irina-medium"
MODEL_ONNX = VOICES_DIR / f"{DEFAULT_MODEL_NAME}.onnx"
MODEL_JSON = VOICES_DIR / f"{DEFAULT_MODEL_NAME}.onnx.json"
TMP_DIR = Path(tempfile.gettempdir()) / "berta_tts"
TMP_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_piper_available: Optional[bool] = None
_piper_bin: Optional[str] = None


def voices_ready():
    return MODEL_ONNX.is_file() and MODEL_JSON.is_file()


def _candidate_piper_bins():
    """Ищет Piper прежде всего в том же venv, которым запущена BERTA."""
    candidates = []
    exe_dir = Path(sys.executable).resolve().parent
    candidates.append(exe_dir / "piper")
    candidates.append(exe_dir / "piper.exe")

    project_root = Path(__file__).resolve().parents[1]
    candidates.append(project_root / ".venv" / "bin" / "piper")
    candidates.append(project_root / ".venv" / "Scripts" / "piper.exe")

    found = shutil.which("piper")
    if found:
        candidates.append(Path(found))

    result = []
    seen = set()
    for path in candidates:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key not in seen and path.is_file():
            seen.add(key)
            result.append(path)
    return result


def _find_piper():
    global _piper_bin
    if _piper_bin:
        return _piper_bin

    for path in _candidate_piper_bins():
        try:
            result = subprocess.run(
                [str(path), "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=8,
            )
            output = (result.stdout + result.stderr).lower()
            if result.returncode == 0 or b"piper" in output or b"usage" in output:
                _piper_bin = str(path)
                return _piper_bin
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def check_piper():
    global _piper_available
    if _piper_available is not None:
        return _piper_available

    # В первую очередь — реальный executable piper из .venv.
    if _find_piper():
        _piper_available = True
        return True

    # Запасной путь для Python API.
    try:
        import piper  # noqa: F401
        _piper_available = True
        return True
    except Exception:
        _piper_available = False
        return False


def synthesize(text: str, max_chars: int = 1200):
    text = (text or "").strip()
    if not text:
        return None
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"

    if not voices_ready():
        bus.emit("error", {"message": f"Голосовая модель не найдена: {MODEL_ONNX}"}, source="voice")
        return None
    if not check_piper():
        bus.emit("error", {"message": "Локальный голосовой движок недоступен в окружении BERTA."}, source="voice")
        return None

    with _lock:
        try:
            data = _synthesize_cli(text)
            if data:
                bus.emit("system", {"message": "Голос готов к воспроизведению."}, source="voice")
            return data
        except Exception as exc:
            bus.emit("error", {"message": f"Ошибка озвучки: {exc}"}, source="voice")
            return None


def _synthesize_cli(text):
    piper_bin = _find_piper()
    if not piper_bin:
        return _synthesize_python(text)

    out_path = TMP_DIR / f"tts_{os.getpid()}_{threading.get_ident()}.wav"
    try:
        proc = subprocess.run(
            [piper_bin, "--model", str(MODEL_ONNX), "--output_file", str(out_path)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or f"Piper завершился с кодом {proc.returncode}")
        if not out_path.is_file():
            raise RuntimeError("Piper не создал WAV-файл")
        data = out_path.read_bytes()
        return data or None
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def _synthesize_python(text):
    try:
        from piper import PiperVoice
    except Exception:
        return None

    out_path = TMP_DIR / f"tts_py_{os.getpid()}_{threading.get_ident()}.wav"
    try:
        voice = PiperVoice.load(str(MODEL_ONNX), config_path=str(MODEL_JSON))
        with wave.open(str(out_path), "wb") as wav_file:
            voice.synthesize(text, wav_file)
        data = out_path.read_bytes()
        return data or None
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def model_status():
    piper = check_piper()
    return {
        "ready": voices_ready() and piper,
        "engine": "local",
        "model_path": str(MODEL_ONNX),
        "model_exists": MODEL_ONNX.is_file(),
        "config_exists": MODEL_JSON.is_file(),
        "voice": DEFAULT_MODEL_NAME,
        "executable": _piper_bin or "",
    }

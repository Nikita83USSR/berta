#!/bin/bash
# Установка Piper + голос Irina (medium) для BERTA
set -e

VOICES_DIR="${BERTA_VOICES_DIR:-$HOME/.berta/voices}"
mkdir -p "$VOICES_DIR"
cd "$VOICES_DIR"

echo "==> Установка piper-tts (pip)..."
pip install --user piper-tts 2>/dev/null || pip install piper-tts

echo "==> Скачивание модели ru_RU-irina-medium..."
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium"

if [ ! -f ru_RU-irina-medium.onnx ]; then
  wget -O ru_RU-irina-medium.onnx "${BASE}/ru_RU-irina-medium.onnx?download=true"
fi
if [ ! -f ru_RU-irina-medium.onnx.json ]; then
  wget -O ru_RU-irina-medium.onnx.json "${BASE}/ru_RU-irina-medium.onnx.json?download=true"
fi

echo "==> Готово."
echo "Модель: $VOICES_DIR/ru_RU-irina-medium.onnx"
echo "Запусти BERTA и в Web UI нажми кнопку ГОЛОС."
ls -lh "$VOICES_DIR"

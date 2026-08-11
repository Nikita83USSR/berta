# BERTA TTS (Piper + Irina) — локальная установка

## Куда положить файлы

В корне проекта BERTA:

```
core/voice.py                          ← новый
interface/web/server.py                ← заменить
interface/web/static/index.html        ← заменить
interface/web/static/style.css         ← заменить
interface/web/static/app.js            ← заменить
scripts/install_piper_voice.sh         ← новый
requirements.txt                       ← обновить (добавлен piper-tts)
```

## Установка Piper + голос

```bash
cd /path/to/berta
bash scripts/install_piper_voice.sh
```

Или вручную:

```bash
pip install piper-tts
mkdir -p ~/.berta/voices && cd ~/.berta/voices
wget -O ru_RU-irina-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx?download=true"
wget -O ru_RU-irina-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json?download=true"
```

## Запуск

```bash
python berta_agent.py
```

Открой Web UI → кнопка **ГОЛОС** в шапке (должна стать зелёной).

Голос играет только в браузере, не на колонках ВМ.

## Проверка API

```bash
curl -s http://127.0.0.1:8742/api/tts/status
curl -s -X POST http://127.0.0.1:8742/api/speak \
  -H 'Content-Type: application/json' \
  -d '{"text":"Привет, я Берта."}'
```

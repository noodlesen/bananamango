#!/usr/bin/env python3
"""
Телеграм-бот в одном файле.

Функции:
- принимает текст и голос (voice)
- расшифровывает голос через Whisper (ProxyAPI)
- отправляет текст в GPT (ProxyAPI) с инструкцией вернуть КБЖУ в строгом JSON
- сохраняет записи в JSON-файлы в папке data/meals/<user_id>/<YYYY-MM-DD>.json
- возвращает пользователю данные по приёму пищи и суммарную статистику за день

Переменные окружения:
- TELEGRAM_BOT_TOKEN  — токен бота
- PROXYAPI_KEY        — ключ ProxyAPI (Bearer)
- PROXYAPI_BASE       — базовый URL ProxyAPI (по умолчанию https://openai.api.proxyapi.ru/v1)
- DATA_DIR            — опционально, директория для сохранения json (по умолчанию ./data)

Зависимости: python-telegram-bot >=20, requests
"""

import os
import sys
import json
import time
import uuid
import logging
import tempfile
import datetime
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv


import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- конфигурация ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_BASE = os.getenv("PROXYAPI_BASE", "https://openai.api.proxyapi.ru/v1")
DATA_DIR = os.getenv("DATA_DIR", "./data")

if not TELEGRAM_BOT_TOKEN or not PROXYAPI_KEY:
    print("Environment variables TELEGRAM_BOT_TOKEN and PROXYAPI_KEY must be set", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {PROXYAPI_KEY}"}
TIMEOUT = 30  # seconds for HTTP requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("foodbot")


# ---------- Storage helpers ----------

def ensure_user_dir(user_id: int) -> str:
    path = os.path.join(DATA_DIR, "meals", str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def day_file_path(user_id: int, date: datetime.date) -> str:
    user_dir = ensure_user_dir(user_id)
    return os.path.join(user_dir, f"{date.isoformat()}.json")


def load_day_entries(user_id: int, date: datetime.date) -> List[Dict[str, Any]]:
    path = day_file_path(user_id, date)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load day file %s: %s", path, e)
        return []


def save_day_entries(user_id: int, date: datetime.date, entries: List[Dict[str, Any]]) -> None:
    path = day_file_path(user_id, date)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        logger.exception("Failed to save day file %s: %s", path, e)
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


# ---------- ProxyAPI (Whisper & Chat) helpers ----------

def transcribe_voice_via_proxyapi(file_path: str, language: Optional[str] = "ru") -> str:
    """
    Отправляет аудиофайл на ProxyAPI /audio/transcriptions и возвращает распознанный текст.
    """
    url = f"{PROXYAPI_BASE.rstrip('/')}/audio/transcriptions"
    files = {"file": open(file_path, "rb")}
    data = {"model": "whisper-1"}
    if language:
        data["language"] = language
    try:
        resp = requests.post(url, headers=HEADERS, files=files, data=data, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        # Ожидаем поле "text"
        text = payload.get("text")
        if isinstance(text, str):
            return text.strip()
        # В некоторых реализациях ответ может иметь другой формат
        # Попробуем найти текст в json
        # fallback: try to join string values
        for v in payload.values():
            if isinstance(v, str) and len(v) > 10:
                return v.strip()
        return ""
    finally:
        try:
            files["file"].close()
        except Exception:
            pass


def strip_code_fences(s: str) -> str:
    """
    Убирает тройные или одинарные блоки кода ```...``` или ```json ... ```
    """
    if not s:
        return s
    # remove ```...``` blocks but if content inside is pure JSON, keep it
    # We'll try to extract the first JSON-like substring
    s = s.strip()
    # If starts with ``` remove fencing
    if s.startswith("```") and s.endswith("```"):
        inner = s[3:-3].strip()
        return inner
    # remove single fence at start if present
    if s.startswith("```"):
        s = s[3:].strip()
    # also remove leading/trailing backticks
    return s


def extract_json_from_text(s: str) -> Optional[str]:
    """
    Пытаемся извлечь JSON-объект или массив из произвольного текста.
    Возвращает строку JSON или None.
    """
    if not s:
        return None
    s = s.strip()
    # убираем окружение code fences
    s = strip_code_fences(s)
    # Ищем первую '{' или '['
    start = None
    for i, ch in enumerate(s):
        if ch in ("{", "["):
            start = i
            break
    if start is None:
        return None
    # Попробуем найти соответствующую закрывающую скобку — простая стратегия: парсить progressively
    candidate = s[start:]
    # Попытка прямого json.loads
    for end in range(len(candidate), 0, -1):
        try:
            js = candidate[:end]
            obj = json.loads(js)
            return js
        except Exception:
            continue
    # если не смогли, возвращаем None
    return None


def call_gpt_for_kbju(text: str) -> Dict[str, Any]:
    """
    Отправляет prompt в chat/completions ProxyAPI и ожидает строго JSON-ответ вида:
    {"calories": <float>, "protein": <float>, "fat": <float>, "carbs": <float>}
    В prompt просим вернуть только JSON.
    """
    url = f"{PROXYAPI_BASE.rstrip('/')}/chat/completions"
    system_prompt = (
        "Ты — помощник, который точно оценивает пищевую ценность блюд. "
        "На вход — краткое описание приёма пищи (на любом языке). "
        "Требуется выдать строгий JSON с полями: calories, protein, fat, carbs. "
        "Прежде чем оценить, подумай как готовится такое блюдо, используется ли в нем масло или соусы при приготовлении"
        "Значения должны быть числами (можно с дробной частью). "
        "Никаких пояснений вне JSON. Если не уверен — оцени консервативно. "
        "Если в описании явно указано количество (граммы, столовые ложки и т.п.) — используй их."
    )
    user_prompt = (
        "Оцени для этого описания: "
        + text
        + "\n\n"
        "Ответь строго JSON-объектом, например: "
        '{"calories": 250, "protein": 12, "fat": 10, "carbs": 30}'
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 300,
    }
    try:
        resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/json"}, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # ожидаем data["choices"][0]["message"]["content"]
        choices = data.get("choices") or []
        if not choices:
            logger.warning("GPT returned no choices: %s", data)
            return {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        message = choices[0].get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            # try other fallbacks
            raw = json.dumps(data, ensure_ascii=False)
            content = raw
        # извлекаем JSON
        json_text = extract_json_from_text(content)
        if not json_text:
            # как fallback попробуем убрать всё, кроме фигурных скобок
            # найти первую { и последнюю }
            s = content
            a = s.find("{")
            b = s.rfind("}")
            if a != -1 and b != -1 and b > a:
                json_text = s[a:b+1]
        if not json_text:
            logger.warning("Failed to extract JSON from GPT content: %s", content)
            return {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        parsed = json.loads(json_text)
        # ensure numeric types
        def num(v):
            try:
                return float(v)
            except Exception:
                return 0.0
        return {
            "calories": num(parsed.get("calories", 0)),
            "protein": num(parsed.get("protein", 0)),
            "fat": num(parsed.get("fat", 0)),
            "carbs": num(parsed.get("carbs", 0)),
        }
    except Exception as e:
        logger.exception("call_gpt_for_kbju failed: %s", e)
        return {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}


# ---------- Bot handlers ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    await msg.reply_text("Отправляй текст или голос с описанием приёма пищи.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    await msg.reply_text("Поддерживаются текстовые и голосовые сообщения. Бот сохраняет данные локально.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    user = msg.from_user
    if user is None:
        return
    text = msg.text
    if not text:
        return
    # process
    await msg.reply_text("Получил текст. Анализирую...")
    kbju = call_gpt_for_kbju(text)
    # prepare entry
    now = datetime.datetime.utcnow().isoformat() + "Z"
    entry = {
        "id": str(uuid.uuid4()),
        "datetime": now,
        "text": text,
        "calories": kbju["calories"],
        "protein": kbju["protein"],
        "fat": kbju["fat"],
        "carbs": kbju["carbs"],
        "source": "text",
    }
    today = datetime.date.today()
    entries = load_day_entries(user.id, today)
    entries.append(entry)
    save_day_entries(user.id, today, entries)
    # compute totals
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        totals["calories"] += float(e.get("calories", 0) or 0)
        totals["protein"] += float(e.get("protein", 0) or 0)
        totals["fat"] += float(e.get("fat", 0) or 0)
        totals["carbs"] += float(e.get("carbs", 0) or 0)
    resp = (
        f"Запись сохранена.\n\nПриём: {entry['text']}\n"
        f"Калории: {entry['calories']} kcal\n"
        f"Белок: {entry['protein']} g, Жиры: {entry['fat']} g, Углеводы: {entry['carbs']} g\n\n"
        f"Итог за {today.isoformat()} — Калории: {totals['calories']:.1f} kcal, "
        f"Белок: {totals['protein']:.1f} g, Жиры: {totals['fat']:.1f} g, Углеводы: {totals['carbs']:.1f} g"
    )
    await msg.reply_text(resp)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    user = msg.from_user
    if user is None:
        return
    voice = msg.voice
    if voice is None:
        await msg.reply_text("Не удалось найти голосовое сообщение.")
        return
    # download
    file = await voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tf:
        await file.download_to_drive(tf.name)
        await msg.reply_text("Расшифровываю голосовое сообщение...")
        text = ""
        try:
            text = transcribe_voice_via_proxyapi(tf.name, language="ru")
        except Exception as e:
            logger.exception("transcription failed: %s", e)
            await msg.reply_text("Ошибка распознавания голоса.")
            return
    if not text:
        await msg.reply_text("Не удалось распознать текст из аудиосообщения.")
        return
    # forward to same pipeline as text
    await msg.reply_text(f"Распознанный текст: {text}\nАнализирую содержимое...")
    kbju = call_gpt_for_kbju(text)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    entry = {
        "id": str(uuid.uuid4()),
        "datetime": now,
        "text": text,
        "calories": kbju["calories"],
        "protein": kbju["protein"],
        "fat": kbju["fat"],
        "carbs": kbju["carbs"],
        "source": "voice",
    }
    today = datetime.date.today()
    entries = load_day_entries(user.id, today)
    entries.append(entry)
    save_day_entries(user.id, today, entries)
    # totals
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        totals["calories"] += float(e.get("calories", 0) or 0)
        totals["protein"] += float(e.get("protein", 0) or 0)
        totals["fat"] += float(e.get("fat", 0) or 0)
        totals["carbs"] += float(e.get("carbs", 0) or 0)
    resp = (
        f"Запись сохранена.\n\nПриём: {entry['text']}\n"
        f"Калории: {entry['calories']} kcal\n"
        f"Белок: {entry['protein']} g, Жиры: {entry['fat']} g, Углеводы: {entry['carbs']} g\n\n"
        f"Итог за {today.isoformat()} — Калории: {totals['calories']:.1f} kcal, "
        f"Белок: {totals['protein']:.1f} g, Жиры: {totals['fat']:.1f} g, Углеводы: {totals['carbs']:.1f} g"
    )
    await msg.reply_text(resp)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    user = msg.from_user
    if user is None:
        return
    today = datetime.date.today()
    entries = load_day_entries(user.id, today)
    if not entries:
        await msg.reply_text(f"Записей за {today.isoformat()} нет.")
        return
    lines = [f"Статистика за {today.isoformat()}:\n"]
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for e in entries:
        lines.append(f"- {e.get('text','')[:120]} ({e.get('calories',0)} kcal)")
        totals["calories"] += float(e.get("calories", 0) or 0)
        totals["protein"] += float(e.get("protein", 0) or 0)
        totals["fat"] += float(e.get("fat", 0) or 0)
        totals["carbs"] += float(e.get("carbs", 0) or 0)
    lines.append("")
    lines.append(
        f"Итого: {totals['calories']:.1f} kcal, белок {totals['protein']:.1f} g, "
        f"жиры {totals['fat']:.1f} g, углеводы {totals['carbs']:.1f} g"
    )
    await msg.reply_text("\n".join(lines))


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.run_polling()


if __name__ == "__main__":
    main()

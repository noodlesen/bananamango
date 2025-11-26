import os
import logging
import requests
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import openai

API_URL = os.getenv("DJANGO_API_URL")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openai.api_key = PROXYAPI_KEY
openai.api_base = "https://openai.api.proxyapi.ru/v1"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None:
        return
    await message.reply_text(
        "Привет! Я буду отслеживать твои приёмы пищи, вес и активность. "
        "Отправляй текст или голос с описанием еды."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None:
        return
    await message.reply_text(
        "/start - начать работу\n"
        "/today - показать суммарные данные за сегодня"
    )


def post_meal_to_api(user_id: int, day_id: int, text: str):
    payload = {"user": user_id, "day": day_id, "text": text}
    r = requests.post(f"{API_URL}meals/", json=payload)
    return r.json()


def get_today_from_api(user_id: int):
    r = requests.get(f"{API_URL}days/today/")
    return r.json()


def transcribe_voice(file_path: str) -> str:
    with open(file_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript["text"]


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str | None = None):
    message = update.message
    if message is None:
        return

    user = message.from_user
    if user is None:
        return

    user_id = user.id
    text_value = text or message.text
    if not text_value:
        return

    day_data = get_today_from_api(user_id)
    day_id = day_data.get("id")
    if day_id is None:
        await message.reply_text("Ошибка: не удалось получить день пользователя.")
        return

    meal_data = post_meal_to_api(user_id, day_id, text_value)

    response_text = (
        f"Добавлено: {text_value}\n"
        f"Калории: {meal_data.get('calories', 0)}, "
        f"Белки: {meal_data.get('protein', 0)}, "
        f"Жиры: {meal_data.get('fat', 0)}, "
        f"Углеводы: {meal_data.get('carbs', 0)}\n\n"
        f"Суммарно за день:\n"
        f"Калории: {day_data.get('total_calories', 0)}, "
        f"Белки: {day_data.get('total_protein', 0)}"
    )

    await message.reply_text(response_text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None:
        return

    user = message.from_user
    if user is None:
        return

    voice = message.voice
    if voice is None:
        return

    voice_file = await voice.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg") as tf:
        await voice_file.download_to_drive(tf.name)
        text_value = transcribe_voice(tf.name)

    await handle_text(update, context, text=text_value)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None:
        return

    user = message.from_user
    if user is None:
        return

    user_id = user.id
    day_data = get_today_from_api(user_id)
    meals = day_data.get("meals", [])

    lines = [
        f"День: {day_data.get('date', '-')}, "
        f"Вес: {day_data.get('weight', '-')}, "
        f"Шаги: {day_data.get('steps', '-')}\n"
    ]

    for meal in meals:
        lines.append(f"- {meal.get('text', '')} ({meal.get('calories', 0)} ккал)")

    await message.reply_text("\n".join(lines))


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()


if __name__ == "__main__":
    main()

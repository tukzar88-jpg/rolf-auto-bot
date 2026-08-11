import os
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER\n\n"
        "Бот запущен и готов к настройке.\n\n"
        "Команды:\n"
        "/start — запуск\n"
        "/status — статус бота\n"
        "/filters — мои фильтры"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 Бот работает.\n\n"
        "Следующий этап — подключение мониторинга автомобилей."
    )


async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Текущие фильтры:\n\n"
        "💰 Цена: 2–8 млн ₽\n"
        "📅 Год: от 2019\n"
        "🇨🇳 Китай: 2 000–30 000 км\n"
        "🇰🇷 Корея: до 70 000 км\n"
        "🇩🇪 Германия: максимальные комплектации\n"
        "📍 Регион: вся Россия"
    )


def main():
    if not TOKEN:
        raise RuntimeError("Не задана переменная BOT_TOKEN")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("filters", filters))

    print("ROLF AUTO FINDER запущен")
    app.run_polling()


if __name__ == "__main__":
    main()

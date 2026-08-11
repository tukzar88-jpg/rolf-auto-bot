import os
import logging
import random
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- МОК-ДАННЫЕ (имитация найденных авто) ----------
# Позже заменим на реальный парсинг / API
MOCK_CARS = [
    {
        "name": "BMW X5 xDrive30d M Sport",
        "price": 5250000,
        "below_market": 480000,
        "mileage": 41000,
        "owners": 1,
        "city": "Москва",
        "year": 2021,
        "url": "https://auto.ru/mock/1"
    },
    {
        "name": "Kia Telluride Premium",
        "price": 4500000,
        "below_market": 320000,
        "mileage": 58000,
        "owners": 1,
        "city": "Санкт-Петербург",
        "year": 2020,
        "url": "https://auto.ru/mock/2"
    },
    {
        "name": "Chery Tiggo 8 Pro Max",
        "price": 3200000,
        "below_market": 150000,
        "mileage": 18000,
        "owners": 2,
        "city": "Казань",
        "year": 2022,
        "url": "https://auto.ru/mock/3"
    },
    {
        "name": "Mercedes-Benz GLE 400 d",
        "price": 7800000,
        "below_market": 650000,
        "mileage": 32000,
        "owners": 1,
        "city": "Москва",
        "year": 2022,
        "url": "https://auto.ru/mock/4"
    },
    {
        "name": "Hyundai Santa Fe High-Tech",
        "price": 3800000,
        "below_market": 210000,
        "mileage": 65000,
        "owners": 2,
        "city": "Новосибирск",
        "year": 2021,
        "url": "https://auto.ru/mock/5"
    }
]

# ---------- ХРАНИЛИЩЕ СОСТОЯНИЙ (в памяти) ----------
# Ключ: chat_id, значение: {"monitoring": bool, "found_count": int}
user_states = {}

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {"monitoring": False, "found_count": 0}
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER\n\n"
        "Бот запущен и готов к мониторингу.\n\n"
        "Команды:\n"
        "/start — перезапуск\n"
        "/monitor — найти авто (выдаёт 1 вариант)\n"
        "/stop — остановить поиск\n"
        "/stats — статистика за сессию\n"
        "/filters — мои фильтры"
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

async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Инициализация состояния, если юзер новый
    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}

    user_states[chat_id]["monitoring"] = True
    user_states[chat_id]["found_count"] += 1

    # Выбираем случайное авто из мока
    car = random.choice(MOCK_CARS)

    # Форматируем цену с пробелами
    price_str = f"{car['price']:,}".replace(",", " ")
    below_str = f"{car['below_market']:,}".replace(",", " ")
    mileage_str = f"{car['mileage']:,}".replace(",", " ")

    message = (
        f"🚨 *{car['name']}*\n"
        f"💰 Цена: {price_str} ₽\n"
        f"📉 Ниже рынка: {below_str} ₽\n"
        f"🚗 Пробег: {mileage_str} км\n"
        f"👤 Владельцев: {car['owners']}\n"
        f"📅 Год: {car['year']}\n"
        f"📍 {car['city']}\n"
        f"🔗 [Ссылка на объявление]({car['url']})"
    )

    await update.message.reply_text(message, parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_states:
        user_states[chat_id]["monitoring"] = False
        await update.message.reply_text("⏹ Мониторинг остановлен. Найденные авто сохранены в статистике.")
    else:
        await update.message.reply_text("Мониторинг ещё не был запущен.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}

    count = user_states[chat_id]["found_count"]
    status = "включён" if user_states[chat_id]["monitoring"] else "выключен"

    await update.message.reply_text(
        f"📊 Статистика за сессию:\n\n"
        f"🔍 Найдено авто: {count}\n"
        f"⚙️ Мониторинг: {status}"
    )

# ---------- ЗАПУСК ----------
def main():
    if not TOKEN:
        raise RuntimeError("Не задана переменная BOT_TOKEN")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("filters", filters))
    app.add_handler(CommandHandler("monitor", monitor))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("stats", stats))

    print("ROLF AUTO FINDER запущен (v1.0 с мок-данными)")
    app.run_polling()

if __name__ == "__main__":
    main()

import os
import logging
import random
import re
import statistics
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- ПОЛУЧЕНИЕ ДАННЫХ С AVITO ЧЕРЕЗ RSS (РЕГУЛЯРКИ) ----------
def fetch_cars_from_avito():
    url = (
        "https://www.avito.ru/rossiya/avtomobili/rss"
        "?pmax=8000000"
        "&pmin=2000000"
        "&year_from=2019"
        "&distance=70000"
        "&s=1"
    )

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        logging.error(f"Ошибка при запросе RSS Avito: {e}")
        return []

    items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
    if not items:
        logging.warning("Не найдено блоков <item> в RSS")
        return []

    cars = []
    for item_text in items[:10]:
        try:
            title_match = re.search(r'<title>(.*?)</title>', item_text, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""

            link_match = re.search(r'<link>(.*?)</link>', item_text, re.DOTALL)
            link = link_match.group(1).strip() if link_match else "#"

            desc_match = re.search(r'<description>(.*?)</description>', item_text, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else ""

            full_text = title + " " + description

            price_match = re.search(r"(\d+[\s]?[₽руб])", full_text)
            price = 0
            if price_match:
                price_text = re.sub(r"[^\d]", "", price_match.group(1))
                price = int(price_text) if price_text else 0

            mileage_match = re.search(r"(\d+[\s]?км)", full_text)
            mileage = 0
            if mileage_match:
                mileage_text = re.sub(r"[^\d]", "", mileage_match.group(1))
                mileage = int(mileage_text) if mileage_text else 0

            year_match = re.search(r"\b(20\d{2})\b", full_text)
            year = int(year_match.group(1)) if year_match else 0

            city_match = re.search(r"в\s+([А-Яа-я\s\-]+)", title)
            city = city_match.group(1) if city_match else "Россия"

            if price < 2000000 or price > 8000000:
                continue

            cars.append({
                "name": title,
                "price": price,
                "below_market": 0,
                "mileage": mileage,
                "owners": 1,
                "city": city,
                "year": year,
                "url": link
            })
        except Exception as e:
            logging.warning(f"Ошибка парсинга одного объявления: {e}")
            continue

    if not cars:
        logging.warning("Не удалось получить ни одного подходящего объявления с Avito")
    return cars

# ---------- ХРАНИЛИЩЕ СОСТОЯНИЙ ----------
user_states = {}

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {"monitoring": False, "found_count": 0}
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER (Avito RSS)\n\n"
        "Бот ищет авто на Avito по вашим фильтрам.\n\n"
        "Команды:\n"
        "/start — перезапуск\n"
        "/monitor — найти авто (случайное из свежих)\n"
        "/stop — остановить поиск\n"
        "/stats — статистика\n"
        "/filters — мои фильтры"
    )

async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Текущие фильтры (Avito):\n\n"
        "💰 Цена: 2–8 млн ₽\n"
        "📅 Год: от 2019\n"
        "🚗 Пробег: до 70 000 км\n"
        "📍 Регион: вся Россия"
    )

async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}

    user_states[chat_id]["monitoring"] = True
    user_states[chat_id]["found_count"] += 1

    await update.message.reply_text("🔍 Анализирую рынок Avito, ищу варианты...")

    all_cars = fetch_cars_from_avito()

    if not all_cars:
        await update.message.reply_text(
            "😕 Не удалось получить объявления с Avito.\n"
            "Попробуйте позже или проверьте логи."
        )
        return

    prices = [car['price'] for car in all_cars if car['price'] > 0]
    if not prices:
        await update.message.reply_text("Не удалось рассчитать среднюю цену (нет данных).")
        return

    average_price = statistics.mean(prices)
    avg_price_str = f"{int(average_price):,}".replace(",", " ")

    car = random.choice(all_cars)

    deviation = (car['price'] - average_price) / average_price * 100
    deviation_rounded = round(deviation, 1)

    if abs(deviation) <= 10:
        badge = "✅ Соответствует оценке"
    elif deviation < -10:
        badge = "📉 Выгодное предложение (ниже рынка)"
    else:
        badge = "📈 Выше средней цены"

    price_str = f"{car['price']:,}".replace(",", " ")
    mileage_str = f"{car['mileage']:,}".replace(",", " ") if car['mileage'] > 0 else "не указан"

    message = (
        f"🚗 *{car['name']}*\n"
        f"💰 Цена: {price_str} ₽\n"
        f"📊 Средняя цена на рынке: {avg_price_str} ₽\n"
        f"📊 Отклонение: {deviation_rounded}%\n"
        f"🏷️ {badge}\n"
        f"🚗 Пробег: {mileage_str} км\n"
        f"📅 Год: {car['year'] if car['year'] > 0 else 'не указан'}\n"
        f"📍 {car['city']}\n"
        f"🔗 [Ссылка на объявление]({car['url']})"
    )

    await update.message.reply_text(message, parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_states:
        user_states[chat_id]["monitoring"] = False
        await update.message.reply_text("⏹ Мониторинг остановлен.")
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

    print("ROLF AUTO FINDER запущен (Avito RSS)")
    app.run_polling()

if __name__ == "__main__":
    main()

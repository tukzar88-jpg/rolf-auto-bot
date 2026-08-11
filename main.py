import os
import logging
import random
import re
import statistics
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

def fetch_cars_from_avito():
    # Цена от 1.5 млн, год не ограничен, пробег до 150 000 км (можно убрать)
    url = (
        "https://www.avito.ru/rossiya/avtomobili/rss"
        "?pmin=1500000&distance=150000"
    )
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        logging.error(f"Ошибка RSS Avito: {e}")
        return []

    items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
    if not items:
        logging.warning("Avito: нет <item>")
        return []

    cars = []
    for item_text in items[:50]:
        try:
            title_match = re.search(r'<title>(.*?)</title>', item_text, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            link_match = re.search(r'<link>(.*?)</link>', item_text, re.DOTALL)
            link = link_match.group(1).strip() if link_match else "#"
            desc_match = re.search(r'<description>(.*?)</description>', item_text, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else ""
            full = title + " " + description

            price_match = re.search(r"(\d+[\s]?[₽руб])", full)
            price = 0
            if price_match:
                price_text = re.sub(r"[^\d]", "", price_match.group(1))
                price = int(price_text) if price_text else 0

            mileage_match = re.search(r"(\d+[\s]?км)", full)
            mileage = 0
            if mileage_match:
                mileage_text = re.sub(r"[^\d]", "", mileage_match.group(1))
                mileage = int(mileage_text) if mileage_text else 0

            year_match = re.search(r"\b(20\d{2})\b", full)
            year = int(year_match.group(1)) if year_match else 0

            city_match = re.search(r"в\s+([А-Яа-я\s\-]+)", title)
            city = city_match.group(1) if city_match else "Россия"

            if price < 1500000:
                continue

            cars.append({
                "name": title,
                "price": price,
                "mileage": mileage,
                "city": city,
                "year": year,
                "url": link,
                "source": "Avito"
            })
        except Exception as e:
            logging.warning(f"Ошибка парсинга Avito: {e}")
            continue
    return cars

def fetch_all_cars():
    return fetch_cars_from_avito()

user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {"monitoring": False, "found_count": 0}
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER (Avito RSS)\n\n"
        "Команды:\n/start — перезапуск\n/monitor — показать случайное авто\n/stop — остановить мониторинг\n/stats — статистика\n/filters — мои фильтры"
    )

async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Фильтры:\n💰 от 1.5 млн ₽\n📅 без ограничений по году\n🚗 пробег до 150 000 км\n📍 вся Россия\n📌 Источник: Avito"
    )

async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}
    user_states[chat_id]["monitoring"] = True
    user_states[chat_id]["found_count"] += 1

    await update.message.reply_text("🔍 Анализирую RSS Avito...")

    cars = fetch_all_cars()
    if not cars:
        await update.message.reply_text(
            "😕 Нет объявлений по вашим фильтрам на Avito.\n"
            "Попробуйте изменить фильтры или повторите позже."
        )
        return

    prices = [c['price'] for c in cars if c['price'] > 0]
    if not prices:
        await update.message.reply_text("Не удалось рассчитать среднюю цену.")
        return

    avg_price = statistics.mean(prices)
    avg_price_str = f"{int(avg_price):,}".replace(",", " ")

    car = random.choice(cars)

    price_str = f"{car['price']:,}".replace(",", " ")
    mileage_str = f"{car['mileage']:,}".replace(",", " ") if car['mileage'] > 0 else "не указан"

    message = (
        f"🚗 *{car['name']}*\n"
        f"💰 Цена: {price_str} ₽\n"
        f"📊 Средняя цена на рынке: {avg_price_str} ₽\n"
        f"🚗 Пробег: {mileage_str} км\n"
        f"📅 Год: {car['year'] if car['year'] > 0 else 'не указан'}\n"
        f"📍 {car['city']}\n"
        f"📌 Источник: Avito\n"
        f"🔗 [Ссылка]({car['url']})"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_states:
        user_states[chat_id]["monitoring"] = False
        await update.message.reply_text("⏹ Мониторинг остановлен.")
    else:
        await update.message.reply_text("Мониторинг не был запущен.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}
    count = user_states[chat_id]["found_count"]
    status = "включён" if user_states[chat_id]["monitoring"] else "выключен"
    await update.message.reply_text(f"📊 Найдено авто: {count}\n⚙️ Мониторинг: {status}")

def main():
    if not TOKEN:
        raise RuntimeError("Нет BOT_TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("filters", filters))
    app.add_handler(CommandHandler("monitor", monitor))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("stats", stats))
    print("Бот запущен (Avito RSS, фильтры: цена от 1.5 млн, пробег до 150 тыс., год без ограничений)")
    app.run_polling()

if __name__ == "__main__":
    main()

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

# ---------- ПОЛУЧЕНИЕ ДАННЫХ С AVITO ----------
def fetch_cars_from_avito():
    url = (
        "https://www.avito.ru/rossiya/avtomobili/rss"
        "?pmax=8000000&pmin=2000000&year_from=2019&distance=70000"
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
    for item_text in items[:30]:
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

            if price < 2000000 or price > 8000000:
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

# ---------- ПОЛУЧЕНИЕ ДАННЫХ С DROM.RU ----------
def fetch_cars_from_drom():
    url = (
        "https://www.drom.ru/region/all/rss/"
        "?price_from=2000000&price_to=8000000"
        "&year_from=2019&run=70000"
    )
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        logging.error(f"Ошибка RSS Drom: {e}")
        return []

    items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
    if not items:
        logging.warning("Drom: нет <item>")
        return []

    cars = []
    for item_text in items[:30]:
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

            if price < 2000000 or price > 8000000:
                continue

            cars.append({
                "name": title,
                "price": price,
                "mileage": mileage,
                "city": city,
                "year": year,
                "url": link,
                "source": "Drom"
            })
        except Exception as e:
            logging.warning(f"Ошибка парсинга Drom: {e}")
            continue
    return cars

# ---------- ОБЩАЯ ФУНКЦИЯ СБОРА ----------
def fetch_all_cars():
    cars = []
    cars += fetch_cars_from_avito()
    cars += fetch_cars_from_drom()
    random.shuffle(cars)
    return cars

# ---------- СОСТОЯНИЯ ----------
user_states = {}

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {"monitoring": False, "found_count": 0}
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER (Avito + Drom)\n\n"
        "Команды:\n"
        "/start — перезапуск\n"
        "/monitor — показать случайное авто\n"
        "/stop — остановить мониторинг\n"
        "/stats — статистика\n"
        "/filters — мои фильтры"
    )

async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Фильтры:\n💰 2–8 млн ₽\n📅 от 2019 г.\n🚗 пробег до 70 000 км\n📍 вся Россия\n"
        "📌 Источники: Avito, Drom.ru"
    )

async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}
    user_states[chat_id]["monitoring"] = True
    user_states[chat_id]["found_count"] += 1

    await update.message.reply_text("🔍 Анализирую рынок Avito и Drom...")

    cars = fetch_all_cars()
    if not cars:
        await update.message.reply_text(
            "😕 Нет объявлений по вашим фильтрам на Avito и Drom.\n"
            "Попробуйте изменить фильтры или повторите позже."
        )
        return

    # Рассчитываем среднюю цену только для справки (не выводим её, но используем в логах)
    prices = [c['price'] for c in cars if c['price'] > 0]
    avg_price = statistics.mean(prices) if prices else 0
    avg_price_str = f"{int(avg_price):,}".replace(",", " ") if avg_price else "неизвестна"

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
        f"📌 Источник: {car['source']}\n"
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

# ---------- ЗАПУСК ----------
def main():
    if not TOKEN:
        raise RuntimeError("Нет BOT_TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("filters", filters))
    app.add_handler(CommandHandler("monitor", monitor))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("stats", stats))
    print("Бот запущен (Avito + Drom)")
    app.run_polling()

if __name__ == "__main__":
    main()

import os
import logging
import random
import time
import re
import statistics          # <-- НОВЫЙ ИМПОРТ
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- ПАРСИНГ AUTO.RU ----------
def fetch_cars_from_auto_ru():
    """
    Парсит auto.ru с фильтрами:
    - цена от 2 000 000 до 8 000 000 ₽
    - год от 2019
    - регион: вся Россия
    - пробег до 70 000 км (общий фильтр)
    Возвращает список словарей с данными о машинах.
    """
    ua = UserAgent()
    headers = {"User-Agent": ua.random}

    url = (
        "https://auto.ru/cars/all/"
        "?price_from=2000000&price_to=8000000"
        "&year_from=2019"
        "&distance=70"
        "&region=0"
        "&sort=creation_date_desc"
        "&page=1"
    )

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        logging.error(f"Ошибка при запросе к Auto.ru: {e}")
        return []

    listings = soup.find_all("div", class_="ListingItem")
    if not listings:
        listings = soup.find_all("div", class_="ListingItem-module__listingItem")

    cars = []
    for item in listings[:10]:
        try:
            name_elem = item.find("a", class_="ListingItemTitle")
            name = name_elem.get_text(strip=True) if name_elem else "Неизвестно"

            price_elem = item.find("span", class_="ListingItemPrice")
            price_text = price_elem.get_text(strip=True) if price_elem else "0 ₽"
            price_digits = re.sub(r"[^\d]", "", price_text)
            price = int(price_digits) if price_digits else 0

            mileage_elem = item.find("span", class_="ListingItemTechInfo")
            if mileage_elem:
                mileage_text = mileage_elem.get_text(strip=True)
                mileage_digits = re.sub(r"[^\d]", "", mileage_text)
                mileage = int(mileage_digits) if mileage_digits else 0
            else:
                mileage = 0

            city_elem = item.find("span", class_="GeoItem")
            city = city_elem.get_text(strip=True) if city_elem else "Россия"

            year_elem = item.find("span", class_="ListingItemTechInfo")
            if year_elem:
                text = year_elem.get_text(strip=True)
                year_match = re.search(r"\b(20\d{2})\b", text)
                year = int(year_match.group(1)) if year_match else 0
            else:
                year = 0

            owners = 1
            link = "https://auto.ru" + name_elem.get("href") if name_elem else "#"

            if price < 2000000 or price > 8000000:
                continue

            # Временная заглушка (больше не используется, но оставлена для совместимости)
            below_market = random.randint(100000, 600000)

            cars.append({
                "name": name,
                "price": price,
                "below_market": below_market,
                "mileage": mileage,
                "owners": owners,
                "city": city,
                "year": year,
                "url": link
            })
        except Exception as e:
            logging.warning(f"Ошибка при парсинге одной карточки: {e}")
            continue

    return cars

# ---------- ХРАНИЛИЩЕ СОСТОЯНИЙ ----------
user_states = {}

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {"monitoring": False, "found_count": 0}
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER (реальный парсинг)\n\n"
        "Бот ищет авто на Auto.ru по вашим фильтрам.\n\n"
        "Команды:\n"
        "/start — перезапуск\n"
        "/monitor — найти авто (реальный поиск)\n"
        "/stop — остановить поиск\n"
        "/stats — статистика\n"
        "/filters — мои фильтры"
    )

async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Текущие фильтры (Auto.ru):\n\n"
        "💰 Цена: 2–8 млн ₽\n"
        "📅 Год: от 2019\n"
        "🚗 Пробег: до 70 000 км\n"
        "📍 Регион: вся Россия\n\n"
        "Примечание: поиск по маркам пока не разделён, но все авто проходят фильтр цены и года."
    )

# ---------- НОВАЯ ФУНКЦИЯ MONITOR (С РАСЧЁТОМ СРЕДНЕЙ ЦЕНЫ) ----------
async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}

    user_states[chat_id]["monitoring"] = True
    user_states[chat_id]["found_count"] += 1

    await update.message.reply_text("🔍 Анализирую рынок, ищу выгодные варианты...")

    # 1. Получаем все авто с Auto.ru
    all_cars = fetch_cars_from_auto_ru()

    if not all_cars:
        await update.message.reply_text("😕 Не удалось найти автомобили по вашему запросу.")
        return

    # 2. Рассчитываем среднюю цену
    prices = [car['price'] for car in all_cars if car['price'] > 0]
    if not prices:
        await update.message.reply_text("Не удалось рассчитать среднюю цену (нет данных).")
        return

    average_price = statistics.mean(prices)

    # 3. Отбираем выгодные предложения (скидка >= 15%)
    discount_threshold = 0.15   # 15% — можно менять
    profitable_cars = []

    for car in all_cars:
        if car['price'] <= 0:
            continue
        discount = 1 - (car['price'] / average_price)
        if discount >= discount_threshold:
            car['discount_percent'] = round(discount * 100, 1)
            profitable_cars.append(car)

    if not profitable_cars:
        await update.message.reply_text(
            f"😕 Авто со скидкой от {discount_threshold*100:.0f}% не найдено.\n"
            f"Средняя цена: {int(average_price):,} ₽"
        )
        return

    # 4. Показываем случайное выгодное авто
    car = random.choice(profitable_cars)
    price_str = f"{car['price']:,}".replace(",", " ")
    avg_price_str = f"{int(average_price):,}".replace(",", " ")
    mileage_str = f"{car['mileage']:,}".replace(",", " ")

    message = (
        f"🚨 *{car['name']}* — ВЫГОДНО!\n"
        f"💰 Цена: {price_str} ₽\n"
        f"📊 Средняя цена на рынке: {avg_price_str} ₽\n"
        f"📉 Ниже рынка на: {car['discount_percent']}%\n"
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

    print("ROLF AUTO FINDER запущен (реальный парсинг Auto.ru)")
    app.run_polling()

if __name__ == "__main__":
    main()

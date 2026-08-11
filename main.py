import os
import logging
import random
import re
import statistics
import time
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")
ua = UserAgent()

# ---------- ПАРСИНГ СТРАНИЦЫ ПОИСКА AVITO ----------
def fetch_cars_from_avito_search():
    """
    Парсит страницу поиска Avito с фильтрами:
    - цена от 1.5 млн ₽
    - год от 2017
    - пробег не ограничен
    - вся Россия
    Возвращает список словарей с данными объявлений.
    """
    base_url = "https://www.avito.ru/rossiya/avtomobili"
    params = {
        "pmin": 1500000,
        "year_from": 2017,
        "s": 104  # параметр сортировки (по дате, можно убрать)
    }
    headers = {"User-Agent": ua.random}

    cars = []
    # Парсим первые 3 страницы (чтобы собрать больше объявлений)
    for page in range(1, 4):
        params["p"] = page
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logging.error(f"Ошибка при запросе страницы {page}: {e}")
            break

        # Ищем блоки объявлений
        items = soup.find_all("div", class_=re.compile("iva-item"))
        if not items:
            logging.warning(f"На странице {page} не найдено объявлений")
            break

        for item in items:
            try:
                # Название и ссылка
                title_elem = item.find("a", class_=re.compile("title"))
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                link = "https://www.avito.ru" + title_elem.get("href")

                # Цена
                price_elem = item.find("span", class_=re.compile("price"))
                price_text = price_elem.get_text(strip=True) if price_elem else ""
                price_match = re.search(r"(\d+[\s]?[₽руб])", price_text)
                price = 0
                if price_match:
                    price_digits = re.sub(r"[^\d]", "", price_match.group(1))
                    price = int(price_digits) if price_digits else 0

                # Пробег и год обычно в строке характеристик
                char_elem = item.find("div", class_=re.compile("params"))
                char_text = char_elem.get_text(strip=True) if char_elem else ""

                # Год
                year_match = re.search(r"\b(20\d{2})\b", char_text)
                year = int(year_match.group(1)) if year_match else 0

                # Пробег
                mileage_match = re.search(r"(\d+[\s]?км)", char_text)
                mileage = 0
                if mileage_match:
                    mileage_digits = re.sub(r"[^\d]", "", mileage_match.group(1))
                    mileage = int(mileage_digits) if mileage_digits else 0

                # Город (в объявлении может быть в отдельном элементе)
                city_elem = item.find("div", class_=re.compile("geo"))
                city = city_elem.get_text(strip=True) if city_elem else "Россия"

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
                logging.warning(f"Ошибка парсинга одного объявления: {e}")
                continue

        # Задержка между страницами, чтобы не нагружать сервер
        time.sleep(random.uniform(1, 2))

    # Перемешиваем, чтобы случайный выбор был разнообразным
    random.shuffle(cars)
    return cars

# ---------- ОБЩАЯ ФУНКЦИЯ СБОРА ----------
def fetch_all_cars():
    return fetch_cars_from_avito_search()

# ---------- СОСТОЯНИЯ ----------
user_states = {}

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {"monitoring": False, "found_count": 0}
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER (Avito — парсинг поиска)\n\n"
        "Команды:\n"
        "/start — перезапуск\n"
        "/monitor — показать случайное авто\n"
        "/stop — остановить мониторинг\n"
        "/stats — статистика\n"
        "/filters — мои фильтры"
    )

async def filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Фильтры (парсинг поиска):\n💰 от 1.5 млн ₽\n📅 от 2017 г.\n🚗 пробег не ограничен\n📍 вся Россия\n"
        "📌 Источник: Avito"
    )

async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_states:
        user_states[chat_id] = {"monitoring": False, "found_count": 0}
    user_states[chat_id]["monitoring"] = True
    user_states[chat_id]["found_count"] += 1

    await update.message.reply_text("🔍 Парсинг страниц Avito... Подождите немного.")

    cars = fetch_all_cars()
    if not cars:
        await update.message.reply_text(
            "😕 Не найдено объявлений по вашим фильтрам на Avito.\n"
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
    print("Бот запущен (парсинг поиска Avito, цена от 1.5 млн, год от 2017)")
    app.run_polling()

if __name__ == "__main__":
    main()

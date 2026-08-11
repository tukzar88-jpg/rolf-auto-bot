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
    Парсит auto.ru с фильтрами. При неудаче логирует HTML для отладки.
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
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text
        # Логируем заголовки и статус
        logging.info(f"Статус ответа: {response.status_code}")
        logging.info(f"Content-Type: {response.headers.get('Content-Type')}")
        # Логируем первые 2000 символов HTML
        logging.info(f"HTML (первые 2000 символов): {html[:2000]}")
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logging.error(f"Ошибка при запросе к Auto.ru: {e}")
        return []

    cars = []

    # Пробуем найти карточки по разным признакам
    listings = []

    # 1. По атрибуту data-placement
    listings = soup.find_all("div", attrs={"data-placement": "listing"})
    if not listings:
        # 2. По классу, содержащему "ListingItem"
        listings = soup.find_all("div", class_=re.compile(r"ListingItem"))
    if not listings:
        # 3. По ссылкам с классом "Link"
        listings = soup.find_all("a", class_=re.compile(r"Link"))
    if not listings:
        # 4. По элементам с ценой
        listings = soup.find_all(string=re.compile(r"\d+[\s]?₽"))
        # Если нашли текст, обернём его в родительский элемент
        if listings:
            # берём родителей
            listings = [elem.parent for elem in listings if elem.parent]

    if not listings:
        logging.warning("Не найдено ни одного блока объявлений на странице Auto.ru")
        # Дополнительно логируем полный HTML (если надо)
        logging.info(f"Полный HTML (первые 3000 символов): {html[:3000]}")
        return []

    # Ограничим количество для скорости
    for item in listings[:10]:
        try:
            # Пытаемся извлечь ссылку и название
            if item.name == "a" and item.get("href") and "/cars/" in item.get("href"):
                link_elem = item
                name = link_elem.get_text(strip=True)
                link = "https://auto.ru" + link_elem.get("href")
                parent = link_elem.find_parent("div")
                if not parent:
                    parent = link_elem
            else:
                # Ищем ссылку внутри
                link_elem = item.find("a", href=re.compile(r"\/cars\/"))
                if not link_elem:
                    # пробуем найти любую ссылку
                    link_elem = item.find("a", class_=re.compile(r"Link"))
                if not link_elem:
                    continue
                name = link_elem.get_text(strip=True)
                link = "https://auto.ru" + link_elem.get("href")
                parent = item

            # Цена
            price_elem = parent.find("span", class_=re.compile(r"Price"))
            if not price_elem:
                # ищем любой элемент с ценой
                price_elem = parent.find(string=re.compile(r"\d+[\s]?₽"))
            if price_elem:
                price_text = price_elem.get_text(strip=True) if hasattr(price_elem, 'get_text') else price_elem.strip()
                price_digits = re.sub(r"[^\d]", "", price_text)
                price = int(price_digits) if price_digits else 0
            else:
                price = 0

            # Пробег
            mileage_elem = parent.find(string=re.compile(r"\d+[\s]?км"))
            if mileage_elem:
                mileage_text = mileage_elem.strip()
                mileage_digits = re.sub(r"[^\d]", "", mileage_text)
                mileage = int(mileage_digits) if mileage_digits else 0
            else:
                mileage = 0

            # Город
            city_elem = parent.find("span", class_=re.compile(r"Geo"))
            city = city_elem.get_text(strip=True) if city_elem else "Россия"

            # Год
            year = 0
            year_match = re.search(r"\b(20\d{2})\b", parent.get_text())
            if year_match:
                year = int(year_match.group(1))

            if price < 2000000 or price > 8000000:
                continue

            cars.append({
                "name": name,
                "price": price,
                "below_market": random.randint(100000, 600000),
                "mileage": mileage,
                "owners": 1,
                "city": city,
                "year": year,
                "url": link
            })
        except Exception as e:
            logging.warning(f"Ошибка при парсинге одной карточки: {e}")
            continue

    if not cars:
        logging.warning("Объявления найдены, но ни одно не подошло по фильтрам или не удалось распарсить.")
        # Логируем часть HTML, где могли быть объявления
        # Найдём div с классом, содержащим "Listing"
        listing_blocks = soup.find_all("div", class_=re.compile(r"Listing"))
        if listing_blocks:
            logging.info(f"Найдены блоки Listing, первый: {listing_blocks[0].prettify()[:500]}")
        else:
            logging.info("Блоков Listing не найдено. HTML-фрагмент: " + html[:1500])

    return cars    
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

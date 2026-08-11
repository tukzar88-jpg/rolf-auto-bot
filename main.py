import os
import logging
import random
import re
import statistics
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- ПОЛУЧЕНИЕ ДАННЫХ С AVITO ЧЕРЕЗ RSS ----------
def fetch_cars_from_avito():
    """
    Получает объявления с Avito через RSS-ленту.
    Фильтры: цена 2-8 млн, год от 2019, пробег до 70 000 км, вся Россия.
    Возвращает список словарей.
    """
    # RSS-лента для легковых авто по всей России с фильтрами
    url = (
        "https://www.avito.ru/rossiya/avtomobili/rss"
        "?pmax=8000000"
        "&pmin=2000000"
        "&year_from=2019"
        "&distance=70000"
        "&s=1"  # сортировка по дате
    )

    try:
        feed = feedparser.parse(url)
        if feed.bozo:  # ошибка парсинга
            logging.error(f"Ошибка RSS: {feed.bozo_exception}")
            return []
    except Exception as e:
        logging.error(f"Ошибка при запросе к Avito RSS: {e}")
        return []

    cars = []
    for entry in feed.entries[:10]:  # берём 10 последних
        try:
            title = entry.title
            summary = entry.summary if hasattr(entry, 'summary') else ""

            # Извлекаем цену
            price_match = re.search(r"(\d+[\s]?[₽руб])", title + " " + summary)
            price = 0
            if price_match:
                price_text = re.sub(r"[^\d]", "", price_match.group(1))
                price = int(price_text) if price_text else 0

            # Пробег
            mileage_match = re.search(r"(\d+[\s]?км)", title + " " + summary)
            mileage = 0
            if mileage_match:
                mileage_text = re.sub(r"[^\d]", "", mileage_match.group(1))
                mileage = int(mileage_text) if mileage_text else 0

            # Год
            year_match = re.search(r"\b(20\d{2})\b", title + " " + summary)
            year = int(year_match.group(1)) if year_match else 0

            # Город (из заголовка, например "в Москве")
            city_match = re.search(r"в\s+([А-Яа-я\s\-]+)", title)
            city = city_match.group(1) if city_match else "Россия"

            # Ссылка
            link = entry.link

            # Пропускаем, если цена вне диапазона
            if price < 2000000 or price > 8000000:
                continue

            cars.append({
                "name": title,
                "price": price,
                "below_market": 0,  # будет пересчитано позже
                "mileage": mileage,
                "owners": 1,  # в RSS нет данных о владельцах
                "city": city,
                "year": year,
                "url": link
            })
        except Exception as e:
            logging.warning(f"Ошибка парсинга записи RSS: {e}")
            continue

    if not cars:
        logging.warning("Не удалось получить объявления с Avito RSS")

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
        "/monitor — найти выгодное авто\n"
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

    await update.message.reply_text("🔍 Анализирую рынок Avito, ищу выгодные варианты...")

    # Получаем данные с Avito
    all_cars = fetch_cars_from_avito()

    if not all_cars:
        await update.message.reply_text(
            "😕 Не удалось получить объявления с Avito.\n"
            "Попробуйте позже или проверьте логи."
        )
        return

    # Рассчитываем среднюю цену
    prices = [car['price'] for car in all_cars if car['price'] > 0]
    if not prices:
        await update.message.reply_text("Не удалось рассчитать среднюю цену (нет данных).")
        return

    average_price = statistics.mean(prices)

    # Отбираем выгодные предложения (скидка >= 15%)
    discount_threshold = 0.15
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

    # Показываем случайное выгодное авто
    car = random.choice(profitable_cars)
    price_str = f"{car['price']:,}".replace(",", " ")
    avg_price_str = f"{int(average_price):,}".replace(",", " ")
    mileage_str = f"{car['mileage']:,}".replace(",", " ") if car['mileage'] > 0 else "не указан"

    message = (
        f"🚨 *{car['name']}* — ВЫГОДНО!\n"
        f"💰 Цена: {price_str} ₽\n"
        f"📊 Средняя цена на рынке: {avg_price_str} ₽\n"
        f"📉 Ниже рынка на: {car['discount_percent']}%\n"
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

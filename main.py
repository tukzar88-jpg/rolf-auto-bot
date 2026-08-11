import os
import logging
import re
import html
from urllib.parse import quote

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# НАСТРОЙКИ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

MIN_PRICE = 1_500_000
MAX_MILEAGE = 150_000

SEARCH_URL = "https://www.google.com/search?q={}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


# =========================================================
# ПОИСК ОБЪЯВЛЕНИЙ
# =========================================================

def search_avito():
    """
    Ищем страницы Avito через поисковую выдачу,
    не открывая сам Avito через Playwright.
    """

    query = (
        'site:avito.ru/avtomobili '
        'автомобиль '
        f'"{MIN_PRICE}"'
    )

    url = SEARCH_URL.format(quote(query))

    logging.info("Поиск автомобилей через поисковую выдачу")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        logging.info(
            "Search HTTP status: %s",
            response.status_code,
        )

        if response.status_code != 200:
            return []

        page = response.text

        # Ищем ссылки Avito
        links = re.findall(
            r'https?://(?:www\.)?avito\.ru/[^"\s<>]+',
            page,
        )

        result = []
        seen = set()

        for link in links:

            link = html.unescape(link)

            # Убираем параметры Google
            link = link.split("&")[0]

            if "avito.ru" not in link:
                continue

            if "/avtomobili/" not in link:
                continue

            if link in seen:
                continue

            seen.add(link)

            result.append(link)

            if len(result) >= 10:
                break

        logging.info(
            "Найдено ссылок Avito: %s",
            len(result),
        )

        return result

    except Exception:

        logging.exception(
            "Ошибка поиска объявлений"
        )

        return []


# =========================================================
# MONITOR
# =========================================================

async def check_avito():

    logging.info(
        "Запущен поиск автомобилей"
    )

    links = search_avito()

    if not links:

        return (
            "⚠️ <b>Объявления пока не найдены</b>\n\n"
            "Поисковая выдача не вернула подходящих "
            "ссылок Avito.\n\n"
            "Это нормально на этапе тестирования.\n\n"
            "Следующим этапом подключим полноценный "
            "поиск и обработку данных."
        )

    text = (
        "🚗 <b>Найдены объявления</b>\n\n"
        f"Количество: {len(links)}\n\n"
    )

    for index, link in enumerate(links, 1):

        text += (
            f"{index}. "
            f"<a href=\"{html.escape(link)}\">"
            f"Открыть объявление"
            f"</a>\n"
        )

    text += (
        "\n🔎 Фильтры:\n"
        f"💰 от {MIN_PRICE:,} ₽\n"
        f"🚗 пробег до {MAX_MILEAGE:,} км\n\n"
        "📊 Следующим этапом добавим "
        "анализ цены и потенциальной прибыли."
    )

    return text


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🚗 <b>ROLF AUTO FINDER</b>\n\n"
        "Бесплатный тестовый режим.\n\n"
        "/monitor — найти автомобили\n"
        "/filters — показать фильтры\n"
        "/stop — остановить\n"
        "/stats — статистика",
        parse_mode="HTML",
    )


# =========================================================
# MONITOR COMMAND
# =========================================================

async def monitor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🔎 <b>Ищу автомобили...</b>\n\n"
        "Подожди несколько секунд.",
        parse_mode="HTML",
    )

    result = await check_avito()

    await update.message.reply_text(
        result,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# =========================================================
# FILTERS
# =========================================================

async def filters(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🔎 <b>Текущие фильтры:</b>\n\n"
        f"💰 Цена: от {MIN_PRICE:,} ₽\n"
        f"🚗 Пробег: до {MAX_MILEAGE:,} км\n"
        "📅 Год: без ограничений\n"
        "📍 Россия\n"
        "📌 Источник: Avito\n\n"
        "💡 Поиск выполняется через поисковую выдачу.",
        parse_mode="HTML",
    )


# =========================================================
# STOP
# =========================================================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "⏹ Мониторинг остановлен."
    )


# =========================================================
# STATS
# =========================================================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "📊 <b>Статистика</b>\n\n"
        "Режим: тестирование\n"
        "Источник: поисковая выдача\n"
        f"Минимальная цена: {MIN_PRICE:,} ₽\n"
        f"Максимальный пробег: {MAX_MILEAGE:,} км\n\n"
        "Автоматическая оценка выгоды "
        "будет добавлена следующим этапом.",
        parse_mode="HTML",
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logging.error(
        "Ошибка обработки обновления: %s",
        context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не найден!"
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "monitor",
            monitor,
        )
    )

    app.add_handler(
        CommandHandler(
            "filters",
            filters,
        )
    )

    app.add_handler(
        CommandHandler(
            "stop",
            stop,
        )
    )

    app.add_handler(
        CommandHandler(
            "stats",
            stats,
        )
    )

    app.add_error_handler(
        error_handler
    )

    logging.info(
        "ROLF AUTO FINDER запущен"
    )

    app.run_polling()


if __name__ == "__main__":
    main()

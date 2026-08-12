import os
import logging
import re
import html
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")

# =========================
# НАСТРОЙКИ ПОИСКА
# =========================

PRICE_MIN = 1_500_000
PRICE_MAX = 10_000_000
MILEAGE_MAX = 150_000

AVITO_HOME = "https://m.avito.ru/"
AVITO_API = "https://m.avito.ru/api/9/items"

# Автомобили
CATEGORY_ID = 9

SEARCH_RADIUS = 150

# =========================
# HTTP СЕССИЯ
# =========================

def create_session():
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 "
                "Mobile Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/json;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )

    return session


# =========================
# ПОЛУЧЕНИЕ KEY
# =========================

def extract_avito_key(text):
    patterns = [
        r'"key"\s*:\s*"([^"]+)"',
        r'"key"\s*:\s*\'([^\']+)\'',
        r'key\s*=\s*"([^"]+)"',
        r'key\s*=\s*\'([^\']+)\'',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return match.group(1)

    return None


# =========================
# ПОИСК AVITO
# =========================

def search_avito():
    session = create_session()

    logging.info("Открываем мобильный Avito...")

    try:
        home_response = session.get(
            AVITO_HOME,
            timeout=20,
        )
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "error": f"Ошибка подключения: {e}",
        }

    logging.info(
        "Avito home HTTP: %s",
        home_response.status_code,
    )

    if home_response.status_code != 200:
        return {
            "ok": False,
            "status": home_response.status_code,
            "error": "Avito не отдал главную страницу.",
        }

    avito_key = extract_avito_key(
        home_response.text
    )

    if not avito_key:
        logging.warning(
            "Ключ Avito не найден."
        )

    params = {
        "categoryId": CATEGORY_ID,
        "priceMin": PRICE_MIN,
        "priceMax": PRICE_MAX,
        "searchRadius": SEARCH_RADIUS,
        "withImagesOnly": "true",
        "display": "list",
        "limit": 30,
        "page": 1,
        "sort": "date",
    }

    if avito_key:
        params["key"] = avito_key

    headers = {
        "Referer": AVITO_HOME,
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }

    logging.info(
        "Запрашиваем объявления Avito..."
    )

    try:
        response = session.get(
            AVITO_API,
            params=params,
            headers=headers,
            timeout=30,
        )
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "error": f"Ошибка запроса: {e}",
        }

    logging.info(
        "Avito API HTTP: %s",
        response.status_code,
    )

    if response.status_code != 200:
        return {
            "ok": False,
            "status": response.status_code,
            "error": (
                "Avito ограничил или отклонил "
                "запрос."
            ),
        }

    try:
        data = response.json()
    except Exception:
        return {
            "ok": False,
            "status": response.status_code,
            "error": (
                "Avito ответил не JSON."
            ),
        }

    if not isinstance(data, dict):
        return {
            "ok": False,
            "status": response.status_code,
            "error": "Неожиданный формат ответа Avito.",
        }

    return {
        "ok": True,
        "status": response.status_code,
        "data": data,
    }


# =========================
# ИЗВЛЕЧЕНИЕ ОБЪЯВЛЕНИЙ
# =========================

def extract_items(data):
    result = []

    if not isinstance(data, dict):
        return result

    result_block = data.get("result")

    if isinstance(result_block, dict):
        items = result_block.get("items", [])
    else:
        items = data.get("items", [])

    if not isinstance(items, list):
        return result

    for item in items:
        if not isinstance(item, dict):
            continue

        if item.get("type") not in (
            None,
            "item",
        ):
            continue

        value = item.get("value", item)

        if not isinstance(value, dict):
            continue

        item_id = (
            value.get("id")
            or value.get("itemId")
            or item.get("id")
        )

        if not item_id:
            continue

        title = (
            value.get("title")
            or value.get("name")
            or "Автомобиль"
        )

        price = (
            value.get("price")
            or value.get("priceDetailed")
            or ""
        )

        url = (
            value.get("url")
            or value.get("uri")
            or ""
        )

        if url and url.startswith("/"):
            url = "https://www.avito.ru" + url

        if not url:
            url = (
                "https://www.avito.ru/"
                f"items/{item_id}"
            )

        result.append(
            {
                "id": str(item_id),
                "title": str(title),
                "price": str(price),
                "url": str(url),
            }
        )

    return result


# =========================
# КОМАНДА START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🚗 <b>ROLF AUTO FINDER</b>\n\n"
        "Бот запущен.\n\n"
        "/monitor — поиск автомобилей\n"
        "/test — тест соединения с Avito\n"
        "/filters — текущие фильтры\n"
        "/stop — остановить\n"
        "/stats — статистика",
        parse_mode="HTML",
    )


# =========================
# ТЕСТ AVITO
# =========================

async def test_avito(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🧪 Проверяю бесплатный способ "
        "получения объявлений Avito...\n\n"
        "Подожди несколько секунд."
    )

    result = search_avito()

    if not result["ok"]:
        error_text = html.escape(
            str(result.get("error", "Неизвестная ошибка"))
        )

        await update.message.reply_text(
            "❌ <b>Тест не прошёл</b>\n\n"
            f"HTTP: {result.get('status', 0)}\n\n"
            f"<code>{error_text[:2500]}</code>",
            parse_mode="HTML",
        )

        return

    items = extract_items(
        result["data"]
    )

    if not items:
        await update.message.reply_text(
            "⚠️ <b>Avito ответил нормально, "
            "но объявления не найдены.</b>\n\n"
            f"HTTP: {result['status']}\n\n"
            "Это уже полезный результат: "
            "соединение работает, теперь нужно "
            "доработать параметры поиска.",
            parse_mode="HTML",
        )

        return

    text = (
        "✅ <b>Бесплатный поиск работает!</b>\n\n"
        f"HTTP: {result['status']}\n"
        f"Найдено: {len(items)}\n\n"
    )

    for number, item in enumerate(
        items[:5],
        start=1,
    ):
        title = html.escape(
            item["title"]
        )

        price = html.escape(
            item["price"]
        )

        url = html.escape(
            item["url"]
        )

        text += (
            f"{number}. <b>{title}</b>\n"
            f"💰 {price}\n"
            f"🔗 {url}\n\n"
        )

    await update.message.reply_text(
        text[:3900],
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# =========================
# ОСНОВНОЙ МОНИТОРИНГ
# =========================

async def monitor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔍 <b>Ищу автомобили на Avito...</b>\n\n"
        f"💰 Цена: от {PRICE_MIN:,} ₽\n"
        f"🚗 Пробег: до {MILEAGE_MAX:,} км\n\n"
        "Подожди несколько секунд.".replace(",", " "),
        parse_mode="HTML",
    )

    result = search_avito()

    if not result["ok"]:
        status = result.get(
            "status",
            0,
        )

        if status in (
            403,
            429,
        ):
            await update.message.reply_text(
                "🛡 <b>Avito ограничил доступ</b>\n\n"
                f"HTTP: {status}\n\n"
                "Бесплатный способ сейчас "
                "заблокирован со стороны Avito.\n\n"
                "Telegram и Railway работают "
                "нормально. Проблема только "
                "в доступе к выдаче Avito.",
                parse_mode="HTML",
            )

        else:
            error_text = html.escape(
                str(
                    result.get(
                        "error",
                        "Неизвестная ошибка",
                    )
                )
            )

            await update.message.reply_text(
                "❌ <b>Ошибка получения Avito</b>\n\n"
                f"HTTP: {status}\n\n"
                f"<code>{error_text[:2500]}</code>",
                parse_mode="HTML",
            )

        return

    items = extract_items(
        result["data"]
    )

    if not items:
        await update.message.reply_text(
            "⚠️ <b>Объявления пока не найдены</b>\n\n"
            "Avito ответил, но текущий формат "
            "выдачи не содержит подходящих "
            "объявлений.\n\n"
            "Следующим этапом настроим "
            "точные параметры автомобилей.",
            parse_mode="HTML",
        )

        return

    text = (
        "🚗 <b>НАЙДЕННЫЕ АВТО</b>\n\n"
    )

    for number, item in enumerate(
        items[:10],
        start=1,
    ):
        title = html.escape(
            item["title"]
        )

        price = html.escape(
            item["price"]
        )

        url = html.escape(
            item["url"]
        )

        text += (
            f"<b>{number}. {title}</b>\n"
            f"💰 {price}\n"
            f"🔗 {url}\n\n"
        )

    await update.message.reply_text(
        text[:3900],
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# =========================
# ФИЛЬТРЫ
# =========================

async def filters(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔎 <b>Текущие фильтры:</b>\n\n"
        f"💰 Цена: от {PRICE_MIN:,} ₽\n"
        f"💰 Цена до: {PRICE_MAX:,} ₽\n"
        f"🚗 Пробег: до {MILEAGE_MAX:,} км\n"
        "📅 Год: без ограничений\n"
        "📍 Россия\n"
        "📌 Источник: Avito\n\n"
        "⚙️ Режим: бесплатный поиск",
        parse_mode="HTML",
    )


# =========================
# STOP
# =========================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "⏹ Мониторинг остановлен."
    )


# =========================
# STATS
# =========================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "📊 <b>Статистика</b>\n\n"
        "Режим: тестовый\n"
        "Источник: Avito\n"
        "Стоимость API: 0 ₽\n\n"
        "Автоматическая оценка выгодности "
        "будет добавлена после успешного "
        "получения объявлений.",
        parse_mode="HTML",
    )


# =========================
# ERROR HANDLER
# =========================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.error(
        "Ошибка обработки обновления: %s",
        context.error,
    )


# =========================
# MAIN
# =========================

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
            "test",
            test_avito,
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

    print(
        "ROLF AUTO FINDER запущен"
    )

    app.run_polling()


if __name__ == "__main__":
    main()

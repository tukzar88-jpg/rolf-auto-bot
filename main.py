import os
import logging
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")


def check_avito():
    url = (
        "https://www.avito.ru/rossiya/avtomobili"
        "?pmin=1500000"
        "&distance=150000"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20,
            allow_redirects=True,
        )

        status = response.status_code
        content = response.text
        size = len(content)

        logging.info(
            f"Avito status={status}, size={size}, "
            f"url={response.url}"
        )

        lower_content = content.lower()

        if "captcha" in lower_content:
            return (
                "🛡 Avito вернул CAPTCHA.\n\n"
                f"HTTP: {status}\n"
                f"Размер ответа: {size} символов"
            )

        if "доступ ограничен" in lower_content:
            return (
                "🛡 Avito ограничил доступ.\n\n"
                f"HTTP: {status}\n"
                f"Размер ответа: {size} символов"
            )

        if "robot" in lower_content:
            return (
                "🤖 Avito определил запрос как автоматический.\n\n"
                f"HTTP: {status}\n"
                f"Размер ответа: {size} символов"
            )

        if status != 200:
            return (
                "❌ Avito вернул ошибку.\n\n"
                f"HTTP: {status}\n"
                f"Размер ответа: {size} символов"
            )

        # Проверяем характерные элементы страницы
        markers = {
            "объявления": "item" in lower_content,
            "avito": "avito" in lower_content,
            "автомобили": "автомобил" in lower_content,
            "цена": "₽" in content or "руб" in lower_content,
        }

        found = [
            name
            for name, exists in markers.items()
            if exists
        ]

        result = (
            "🔎 Результат проверки Avito\n\n"
            f"HTTP: {status}\n"
            f"Размер ответа: {size} символов\n\n"
            f"Найдено признаков: "
            f"{', '.join(found) if found else 'ничего'}"
        )

        # Показываем небольшой фрагмент ответа
        preview = " ".join(content[:500].split())

        result += (
            "\n\n📄 Первые 500 символов ответа:\n"
            f"<code>{preview[:350]}</code>"
        )

        return result

    except requests.exceptions.Timeout:
        logging.exception("Timeout Avito")

        return (
            "⏱ Avito не ответил за 20 секунд."
        )

    except requests.exceptions.RequestException as e:
        logging.exception("Ошибка запроса Avito")

        return (
            "❌ Ошибка соединения с Avito:\n"
            f"{str(e)[:500]}"
        )

    except Exception as e:
        logging.exception("Неизвестная ошибка")

        return (
            "❌ Неизвестная ошибка:\n"
            f"{str(e)[:500]}"
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER\n\n"
        "Тестовая версия.\n\n"
        "/monitor — проверить Avito\n"
        "/filters — показать фильтры\n"
        "/stop — остановить\n"
        "/stats — статистика"
    )


async def monitor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔍 Проверяю подключение к Avito...\n"
        "Это может занять до 20 секунд."
    )

    result = check_avito()

    await update.message.reply_text(
        result,
        parse_mode="HTML",
    )


async def filters(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔎 Текущие фильтры:\n\n"
        "💰 Цена: от 1 500 000 ₽\n"
        "🚗 Пробег: до 150 000 км\n"
        "📅 Год: без ограничений\n"
        "📍 Регион: вся Россия\n"
        "📌 Источник: Avito"
    )


async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "⏹ Мониторинг остановлен."
    )


async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "📊 Статистика пока недоступна.\n\n"
        "Это диагностическая версия."
    )


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
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("monitor", monitor)
    )

    app.add_handler(
        CommandHandler("filters", filters)
    )

    app.add_handler(
        CommandHandler("stop", stop)
    )

    app.add_handler(
        CommandHandler("stats", stats)
    )

    print("ROLF AUTO FINDER запущен")

    app.run_polling()


if __name__ == "__main__":
    main()

import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from playwright.async_api import async_playwright


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN")


AVITO_URL = (
    "https://www.avito.ru/rossiya/avtomobili"
    "?pmin=1500000"
    "&distance=150000"
)


async def check_avito():
    try:
        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 768,
                },
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )

            page = await context.new_page()

            logging.info("Открываю Avito...")

            response = await page.goto(
                AVITO_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            status = response.status if response else 0

            logging.info(
                f"Avito HTTP status: {status}"
            )

            await page.wait_for_timeout(5000)

            title = await page.title()

            html = await page.content()

            text = await page.locator("body").inner_text()

            logging.info(
                f"Avito title: {title}"
            )

            logging.info(
                f"Размер HTML: {len(html)}"
            )

            lower_text = text.lower()
            lower_html = html.lower()

            # Проверяем CAPTCHA
            captcha_words = [
                "captcha",
                "капча",
                "проверка безопасности",
                "подтвердите, что вы не робот",
                "я не робот",
            ]

            captcha_found = any(
                word in lower_text or word in lower_html
                for word in captcha_words
            )

            if captcha_found:
                await browser.close()

                return (
                    "🛡 <b>Avito показал CAPTCHA</b>\n\n"
                    f"HTTP: {status}\n"
                    f"Заголовок: {title}\n"
                    f"Размер страницы: {len(html)} символов\n\n"
                    "❌ Обычный Playwright-сеанс "
                    "тоже получил защиту."
                )

            # Проверяем наличие автомобилей
            car_markers = [
                "₽",
                "руб",
                "автомобил",
                "пробег",
                "год выпуска",
            ]

            found_markers = [
                marker
                for marker in car_markers
                if marker in lower_text
                or marker in lower_html
            ]

            # Ссылки Avito
            links = await page.locator(
                'a[href*="/avtomobili/"]'
            ).count()

            if links > 0:

                await browser.close()

                return (
                    "✅ <b>Avito открылся!</b>\n\n"
                    f"HTTP: {status}\n"
                    f"Заголовок: {title}\n"
                    f"Ссылок на авто: {links}\n\n"
                    f"Найдены признаки:\n"
                    f"{', '.join(found_markers) if found_markers else 'нет'}\n\n"
                    "🔥 Можно пробовать извлекать объявления."
                )

            # Если CAPTCHA нет, но объявлений тоже нет
            preview = " ".join(
                text[:1000].split()
            )

            await browser.close()

            return (
                "⚠️ <b>Avito открылся, "
                "но объявления не найдены</b>\n\n"
                f"HTTP: {status}\n"
                f"Заголовок: {title}\n"
                f"Ссылок на авто: {links}\n\n"
                f"Фрагмент страницы:\n"
                f"<code>{preview[:1200]}</code>"
            )

    except Exception as e:

        logging.exception(
            "Ошибка Playwright"
        )

        return (
            "❌ <b>Ошибка Playwright</b>\n\n"
            f"<code>{str(e)[:1500]}</code>"
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🚗 ROLF AUTO FINDER\n\n"
        "Бесплатный тестовый режим.\n\n"
        "/monitor — проверить Avito\n"
        "/filters — показать фильтры"
    )


async def monitor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔍 Открываю Avito через браузер...\n\n"
        "Подожди несколько секунд."
    )

    result = await check_avito()

    await update.message.reply_text(
        result,
        parse_mode="HTML",
    )


async def filters(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🔎 Фильтры:\n\n"
        "💰 Цена: от 1 500 000 ₽\n"
        "🚗 Пробег: до 150 000 км\n"
        "📅 Год: без ограничений\n"
        "📍 Россия\n"
        "📌 Источник: Avito"
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

    print(
        "ROLF AUTO FINDER запущен"
    )

    app.run_polling()


if __name__ == "__main__":
    main()

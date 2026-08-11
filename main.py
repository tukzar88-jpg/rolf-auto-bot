```python
import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from playwright.async_api import async_playwright


# =========================
# НАСТРОЙКА ЛОГОВ
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")

AVITO_URL = (
    "https://www.avito.ru/rossiya/avtomobili"
    "?pmin=1500000"
    "&distance=150000"
)


# =========================
# ПРОВЕРКА AVITO
# =========================

async def check_avito():

    browser = None

    try:

        logging.info(
            "Запускаем Playwright..."
        )

        async with async_playwright() as p:

            # Используем Chromium,
            # установленный Playwright
            logging.info(
                "Запускаем Chromium через Playwright..."
            )

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            logging.info(
                "Chromium успешно запущен!"
            )

            context = await browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 768,
                },
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            logging.info(
                "Открываем страницу Avito..."
            )

            response = await page.goto(
                AVITO_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            status = (
                response.status
                if response
                else 0
            )

            logging.info(
                f"Avito HTTP status: {status}"
            )

            # Даём странице загрузить JavaScript
            await page.wait_for_timeout(7000)

            title = await page.title()

            html = await page.content()

            try:

                text = await page.locator(
                    "body"
                ).inner_text(
                    timeout=5000
                )

            except Exception:

                text = ""

            logging.info(
                f"Avito title: {title}"
            )

            logging.info(
                f"Размер HTML: {len(html)}"
            )

            lower_text = text.lower()
            lower_html = html.lower()


            # =========================
            # ПРОВЕРКА CAPTCHA
            # =========================

            captcha_words = [
                "captcha",
                "капча",
                "проверка безопасности",
                "подтвердите, что вы не робот",
                "я не робот",
                "докажите, что вы не робот",
            ]

            captcha_found = any(
                word in lower_text
                or word in lower_html
                for word in captcha_words
            )

            if captcha_found:

                await browser.close()
                browser = None

                return (
                    "🛡 <b>Avito показал CAPTCHA</b>\n\n"
                    f"HTTP: {status}\n"
                    f"Заголовок: {title}\n"
                    f"Размер страницы: "
                    f"{len(html)} символов\n\n"
                    "❌ Браузер запустился, "
                    "но Avito заблокировал "
                    "автоматический запрос."
                )


            # =========================
            # ПОИСК ССЫЛОК НА АВТО
            # =========================

            car_links = await page.locator(
                'a[href*="/avtomobili/"]'
            ).all()

            unique_links = set()

            for link in car_links:

                try:

                    href = await link.get_attribute(
                        "href"
                    )

                    if href:
                        unique_links.add(href)

                except Exception:

                    continue


            # =========================
            # ПРОВЕРКА ПРИЗНАКОВ АВТО
            # =========================

            markers = {
                "₽": "₽" in text,
                "руб": "руб" in lower_text,
                "автомобили": (
                    "автомобил" in lower_text
                ),
                "пробег": (
                    "пробег" in lower_text
                ),
                "год": (
                    "год" in lower_text
                ),
            }

            found_markers = [
                name
                for name, exists in markers.items()
                if exists
            ]


            # =========================
            # ЕСЛИ НАШЛИ АВТО
            # =========================

            if unique_links:

                first_links = list(
                    unique_links
                )[:5]

                links_text = "\n".join(
                    first_links
                )

                await browser.close()
                browser = None

                return (
                    "✅ <b>Avito открылся!</b>\n\n"
                    f"HTTP: {status}\n"
                    f"Заголовок: {title}\n"
                    f"Найдено ссылок: "
                    f"{len(unique_links)}\n\n"
                    "🔎 Признаки объявлений:\n"
                    f"{', '.join(found_markers) "
                    f"if found_markers else 'нет'}\n\n"
                    "Первые ссылки:\n"
                    f"<code>{links_text[:2500]}</code>\n\n"
                    "🔥 Можно переходить "
                    "к разработке парсера."
                )


            # =========================
            # AVITO ОТКРЫЛСЯ,
            # НО АВТО НЕ НАЙДЕНЫ
            # =========================

            preview = " ".join(
                text[:1500].split()
            )

            await browser.close()
            browser = None

            return (
                "⚠️ <b>Avito открылся, "
                "но объявления не найдены</b>\n\n"
                f"HTTP: {status}\n"
                f"Заголовок: {title}\n"
                f"Размер HTML: {
```

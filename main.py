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
# НАСТРОЙКА ЛОГИРОВАНИЯ
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
        logging.info("Запускаем Playwright...")

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            logging.info("Chromium успешно запущен")

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

            logging.info("Открываем Avito...")

            response = await page.goto(
                AVITO_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            status = response.status if response else 0

            logging.info(
                f"Avito HTTP status: {status}"
            )

            # Ждём загрузку динамического контента
            await page.wait_for_timeout(5000)

            title = await page.title()

            html = await page.content()

            try:
                text = await page.locator(
                    "body"
                ).inner_text(timeout=5000)
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
            # CAPTCHA / БЛОКИРОВКА
            # =========================

            captcha_words = [
                "captcha",
                "капча",
                "проверка безопасности",
                "подтвердите, что вы не робот",
                "я не робот",
                "докажите, что вы не робот",
                "доступ ограничен",
                "проблема с ip",
            ]

            captcha_found = any(
                word in lower_text
                or word in lower_html
                for word in captcha_words
            )

            if status in (403, 429) or captcha_found:

                await browser.close()
                browser = None

                return (
                    "🛡 <b>Avito ограничил доступ</b>\n\n"
                    f"HTTP: {status}\n"
                    f"Заголовок: {title}\n\n"
                    "Браузер работает, но Avito "
                    "не отдаёт нормальную поисковую выдачу "
                    "этому запросу.\n\n"
                    "⏳ Бот работает. "
                    "Нужно использовать другой способ "
                    "получения объявлений."
                )

            # =========================
            # ПОИСК ССЫЛОК
            # =========================

            link_locator = page.locator(
                'a[href*="/avtomobili/"]'
            )

            try:
                await link_locator.first.wait_for(
                    state="attached",
                    timeout=10000,
                )
            except Exception:

                logging.info(
                    "Ссылки на объявления "
                    "за время ожидания не появились"
                )

            # Дополнительное ожидание
            await page.wait_for_timeout(3000)

            # =========================
            # ПОЛУЧАЕМ ССЫЛКИ
            # =========================

            unique_links = set()

            try:

                links = await link_locator.all()

                logging.info(
                    f"Найдено элементов ссылок: "
                    f"{len(links)}"
                )

                for link in links:

                    try:

                        href = await link.get_attribute(
                            "href"
                        )

                        if not href:
                            continue

                        if "/avtomobili/" not in href:
                            continue

                        # Если ссылка относительная
                        if href.startswith("/"):
                            href = (
                                "https://www.avito.ru"
                                + href
                            )

                        # Убираем параметры
                        href = href.split("?")[0]

                        unique_links.add(href)

                    except Exception:
                        continue

            except Exception as e:

                logging.exception(
                    f"Ошибка получения ссылок: {e}"
                )

            # =========================
            # ОБЪЯВЛЕНИЯ НАЙДЕНЫ
            # =========================

            if unique_links:

                first_links = list(
                    unique_links
                )[:10]

                result_lines = []

                for number, link in enumerate(
                    first_links,
                    start=1,
                ):

                    result_lines.append(
                        f"{number}. {link}"
                    )

                links_text = "\n".join(
                    result_lines
                )

                await browser.close()
                browser = None

                return (
                    "✅ <b>Объявления найдены!</b>\n\n"
                    "💰 Цена от: 1 500 000 ₽\n"
                    "🚗 Пробег: до 150 000 км\n"
                    "📍 Россия\n"
                    "📌 Источник: Avito\n\n"
                    f"🔎 Найдено ссылок: "
                    f"{len(unique_links)}\n\n"
                    "🚘 <b>Первые объявления:</b>\n\n"
                    f"{links_text[:3500]}\n\n"
                    "Следующим этапом добавим "
                    "получение цены, марки, модели, "
                    "года и пробега."
                )

            # =========================
            # ОБЪЯВЛЕНИЯ НЕ НАЙДЕНЫ
            # =========================

            preview = " ".join(
                text[:2000].split()
            )

            await browser.close()
            browser = None

            return (
                "⚠️ <b>Объявления пока не найдены</b>\n\n"
                f"HTTP: {status}\n"
                f"Заголовок: {title}\n"
                f"Размер HTML: {len(html)}\n\n"
                "Поисковая выдача не вернула "
                "подходящих ссылок Avito.\n\n"
                "Фрагмент страницы:\n"
                f"<code>{preview[:2000]}</code>"
            )

    except Exception as e:

        logging.exception(
            "Ошибка Playwright"
        )

        if browser:

            try:
                await browser.close()
            except Exception:
                pass

        return (
            "❌ <b>Ошибка Playwright</b>\n\n"
            f"<code>{str(e)[:2500]}</code>"
        )


# =========================
# /start
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🚗 <b>ROLF AUTO FINDER</b>\n\n"
        "Бесплатный тестовый режим.\n\n"
        "/monitor — проверить Avito\n"
        "/filters — показать фильтры\n"
        "/stop — остановить\n"
        "/stats — статистика",
        parse_mode="HTML",
    )


# =========================
# /monitor
# =========================

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
        disable_web_page_preview=True,
    )


# =========================
# /filters
# =========================

async def filters(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🔎 <b>Текущие фильтры:</b>\n\n"
        "💰 Цена: от 1 500 000 ₽\n"
        "🚗 Пробег: до 150 000 км\n"
        "📅 Год: без ограничений\n"
        "📍 Россия\n"
        "📌 Источник: Avito",
        parse_mode="HTML",
    )


# =========================
# /stop
# =========================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "⏹ Мониторинг остановлен."
    )


# =========================
# /stats
# =========================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "📊 Статистика пока недоступна.\n\n"
        "Сейчас бот находится "
        "в диагностическом режиме."
    )


# =========================
# ОБРАБОТКА ОШИБОК
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
# ЗАПУСК БОТА
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


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    main()

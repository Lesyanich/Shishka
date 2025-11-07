#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHOPEE ПАРСЕР v9 — ИМИТАЦИЯ ПРОКРУТКИ И КЛИКА
"""

import os, json, asyncio, re
from playwright.async_api import async_playwright

COOKIES_FILE = "shopee_cookies.json"

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'languages', { get: () => ['th-TH', 'th', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {}, app: {}, LoadTimes: () => {} };
navigator.permissions.query = () => Promise.resolve({ state: "granted" });
"""


async def save_cookies():
    print("Открываю Shopee для авторизации...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://shopee.co.th/buyer/login", wait_until="networkidle")
        print("Пожалуйста, войдите в аккаунт в открывшемся браузере.")
        print("После успешного входа (и прохождения CAPTCHA), вернитесь сюда и нажмите ENTER.")
        input()
        await context.storage_state(path=COOKIES_FILE)
        print(f"Cookie сохранены: {COOKIES_FILE}")
        await browser.close()


async def parse_shopee(url):
    if not os.path.exists(COOKIES_FILE):
        print("Нет cookie. Запусти save_cookies().")
        return "No cookie", None, "No cookie", None

    print(f"\n--- ЗАПУСК РЕЖИМА 'КЛИК + ПРОКРУТКА' ---")

    api_data = None

    async with async_playwright() as p:
        # ⬇️ Возвращаем headless=True для боевого режима
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            storage_state=COOKIES_FILE,
            locale="th-TH",
            extra_http_headers={
                "Accept-Language": "th-TH,th;q=0.9",
                "X-Shopee-Language": "th",
            }
        )
        page = await context.new_page()
        await page.add_init_script(STEALTH_SCRIPT)

        # === 1. API через intercept ===
        def handle_response(response):
            nonlocal api_data
            if "api/v4/item/get" in response.url and response.status == 200:
                # print(">>> Перехвачен API-запрос 'api/v4/item/get'!")
                asyncio.create_task(save_api_data(response))

        async def save_api_data(response):
            nonlocal api_data
            try:
                api_data = (await response.json()).get("data", {})
                # print(">>> Данные из API успешно сохранены.")
            except Exception as e:
                # print(f">>> Ошибка сохранения данных из API: {e}")
                pass

        page.on("response", handle_response)

        # === 2. Загрузка ===

        try:
            print("--- ШАГ 1: Иду на главную страницу (Прогрев + Прокрутка)... ---")
            await page.goto("https://shopee.co.th/", wait_until="load", timeout=30000)

            # ⬇️ Имитируем прокрутку вниз, чтобы выглядеть как пользователь
            await page.evaluate("window.scrollTo(0, 500);")
            await page.wait_for_timeout(3000)

            print(f"--- ШАГ 2: Переход на страницу товара (имитация ввода URL)... ---")

            # ⬇️ Имитируем переход по URL вводом в адресную строку
            # Этот метод может быть более 'человечным', чем просто page.goto

            # 1. Сначала переходим на пустую страницу
            await page.goto("about:blank", wait_until="load")

            # 2. Переходим на целевой URL, чтобы перехватчик успел сработать с начала загрузки
            response = await page.goto(url, wait_until="networkidle", timeout=30000)

            print(f"Страница товара загружена. Статус: {response.status if response else 'N/A'}")
            print(f"Финальный URL: {page.url}")

        except Exception as e:
            print(f"Ошибка при загрузке страницы: {e}")
            await browser.close()
            return "Page load error", None, str(e), None

        current_url = page.url
        if "shopee.co.th/search" in current_url or "product" not in current_url:
            print("!!! РЕДИРЕКТ. Похоже, мы не на странице товара.")
            await browser.close()
            return "Redirected", None, "Redirected", None

        # ⬇️ Ждём 5 секунд, чтобы JS гарантированно отработал
        await page.wait_for_timeout(5000)

        # === 3. API ===
        if api_data and api_data.get("itemid"):
            print("API УСПЕХ!")
            await browser.close()
            return extract_from_api(api_data)

        print("--- API-данные не были перехвачены. ---")

        # === 4. __NEXT_DATA__ ===
        print("__NEXT_DATA__ поиск...")
        next_script = await page.query_selector("script#\\__NEXT_DATA__")
        if next_script:
            try:
                json_text = await next_script.inner_text()
                data = json.loads(json_text)
                item_data = data.get("props", {}).get("pageProps", {}).get("itemData", {})
                if not item_data:
                    item_data = data.get("props", {}).get("pageProps", {}).get("item", {})

                if item_data:
                    print("__NEXT_DATA__ УСПЕХ!")
                    await browser.close()
                    return extract_from_next_data(item_data)
                else:
                    print("!!! __NEXT_DATA__ найден, но структура 'itemData' пустая.")
            except Exception as e:
                print(f"JSON ошибка в __NEXT_DATA__: {e}")
        else:
            print("!!! Скрипт __NEXT_DATA__ не найден на странице.")

        # === 5. Fallback ===
        print("Fallback...")
        html = await page.content()
        await browser.close()
        return extract_from_html(html)


# --- Функции извлечения данных без изменений ---

def extract_from_api(data):
    title = data.get("name", "No title")
    img = data.get("image")
    image = f"https://cf.shopee.co.th/file/{img}_tn" if img else None
    pmin = data.get("price_min", 0) / 100000
    pmax = data.get("price_max", 0) / 100000

    if pmin == pmax:
        price = f"THB {pmin:,.0f}"
    else:
        price = f"THB {pmin:,.0f} - THB {pmax:,.0f}"

    max_thb = round(pmax)
    return title, image, price, max_thb


def extract_from_next_data(item):
    title = item.get("name", "No title")
    images = item.get("images", [])
    image = f"https://cf.shopee.co.th/file/{images[0]}_tn" if images else None

    pmin = item.get("price_min", 0)
    pmax = item.get("price_max", pmin)

    if pmin > 1000000:
        pmin = pmin / 100000
        pmax = pmax / 100000

    if pmin == pmax:
        price = f"THB {pmin:,.0f}"
    else:
        price = f"THB {pmin:,.0f} - THB {pmax:,.0f}"

    max_thb = round(pmax)
    return title, image, price, max_thb


def extract_from_html(html):
    title_match = re.search(r'<meta property="og:title" content="([^"]+)">', html)
    title = title_match.group(1).strip() if title_match else "No title"

    img_match = re.search(r'<meta property="og:image" content="([^"]+)">', html)
    image = img_match.group(1).strip() if img_match else None

    price_data = None
    json_ld_match = re.search(r'<script type="application/ld\+json">([\s\S]+?)</script>', html)
    if json_ld_match:
        try:
            data = json.loads(json_ld_match.group(1))
            if data.get("@type") == "Product" and "offers" in data:
                offers = data["offers"]
                if isinstance(offers, list):
                    offers = offers[0]

                if "lowPrice" in offers and "highPrice" in offers:
                    pmin = float(offers["lowPrice"])
                    pmax = float(offers["highPrice"])
                    price_data = (f"THB {pmin:,.0f} - THB {pmax:,.0f}", pmax)
                elif "price" in offers:
                    p = float(offers["price"])
                    price_data = (f"THB {p:,.0f}", p)
        except:
            pass

    if price_data:
        price, max_thb = price_data
    else:
        prices = re.findall(r'฿\s*([0-9,]+)', html)
        price = " / ".join(prices[:2]) if prices else "No price found"
        max_thb = int(prices[-1].replace(',', '')) if prices else None

    return title, image, price, max_thb


# ================== MAIN ==================
async def main():
    if not os.path.exists(COOKIES_FILE):
        await save_cookies()

    test_url = "https://shopee.co.th/product/21349111/3503184814"
    title, image, price, max_thb = await parse_shopee(test_url)

    print(f"\nРЕЗУЛЬТАТ")
    print(f"Title: {title}")
    print(f"Image: {image}")
    print(f"Price: {price}")
    print(f"Max THB: {max_thb}")


if __name__ == "__main__":
    asyncio.run(main())
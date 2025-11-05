#!/usr/bin/env python3
# universal_parser.py
# Универсальный парсер: название (C), фото (I), цена (J)
# Поддержка: Alibaba, Lazada, Shopee
# Один HTTP-запрос на страницу, единая авторизация Google Sheets, логирование.

import time
import re
import logging
from urllib.parse import urlparse

import cloudscraper
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import json

# ================== НАСТРОЙКИ ==================
JSON_KEY = 'shishka-475711-43f92ff78d01.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1hLJjx5SuEna80GWOAnMGVnLtso_Y2MZvkpDfAp5fucU/edit?usp=sharing'
WORKSHEET = 'CapEx'

# Пишем в:
COL_DESCRIPTION = 3   # C
COL_IMAGE = 9         # I
COL_PRICE = 10        # J
COL_URL_INDEX = 8     # H (в row массиве индекс 7 — но для ясности: мы читаем через row[7])
THB_RATE = 33.5       # курс USD → THB, менять при необходимости

LOGFILE = 'shishka_universal.log'
REQUEST_TIMEOUT = 20
SLEEP_BETWEEN_ROWS = 1.2

# ================== ЛОГИ ==================
logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
print(f"Лог: {LOGFILE}")

# ================== ИНИЦИАЛИЗАЦИЯ SCRAPER & GOOGLE ==================
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

creds = Credentials.from_service_account_file(JSON_KEY, scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL)
ws = sheet.worksheet(WORKSHEET)
print("Таблица открыта!")

# ================== УТИЛИТЫ ==================
def safe_get(soup, selector=None, attr=None, regex=None):
    """Небольшая вспомогательная: найти селектор и вернуть атрибут или текст."""
    try:
        if selector:
            el = soup.select_one(selector)
            if not el:
                return None
            if attr:
                return el.get(attr)
            return el.get_text(strip=True)
        elif regex:
            t = soup.get_text(" ", strip=True)
            m = re.search(regex, t, re.I)
            return m.group(1) if m else None
    except Exception:
        return None

def clean_price_str(s: str):
    """Убираем лишнее из строки цены, возвращаем число если нашли."""
    if not s:
        return None
    s = s.replace('\xa0', ' ')
    # Найти число с разделителями запятая/точка
    m = re.search(r'([0-9]{1,3}(?:[,\s][0-9]{3})*(?:\.\d+)?|[0-9]+(?:\.\d+)?)', s.replace('¥', '').replace('฿',''))
    if not m:
        return None
    num = m.group(1)
    num = num.replace(' ', '').replace(',', '')
    try:
        return float(num)
    except:
        return None

def format_price_result(min_p, max_p, detected_currency):
    """Форматируем строку результата, аналогично старому формату."""
    if detected_currency == 'THB':
        usd_min = min_p / THB_RATE
        usd_max = max_p / THB_RATE
        return f"THB {min_p:,.2f} - THB {max_p:,.2f} (≈ USD {usd_min:,.0f} - USD {usd_max:,.0f})"
    else:
        thb_min = min_p * THB_RATE
        thb_max = max_p * THB_RATE
        return f"USD {min_p:,.2f} - USD {max_p:,.2f} (฿{thb_min:,.0f} - ฿{thb_max:,.0f})"

# ================== СПЕЦИФИЧНЫЕ ПАРСЕРЫ ==================
def parse_alibaba(soup, page_text):
    """
    Правила выделения для Alibaba:
    - title: meta property og:title или title тега
    - image: meta og:image, script application/ld+json -> image, или первые картинки с alicdn
    - price: искать в text видимые значения (USD/THB/$/฿)
    """
    title = None
    image = None
    price_result = None

    # Title
    title = safe_get(soup, 'meta[property="og:title"]', 'content') or safe_get(soup, 'title')

    # Image
    image = safe_get(soup, 'meta[property="og:image"]', 'content')
    if image and '?' in image:
        image = image.split('?')[0]
    if not image:
        # посмотреть в ld+json
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                data = json.loads(s.string)
                # data может быть dict или list
                if isinstance(data, dict):
                    imgs = data.get('image') or data.get('thumbnailUrl')
                    if isinstance(imgs, str):
                        image = imgs.split('?')[0]
                        break
                    if isinstance(imgs, list) and imgs:
                        image = imgs[0].split('?')[0]
                        break
            except Exception:
                continue
    if not image:
        imgs = soup.find_all('img', src=re.compile(r'alicdn\.com'))
        for im in imgs:
            src = im.get('src') or im.get('data-src') or ''
            if src:
                image = src.split('?')[0]
                break

    # Price (общая схема)
    price_texts = []
    # убрать скрипты/стили
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    # собрать куски с ключевыми словами
    for tag in soup.find_all(['span', 'div', 'meta']):
        txt = ''
        if tag.name == 'meta':
            txt = tag.get('content', '') or ''
        else:
            txt = tag.get_text(" ", strip=True)
        if re.search(r'(price|Price|THB|USD|\$|฿)', txt, re.I):
            price_texts.append(txt)
    full = ' '.join(price_texts)
    # шаблоны
    patterns = [r'(?:THB|฿)\s*([0-9,]+(?:\.\d+)?)', r'(?:USD|\$)\s*([0-9,]+(?:\.\d+)?)']
    prices = []
    for pat in patterns:
        for m in re.findall(pat, full, re.I):
            p = clean_price_str(m)
            if p and 1 < p < 1000000:
                prices.append(p)
    if prices:
        # определить валюту
        detected_currency = 'THB' if re.search(r'THB|฿', full) else 'USD'
        price_result = format_price_result(min(prices), max(prices), detected_currency)

    return title, image, price_result

def parse_lazada(soup, page_text):
    """
    Улучшенный парсер Lazada:
    - title: og:title или h1
    - image: og:image, data-image, или img с lazcdn
    - price: извлекается из JSON (window.pageData / application/ld+json) или текста
    """
    title = safe_get(soup, 'meta[property="og:title"]', 'content') or safe_get(soup, 'h1') or safe_get(soup, 'title')

    image = safe_get(soup, 'meta[property="og:image"]', 'content')
    if image and '?' in image:
        image = image.split('?')[0]
    if not image:
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                data = json.loads(s.string)
                if isinstance(data, dict):
                    imgs = data.get('image')
                    if isinstance(imgs, str):
                        image = imgs.split('?')[0]; break
                    if isinstance(imgs, list) and imgs:
                        image = imgs[0].split('?')[0]; break
            except Exception:
                continue
    if not image:
        imgs = soup.find_all('img', src=re.compile(r'laz-imgs|lazcdn|lazada', re.I))
        for im in imgs:
            src = im.get('src') or im.get('data-src') or ''
            if src:
                image = src.split('?')[0]; break

    # === PRICE ===
    price_result = None
    prices = []

    # 1. Попробуем JSON внутри <script>
    scripts = soup.find_all('script')
    for s in scripts:
        text = (s.string or '')[:40000]
        # ищем шаблоны цены
        for m in re.findall(r'"price"\s*:\s*"?([0-9,.]+)"?', text):
            v = clean_price_str(m)
            if v and 1 < v < 1000000:
                prices.append(v)
        for m in re.findall(r'"offerPrice"\s*:\s*"?([0-9,.]+)"?', text):
            v = clean_price_str(m)
            if v and 1 < v < 1000000:
                prices.append(v)
        for m in re.findall(r'"discountedPrice"\s*:\s*"?([0-9,.]+)"?', text):
            v = clean_price_str(m)
            if v and 1 < v < 1000000:
                prices.append(v)
    # 2. Fallback: видимый текст
    if not prices:
        text = soup.get_text(" ", strip=True)
        for pat in [r'(?:THB|฿)\s*([0-9,]+(?:\.\d+)?)']:
            for m in re.findall(pat, text, re.I):
                v = clean_price_str(m)
                if v:
                    prices.append(v)

    if prices:
        detected_currency = 'THB' if re.search(r'THB|฿', page_text) else 'USD'
        price_result = format_price_result(min(prices), max(prices), detected_currency)
    else:
        price_result = "No price found"

    return title, image, price_result


def parse_shopee(soup, page_text):
    """
    Правила для Shopee:
    - title: og:title или h1
    - image: og:image или картинки со shopeecdn
    - price: часто в JSON внутри <script> или в og:price:amount / og:price:currency
    """
    title = safe_get(soup, 'meta[property="og:title"]', 'content') or safe_get(soup, 'h1') or safe_get(soup, 'title')

    image = safe_get(soup, 'meta[property="og:image"]', 'content')
    if image and '?' in image:
        image = image.split('?')[0]
    if not image:
        imgs = soup.find_all('img', src=re.compile(r'shopeecdn|cf-statics|shopee', re.I))
        for im in imgs:
            src = im.get('src') or im.get('data-src') or ''
            if src:
                image = src.split('?')[0]; break

    # Try meta price
    meta_price = safe_get(soup, 'meta[property="product:price:amount"]', 'content') or safe_get(soup, 'meta[property="og:price:amount"]', 'content')
    meta_currency = safe_get(soup, 'meta[property="product:price:currency"]', 'content') or safe_get(soup, 'meta[property="og:price:currency"]', 'content')

    price_result = None
    if meta_price:
        p = clean_price_str(meta_price)
        if p:
            currency = 'THB' if meta_currency and meta_currency.upper() in ('THB','฿') else 'USD'
            price_result = format_price_result(p, p, currency)
    else:
        # Попробовать вытянуть из JSON внутри скриптов
        scripts = soup.find_all('script')
        prices = []
        for s in scripts:
            text = (s.string or '')[:20000]  # ограничить размер
            # common patterns: "price":12345 or "original_price":12345 etc
            for m in re.findall(r'["\'](?:price|original_price|price_max|price_min)["\']\s*[:]\s*([0-9]+(?:\.[0-9]+)?)', text):
                try:
                    v = float(m)
                    if 1 < v < 100000000:
                        prices.append(v)
                except:
                    continue
        # Also fallback to visible text
        if not prices:
            text = soup.get_text(" ", strip=True)
            for pat in [r'(?:THB|฿)\s*([0-9,]+(?:\.\d+)?)', r'(?:USD|\$)\s*([0-9,]+(?:\.\d+)?)']:
                for m in re.findall(pat, text, re.I):
                    v = clean_price_str(m)
                    if v:
                        prices.append(v)
        if prices:
            detected_currency = 'THB' if re.search(r'THB|฿', page_text) else 'USD'
            price_result = format_price_result(min(prices), max(prices), detected_currency)

    return title, image, price_result

# ================== ГЛАВНЫЙ УНИВЕРСАЛЬНЫЙ ПАРСЕР ==================
def parse_product(url):
    """
    1 HTTP-запрос -> BeautifulSoup -> вызов парсера по домену -> возврат (title, image_url, price_str)
    """
    if not url or not url.startswith('http'):
        return None, None, "Invalid URL"

    try:
        resp = scraper.get(url, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return None, None, f"Request error: {str(e)[:80]}"

    if resp.status_code != 200:
        return None, None, f"HTTP {resp.status_code}"

    page_text = resp.text
    soup = BeautifulSoup(page_text, 'html.parser')

    domain = urlparse(url).netloc.lower()
    # Выбираем парсер по домену
    try:
        if 'alibaba.com' in domain or '1688.com' in domain:
            title, image, price = parse_alibaba(soup, page_text)
        elif 'lazada' in domain:
            title, image, price = parse_lazada(soup, page_text)
        elif 'shopee' in domain:
            title, image, price = parse_shopee(soup, page_text)
        else:
            # Generic fallback: попробуем универсальные правила
            title = safe_get(soup, 'meta[property="og:title"]', 'content') or safe_get(soup, 'title') or safe_get(soup, 'h1')
            image = safe_get(soup, 'meta[property="og:image"]', 'content')
            if image and '?' in image:
                image = image.split('?')[0]
            # price generic
            text = soup.get_text(" ", strip=True)
            prices = []
            for pat in [r'(?:THB|฿)\s*([0-9,]+(?:\.\d+)?)', r'(?:USD|\$)\s*([0-9,]+(?:\.\d+)?)', r'([0-9,]+\.\d{2})']:
                for m in re.findall(pat, text, re.I):
                    v = clean_price_str(m)
                    if v:
                        prices.append(v)
            if prices:
                detected_currency = 'THB' if re.search(r'THB|฿', text) else 'USD'
                price = format_price_result(min(prices), max(prices), detected_currency)
            else:
                price = "No price found"
    except Exception as e:
        logging.exception("Парсер по домену упал")
        return None, None, f"Parse error: {str(e)[:80]}"

    # final clean
    if title:
        title = title.strip()
    if image and image.startswith('//'):
        image = 'https:' + image

    return title or "No title", image or "No image found", price or "No price found"

# ================== ОСНОВНОЙ ЦИКЛ ОБНОВЛЕНИЯ ТАБЛИЦЫ ==================
def main():
    rows = ws.get_all_values()
    updated = 0
    total = len(rows) - 1
    print(f"Всего строк (без заголовка): {total}")

    # Проход с 2-й строки (i = 1) — первая строка обычно заголовки
    for i in range(1, len(rows)):
        row = rows[i]
        row_number = i + 1
        try:
            url = row[7].strip() if len(row) > 7 else ''
        except Exception:
            url = ''
        if not url:
            print(f"Строка {row_number}: нет ссылки в H — пропуск")
            continue

        print(f"\nСтрока {row_number}: {url}")
        logging.info(f"Start row {row_number}: {url}")

        title, image, price = parse_product(url)
        print(f"  Title: {title}")
        print(f"  Image: {image}")
        print(f"  Price: {price}")

        # Подготовка значений для записи
        # Для изображения используем формулу =IMAGE("url") если найдено
        image_value = image
        if isinstance(image, str) and image.startswith("http"):
            image_value = f'=IMAGE("{image}")'
        # Для title и price оставляем строки

        # Записываем в три колонки: C (3), I (9), J (10)
        try:
            if title and title != "No title":
                ws.update_cell(row_number, COL_DESCRIPTION, title)
            if image_value:
                ws.update_cell(row_number, COL_IMAGE, image_value)
            if price:
                ws.update_cell(row_number, COL_PRICE, price)

            logging.info(f"Row {row_number} updated: title={'yes' if title else 'no'}, image={'yes' if image else 'no'}, price={'yes' if price else 'no'}")
            print("   Записано в таблицу")
            updated += 1
        except Exception as e:
            logging.exception(f"Ошибка записи row {row_number}")
            print(f"   Ошибка записи: {e}")

        time.sleep(SLEEP_BETWEEN_ROWS)

    print(f"\nГотово! Обновлено: {updated} строк из {total}")
    logging.info(f"Finished. Updated {updated} rows.")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Гибридный универсальный парсер Alibaba, Lazada, Shopee (v8 – ФИНАЛЬНЫЙ, 100% РАБОЧИЙ)
C = Title
I = Image
J = Price range
K = Max THB
"""

import re, time, logging, random
from urllib.parse import urlparse, parse_qs
import cloudscraper
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
import gspread

# ================== НАСТРОЙКИ ==================
JSON_KEY = 'shishka-475711-43f92ff78d01.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1hLJjx5SuEna80GWOAnMGVnLtso_Y2MZvkpDfAp5fucU/edit?usp=sharing'
WORKSHEET = 'CapEx'

COL_DESCRIPTION = 3
COL_IMAGE = 9
COL_PRICE = 10
COL_PRICE_TBH = 11
THB_RATE = 33.5

LOGFILE = 'shishka_universal.log'
SLEEP_BETWEEN_ROWS = (2, 4)
TIMEOUT = 30

# ================== ЛОГИ ==================
logging.basicConfig(filename=LOGFILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
print(f"Лог: {LOGFILE}")

# ================== GOOGLE SHEETS ==================
creds = Credentials.from_service_account_file(JSON_KEY, scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL)
ws = sheet.worksheet(WORKSHEET)
print("Таблица открыта!")

# ================== CLOUDSCRAPER ==================
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
    delay=10
)

def random_sleep(a, b):
    time.sleep(random.uniform(a, b))

# ================== УНИВЕРСАЛЬНЫЙ ПАРСИНГ (Alibaba + Shopee) ==================
def parse_alibaba_shopee(url):
    try:
        response = scraper.get(url, timeout=TIMEOUT)
        if response.status_code != 200:
            return "No title", None, f"HTTP {response.status_code}", None

        soup = BeautifulSoup(response.text, 'html.parser')

        # --- УДАЛЯЕМ СКРИПТЫ И СТИЛИ ---
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        # --- TITLE ---
        title_tag = soup.find("meta", property="og:title")
        title = title_tag["content"].strip() if title_tag else soup.title.string.strip() if soup.title else "No title"

        # --- IMAGE ---
        img_tag = soup.find("meta", property="og:image")
        image = img_tag["content"] if img_tag else None

        # --- ЦЕНЫ: только в span/div с price/THB/USD ---
        price_containers = soup.find_all(
            lambda tag: tag.name in ['span', 'div'] and
            tag.get_text(strip=True) and
            re.search(r'(price|Price|THB|USD|\$|฿)', tag.get_text(), re.I)
        )
        price_texts = [p.get_text(separator=' ', strip=True) for p in price_containers]
        full_text = ' '.join(price_texts)

        # --- ШАБЛОНЫ ---
        patterns = [
            r'(?:THB|฿)\s*([0-9,]+(?:\.\d+)?)',
            r'(?:USD|\$)\s*([0-9,]+(?:\.\d+)?)'
        ]

        prices = []
        for pattern in patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for m in matches:
                clean = m.replace(',', '')
                if re.match(r'^\d+(\.\d+)?$', clean):
                    p = float(clean)
                    if 10 < p < 100000:
                        prices.append(p)

        if not prices:
            return title, image, "No price found", None

        has_thb = bool(re.search(r'THB|฿', full_text))
        currency = 'THB' if has_thb else 'USD'
        min_p, max_p = min(prices), max(prices)

        if currency == 'THB':
            usd_min = min_p / THB_RATE
            usd_max = max_p / THB_RATE
            price_str = f"THB {min_p:,.0f} - THB {max_p:,.0f} (≈ USD {usd_min:,.0f} - USD {usd_max:,.0f})"
            max_thb = round(max_p)
        else:
            thb_min = min_p * THB_RATE
            thb_max = max_p * THB_RATE
            price_str = f"USD {min_p:,.0f} - USD {max_p:,.0f} (฿{thb_min:,.0f} - ฿{thb_max:,.0f})"
            max_thb = round(thb_max)

        return title, image, price_str, max_thb

    except Exception as e:
        logging.error(f"Parse error {url}: {e}")
        return "No title", None, f"Error: {str(e)[:50]}", None

# ================== LAZADA (ПРЕЖНЯЯ ЛОГИКА) ==================
def parse_lazada(url):
    try:
        r = scraper.get(url, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, 'html.parser')

        title = (soup.find('meta', {'property': 'og:title'}) or {}).get('content', 'No title')
        image = (soup.find('meta', {'property': 'og:image'}) or {}).get('content')

        prices = re.findall(r'(?:THB|฿)\s*([0-9,.]+)', r.text)
        nums = []
        for p in prices:
            clean = p.replace(',', '')
            if re.match(r'^\d+(\.\d+)?$', clean):
                val = float(clean)
                if 50 < val < 100000:
                    nums.append(val)

        if nums:
            pmin, pmax = min(nums), max(nums)
            usd_min = pmin / THB_RATE
            usd_max = pmax / THB_RATE
            price = f"THB {pmin:,.0f} - THB {pmax:,.0f} (≈ USD {usd_min:,.0f} - USD {usd_max:,.0f})"
            max_thb = round(pmax)
        else:
            price, max_thb = "No price found", None

        return title, image, price, max_thb
    except Exception as e:
        logging.error(f"Lazada error: {e}")
        return "No title", None, "No price found", None

# ================== SHOPEE (API + FALLBACK) ==================
def parse_shopee(url):
    # --- API ---
    m = re.search(r'/product/(\d+)/(\d+)', url)
    if m:
        shopid, itemid = m.group(1), m.group(2).split('?')[0]
    else:
        m = re.search(r'i\.(\d+)\.(\d+)', url)
        if m:
            shopid, itemid = m.group(1), m.group(2)
        else:
            return parse_alibaba_shopee(url)  # fallback

    api_url = f"https://shopee.co.th/api/v4/item/get?itemid={itemid}&shopid={shopid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": "https://shopee.co.th/",
        "X-Api-Source": "pc",
        "Af-Ac-Enc-Dat": "null"
    }
    try:
        r = scraper.get(api_url, headers=headers, timeout=TIMEOUT)
        data = r.json().get("data", {})
        if data:
            title = data.get("name", "No title")
            img = data.get("image")
            image = f"https://cf.shopee.co.th/file/{img}_tn" if img else None
            pmin = data.get("price_min", 0) / 100000
            pmax = data.get("price_max", 0) / 100000
            if pmin and pmax and pmin > 0:
                usd_min = pmin / THB_RATE
                usd_max = pmax / THB_RATE
                price = f"THB {pmin:,.0f} - THB {pmax:,.0f} (≈ USD {usd_min:,.0f} - USD {usd_max:,.0f})"
                max_thb = round(pmax)
                return title, image, price, max_thb
    except:
        pass

    # --- FALLBACK: универсальный парсер ---
    return parse_alibaba_shopee(url)

# ================== ROUTER ==================
def parse_product(url):
    netloc = urlparse(url).netloc.lower()
    if "alibaba" in netloc:
        return parse_alibaba_shopee(url)
    elif "shopee" in netloc:
        return parse_shopee(url)
    elif "lazada" in netloc:
        return parse_lazada(url)
    return "No title", None, "No price found", None

# ================== MAIN ==================
def main():
    rows = ws.get_all_values()
    total = len(rows) - 1
    print(f"Всего строк: {total}")
    updated = 0

    for i in range(1, len(rows)):
        row = rows[i]
        url = row[7].strip() if len(row) > 7 else ''
        if not url:
            print(f"Строка {i+1}: нет ссылки")
            continue

        print(f"\nСтрока {i+1}: {url}")
        title, image, price, max_thb = parse_product(url)

        print(f"  Title: {title}")
        print(f"  Image: {image}")
        print(f"  Price: {price}")
        print(f"  Max THB: {max_thb}")

        try:
            if title and title != "No title":
                ws.update_cell(i+1, COL_DESCRIPTION, title)
            if image and image.startswith('http'):
                ws.update_cell(i+1, COL_IMAGE, f'=IMAGE("{image}")')
            if price and "No price" not in price and "Error" not in price:
                ws.update_cell(i+1, COL_PRICE, price)
            if max_thb:
                ws.update_cell(i+1, COL_PRICE_TBH, max_thb)
            updated += 1
            print("  Записано")
        except Exception as e:
            print(f"  Ошибка записи: {e}")
            logging.error(f"Row {i+1}: {e}")

        random_sleep(*SLEEP_BETWEEN_ROWS)

    print(f"\nГотово! Обновлено: {updated} строк")

if __name__ == "__main__":
    main()
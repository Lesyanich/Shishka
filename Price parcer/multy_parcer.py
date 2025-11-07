#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alibaba + Lazada parser (antiban edition)
C = Title
I = Image
J = Price range
K = Max THB
"""

import re, time, logging, random
from urllib.parse import urlparse
import cloudscraper
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
import gspread
from http import HTTPStatus

# ================== НАСТРОЙКИ ==================
JSON_KEY = 'shishka-475711-43f92ff78d01.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1hLJjx5SuEna80GWOAnMGVnLtso_Y2MZvkpDfAp5fucU/edit?usp=sharing'
WORKSHEET = 'CapEx'

COL_DESCRIPTION = 3
COL_IMAGE = 9
COL_PRICE = 10
COL_PRICE_TBH = 11
THB_RATE = 33.5

LOGFILE = 'shishka_universal_antiban.log'
SLEEP_BETWEEN_ROWS = (4, 8)
TIMEOUT = 40
MAX_RETRIES = 3
PAUSE_EVERY_N = 5

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

# ================== ДАННЫЕ ДЛЯ АНТИ-БАНА ==================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
]
LANGS = ["en-US,en;q=0.9", "th-TH,th;q=0.9,en;q=0.8", "en-GB,en;q=0.9"]
REFS = ["https://google.com/", "https://www.alibaba.com/", "https://bing.com/"]

# ================== CLOUDSCRAPER ==================
def new_scraper():
    ua = random.choice(USER_AGENTS)
    s = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
        delay=random.randint(5, 15)
    )
    s.headers.update({
        "User-Agent": ua,
        "Accept-Language": random.choice(LANGS),
        "Referer": random.choice(REFS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    })
    return s

scraper = new_scraper()

def random_sleep(a, b):
    time.sleep(random.uniform(a, b))

# ================== АНТИ-БАН ПАРСЕР ALIBABA ==================
def parse_alibaba(url):
    global scraper
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = scraper.get(url, timeout=TIMEOUT)
            if response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS, 430, 503):
                print(f"⚠️ Alibaba: подозрение на бота (HTTP {response.status_code}), попытка {attempt}")
                logging.warning(f"Retry {attempt} for {url}: {response.status_code}")
                time.sleep(5 * attempt + random.uniform(1, 3))
                scraper = new_scraper()  # новый клиент
                continue

            if response.status_code != 200:
                return "No title", None, f"HTTP {response.status_code}", None

            soup = BeautifulSoup(response.text, 'html.parser')

            # --- очистка ---
            for tag in soup(['script', 'style', 'noscript']):
                tag.decompose()

            # --- TITLE ---
            title_tag = soup.find("meta", property="og:title")
            title = title_tag["content"].strip() if title_tag else soup.title.string.strip() if soup.title else "No title"

            # --- IMAGE ---
            img_tag = soup.find("meta", property="og:image")
            image = img_tag["content"] if img_tag else None

            # --- ЦЕНЫ ---
            text = soup.get_text(separator=' ')
            prices = re.findall(r'(?:USD|\$)\s?([0-9,.]+)', text)
            prices = [float(p.replace(',', '')) for p in prices if p.replace(',', '').isdigit()]

            if not prices:
                return title, image, "No price found", None

            pmin, pmax = min(prices), max(prices)
            thb_min = pmin * THB_RATE
            thb_max = pmax * THB_RATE
            price_str = f"USD {pmin:,.0f} - USD {pmax:,.0f} (฿{thb_min:,.0f} - ฿{thb_max:,.0f})"
            max_thb = round(thb_max)

            return title, image, price_str, max_thb

        except Exception as e:
            print(f"⚠️ Ошибка попытки {attempt}: {e}")
            logging.error(f"Parse error {url}: {e}")
            time.sleep(3 * attempt)
            scraper = new_scraper()

    return "No title", None, "Error after retries", None

# ================== LAZADA ==================
def parse_lazada(url):
    try:
        r = scraper.get(url, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = (soup.find('meta', {'property': 'og:title'}) or {}).get('content', 'No title')
        image = (soup.find('meta', {'property': 'og:image'}) or {}).get('content')

        prices = re.findall(r'(?:THB|฿)\s*([0-9,.]+)', r.text)
        nums = [float(p.replace(',', '')) for p in prices if re.match(r'^\d+(\.\d+)?$', p.replace(',', ''))]
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

# ================== ROUTER ==================
def parse_product(url):
    netloc = urlparse(url).netloc.lower()
    if "alibaba" in netloc:
        return parse_alibaba(url)
    elif "lazada" in netloc:
        return parse_lazada(url)
    else:
        print(f"  Пропущено (не Alibaba/Lazada): {url}")
        return "Skipped", None, "Not supported", None

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
            continue

        print(f"\nСтрока {i+1}: {url}")
        title, image, price, max_thb = parse_product(url)

        if title == "Skipped":
            continue

        print(f"  Title: {title}\n  Price: {price}\n  Max THB: {max_thb}")

        try:
            if title and title != "No title":
                ws.update_cell(i+1, COL_DESCRIPTION, title)
            if image and image.startswith('http'):
                ws.update_cell(i+1, COL_IMAGE, f'=IMAGE("{image}")')
            if price and "No price" not in price:
                ws.update_cell(i+1, COL_PRICE, price)
            if max_thb:
                ws.update_cell(i+1, COL_PRICE_TBH, max_thb)
            updated += 1
            print("  ✅ Записано")
        except Exception as e:
            print(f"  ⚠️ Ошибка записи: {e}")
            logging.error(f"Row {i+1}: {e}")

        if i % PAUSE_EVERY_N == 0:
            print("🕓 Пауза между пакетами...")
            time.sleep(random.uniform(20, 40))
        else:
            random_sleep(*SLEEP_BETWEEN_ROWS)

    print(f"\nГотово! Обновлено: {updated} строк")

if __name__ == "__main__":
    main()

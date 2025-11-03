import gspread
from google.oauth2.service_account import Credentials
import cloudscraper
from bs4 import BeautifulSoup
import re
import time
import logging

# === ЛОГИ ===
logging.basicConfig(filename='shishka_prices.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')
print("Лог: shishka_prices.log")

# === НАСТРОЙКИ ===
JSON_KEY = 'shishka-475711-43f92ff78d01.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1hLJjx5SuEna80GWOAnMGVnLtso_Y2MZvkpDfAp5fucU/edit?usp=sharing'
WORKSHEET = 'CapEx'
THB_RATE = 33.5  # USD → THB

# === CLOUDSCRAPER (обходит Cloudflare) ===
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

# === АВТОРИЗАЦИЯ ===
creds = Credentials.from_service_account_file(JSON_KEY, scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL)
ws = sheet.worksheet(WORKSHEET)
print("Таблица открыта!")


# === ПАРСИНГ ЦЕНЫ (Cloudscraper + Regex) ===
def parse_price(url):
    if not url.startswith('http'):
        return "Invalid URL"

    try:
        response = scraper.get(url, timeout=20)
        if response.status_code != 200:
            return f"HTTP {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()

        # Ищем элементы с классами цены
        price_elements = soup.find_all(class_=re.compile(r'price|Price|amount|range', re.I))
        price_text = ' '.join([el.get_text() for el in price_elements])

        # Все паттерны
        patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*-\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',
            r'[\$฿]\s*([0-9,]+\.?[0-9]*)',
            r'([0-9,]+\.?[0-9]*)\s*(?:USD|THB|Dollar|Baht)',
            r'price[^\d]*([0-9,]+\.?[0-9]*)'
        ]

        prices = []
        for pattern in patterns:
            matches = re.findall(pattern, text + ' ' + price_text)
            for m in matches:
                if isinstance(m, tuple):
                    for val in m:
                        clean = re.sub(r'[^\d.]', '', val)
                        if clean and 50 <= float(clean) <= 10000:
                            prices.append(float(clean))
                else:
                    clean = re.sub(r'[^\d.]', '', m)
                    if clean and 50 <= float(clean) <= 10000:
                        prices.append(float(clean))

        if not prices:
            return "No price found"

        min_p, max_p = min(prices), max(prices)
        currency = 'USD' if any(x in text.upper() for x in ['USD', '$']) else '฿'

        thb_min = min_p * THB_RATE
        thb_max = max_p * THB_RATE

        result = f"{currency} {min_p:,.0f}"
        if min_p != max_p:
            result += f" - {currency} {max_p:,.0f}"
        result += f" (฿{thb_min:,.0f} - ฿{thb_max:,.0f})"

        return result

    except Exception as e:
        return f"Error: {str(e)[:40]}"


# === ОСНОВНОЙ ЦИКЛ ===
rows = ws.get_all_values()
updated = 0

for i in range(1, len(rows)):
    row = rows[i]
    if len(row) > 7 and row[7].strip():
        url = row[7].strip()
        print(f"\nСтрока {i + 1}: {url}")
        price = parse_price(url)
        print(f"   → {price}")

        try:
            ws.update_cell(i + 1, 10, price)
            print("   Записано в J")
            logging.info(f"Row {i + 1}: {url} → {price}")
            updated += 1
        except Exception as e:
            print(f"   Запись ошибка: {e}")

        time.sleep(1.5)
    else:
        print(f"Строка {i + 1}: нет ссылки")

print(f"\nГотово! Обновлено: {updated} строк")
print("Проверь J и лог!")
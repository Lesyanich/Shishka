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
THB_RATE = 33.5  # курс USD → THB

# === CLOUDSCRAPER ===
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


# === ФУНКЦИЯ ПАРСИНГА ЦЕНЫ ===
def parse_price(url):
    if not url.startswith('http'):
        return "Invalid URL"

    try:
        response = scraper.get(url, timeout=20)
        if response.status_code != 200:
            return f"HTTP {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')

        # --- удаляем скрипты и стили (в них часто мусорные JSON-цены) ---
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        # --- ищем только реальные элементы с ценами ---
        price_containers = soup.find_all(
            lambda tag: tag.name in ['span', 'div'] and
            tag.get_text(strip=True) and
            re.search(r'(price|Price|THB|USD|\$|฿)', tag.get_text(), re.I)
        )

        price_texts = [p.get_text(separator=' ', strip=True) for p in price_containers]
        full_text = ' '.join(price_texts)

        # --- шаблоны для видимых цен ---
        patterns = [
            r'(?:THB|฿)\s*([0-9,]+(?:\.\d+)?)',  # THB 8,090.87
            r'(?:USD|\$)\s*([0-9,]+(?:\.\d+)?)'   # USD 240 или $240
        ]

        prices = []
        for pattern in patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for m in matches:
                clean = m.replace(',', '')
                if re.match(r'^\d+(\.\d+)?$', clean):
                    p = float(clean)
                    if 10 < p < 100000:  # фильтр: убираем нули, мусор и SKU-номера
                        prices.append(p)

        if not prices:
            return "No price found"

        has_thb = bool(re.search(r'THB|฿', full_text))
        has_usd = bool(re.search(r'USD|\$', full_text))
        currency = 'THB' if has_thb else 'USD'

        min_p, max_p = min(prices), max(prices)

        # --- расчёт и формат ---
        if currency == 'THB':
            usd_min = min_p / THB_RATE
            usd_max = max_p / THB_RATE
            result = f"THB {min_p:,.2f} - THB {max_p:,.2f} (≈ USD {usd_min:,.0f} - USD {usd_max:,.0f})"
        else:
            thb_min = min_p * THB_RATE
            thb_max = max_p * THB_RATE
            result = f"USD {min_p:,.2f} - USD {max_p:,.2f} (฿{thb_min:,.0f} - ฿{thb_max:,.0f})"

        return result

    except Exception as e:
        return f"Error: {str(e)[:60]}"


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

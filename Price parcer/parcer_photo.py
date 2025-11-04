import gspread
from google.oauth2.service_account import Credentials
import cloudscraper
from bs4 import BeautifulSoup
import re
import time
import logging

# === ЛОГИ ===
logging.basicConfig(filename='shishka_images.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')
print("Лог: shishka_images.log")

# === НАСТРОЙКИ ===
JSON_KEY = 'shishka-475711-43f92ff78d01.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1hLJjx5SuEna80GWOAnMGVnLtso_Y2MZvkpDfAp5fucU/edit?usp=sharing'
WORKSHEET = 'CapEx'

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


# === ПАРСИНГ ГЛАВНОГО ФОТО ===
def get_main_image_url(url):
    if not url.startswith('http'):
        return "Invalid URL"

    try:
        response = scraper.get(url, timeout=20)
        if response.status_code != 200:
            return f"HTTP {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Ищем в meta property="og:image"
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img = og_image["content"]
            if "alicdn.com" in img:
                return img.split("?")[0]  # Убираем параметры

        # 2. Ищем в JSON-данных (Alibaba часто прячет в script)
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            if "image" in script.text:
                match = re.search(r'"image"\s*:\s*"([^"]+\.jpg)', script.text)
                if match:
                    return match.group(1)

        # 3. Ищем первое большое изображение
        images = soup.find_all("img", src=re.compile(r'alicdn\.com.*\.jpg'))
        for img in images:
            src = img.get("src") or img.get("data-src")
            if src and "800x800" in src or "600x600" in src:
                return src.split("?")[0]

        # 4. Fallback: первое изображение с alicdn
        for img in images:
            src = img.get("src") or img.get("data-src")
            if src and "alicdn.com" in src:
                return src.split("?")[0]

        return "No image found"

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

        img_url = get_main_image_url(url)
        formula = f'=IMAGE("{img_url}")' if img_url.startswith("http") else img_url

        print(f"   → {formula}")

        try:
            ws.update_cell(i + 1, 9, formula)  # I = 9
            print("   Записано в I")
            logging.info(f"Row {i + 1}: {url} → {formula}")
            updated += 1
        except Exception as e:
            print(f"   Запись ошибка: {e}")

        time.sleep(1.2)
    else:
        print(f"Строка {i + 1}: нет ссылки")

print(f"\nГотово! Обновлено фото: {updated} строк")
print("Проверь столбец I — изображения появятся через 3–5 сек!")
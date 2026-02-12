import os
import requests
from pathlib import Path
import time
from dotenv import load_dotenv

# --- ИНИЦИАЛИЗАЦИЯ СЕКРЕТОВ ---
# Мы загружаем данные из .env, чтобы не «светить» ключи в коде
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# Путь к папке с обложками
COVERS_DIR = Path("/Users/lesianich/Shishka/Book_organizer/Books/converted_pdf/Covers")

# Проверка, что всё на месте
if not all([NOTION_TOKEN, DATABASE_ID, IMGBB_API_KEY]):
    print("❌ Ошибка: Проверьте файл .env! Не найдены токены или ID базы.")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}


def upload_to_imgbb(image_path):
    """Загрузка картинки и получение прямой ссылки."""
    try:
        with open(image_path, "rb") as file:
            url = "https://api.imgbb.com/1/upload"
            payload = {"key": IMGBB_API_KEY}
            files = {"image": file}
            res = requests.post(url, payload, files=files, timeout=10)
            if res.status_code == 200:
                return res.json()["data"]["url"]
    except Exception as e:
        print(f"  ❌ Ошибка ImgBB при загрузке {image_path.name}: {e}")
    return None


def get_all_notion_pages():
    """Сбор всех страниц из Notion с учетом пагинации (более 100 штук)."""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    pages = []
    has_more = True
    start_cursor = None

    print("🔍 Синхронизация списка книг из Notion...")
    while has_more:
        payload = {"start_cursor": start_cursor} if start_cursor else {}
        res = requests.post(url, headers=HEADERS, json=payload)
        if res.status_code != 200:
            print(f"❌ Ошибка Notion API: {res.text}")
            break
        data = res.json()
        pages.extend(data.get("results", []))
        has_more = data.get("has_more")
        start_cursor = data.get("next_cursor")
    return pages


def sync_missing_covers():
    pages = get_all_notion_pages()
    print(f"✅ База загружена. Всего в Notion: {len(pages)} строк.")

    updated_count = 0
    skipped_count = 0

    for page in pages:
        props = page["properties"]
        page_id = page["id"]

        # 1. Проверка: есть ли уже обложка в шапке или в поле Cover?
        has_system_cover = page.get("cover") is not None
        cover_prop_files = props.get("Cover", {}).get("files", [])
        has_property_cover = len(cover_prop_files) > 0

        if has_system_cover and has_property_cover:
            skipped_count += 1
            continue

        # 2. Извлекаем book_id (B001, B002...).
        # Проверяем и тип 'title' (если это имя страницы), и 'rich_text' (если это колонка)
        book_id = ""
        bid_prop = props.get("book_id", {})

        prop_type = bid_prop.get("type")
        if prop_type == "title":
            texts = bid_prop.get("title", [])
            if texts: book_id = texts[0]["plain_text"].strip()
        elif prop_type == "rich_text":
            texts = bid_prop.get("rich_text", [])
            if texts: book_id = texts[0]["plain_text"].strip()

        if not book_id:
            continue

        # 3. Ищем файл B001.jpg
        img_path = COVERS_DIR / f"{book_id}.jpg"

        if img_path.exists():
            print(f"🔄 Обработка {book_id}...")
            public_url = upload_to_imgbb(img_path)

            if public_url:
                update_url = f"https://api.notion.com/v1/pages/{page_id}"
                update_data = {
                    "cover": {"type": "external", "external": {"url": public_url}},
                    "properties": {
                        "Cover": {
                            "files": [
                                {"name": f"Cover_{book_id}.jpg", "type": "external", "external": {"url": public_url}}]
                        }
                    }
                }
                requests.patch(update_url, headers=HEADERS, json=update_data)
                updated_count += 1
                print(f"  ✅ Готово!")

            time.sleep(0.3)  # Защита от спама API
        else:
            # Если файла нет, просто молча идем дальше
            pass

    print(f"\n✨ Результат:")
    print(f"📊 Добавлено новых обложек: {updated_count}")
    print(f"⏩ Уже были в порядке: {skipped_count}")


if __name__ == "__main__":
    sync_missing_covers()
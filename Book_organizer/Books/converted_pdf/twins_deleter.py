import os
import csv
from pathlib import Path


def clean_filename_logic(filename):
    """Очищает имя файла от мусора для таблицы."""
    name = filename.stem
    # 1. Заменяем подчеркивания на пробелы
    name = name.replace('_', ' ')
    # 2. Убираем специфический мусор
    garbage = ["libgen li", "Optimized", "33", "39", "226", "233"]
    for word in garbage:
        name = name.replace(word, "")

    # Пытаемся разделить автора и название (часто автор в конце или начале)
    # Это упрощенная логика, которую можно подправить в CSV
    parts = name.split('  ')  # ищем двойные пробелы после чистки
    return name.strip()


def finalize_library(books_dir: Path):
    output_dir = books_dir  # работаем в той же папке
    csv_data = []

    # 1. Сначала удаляем те самые 8 дублей (уже без Dry Run)
    trash_patterns = ["_epub.pdf", " (1).pdf", "-2.pdf", "_OceanofPDF.com_"]

    print("🧹 Шаг 1: Удаление дубликатов...")
    for file in list(books_dir.glob("*.pdf")):
        if any(pat in file.name for pat in trash_patterns):
            print(f"🗑 Удалено: {file.name}")
            file.unlink()

    # 2. Переименование и подготовка данных для DB_Library
    print("\n🏷 Шаг 2: Чистка названий и подготовка базы...")

    remaining_files = sorted(list(books_dir.glob("*.pdf")))

    for i, file in enumerate(remaining_files, 1):
        old_name = file.name
        # Генерируем ID как в вашей структуре: B001, B002...
        book_id = f"B{i:03d}"

        # Чистим имя для нового названия файла
        clean_name = file.stem.replace('_', ' ').replace('  ', ' ').strip()
        new_filename = f"{book_id} - {clean_name}.pdf"

        # Путь к новому файлу
        new_file_path = books_dir / new_filename

        # Данные для CSV (DB_Library)
        csv_data.append({
            "book_id": book_id,
            "title": clean_name,
            "author": "Check Source",  # Автора проще подправить в таблице
            "content_type": "PDF",
            "main_category": "",  # Заполните на основе REF_Taxonomy
            "filename": new_filename
        })

        # Переименовываем физически
        file.rename(new_file_path)
        print(f"✅ {book_id}: {old_name} -> {new_filename}")

    # 3. Создаем CSV для импорта в Google Sheets
    csv_file = books_dir / "import_to_db_library.csv"
    with open(csv_file, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\n✨ Готово! Файл для импорта в таблицу создан: {csv_file}")


if __name__ == "__main__":
    path = Path("/Users/lesianich/Shishka/Book_organizer/Books/converted_pdf")
    finalize_library(path)
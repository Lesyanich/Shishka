from pathlib import Path
import shutil


def consolidate_pdfs(base_dir: Path):
    # Папка, куда всё перемещаем
    destination_dir = base_dir / "converted_pdf"

    # Создаем её, если вдруг она ещё не существует
    destination_dir.mkdir(exist_ok=True)

    # Ищем все PDF файлы ТОЛЬКО в корне Books (не заходя в converted_pdf)
    # Используем glob("*.pdf"), так как rglob залезет и во вложенные папки
    pdf_files = [f for f in base_dir.glob("*.pdf") if f.is_file()]

    if not pdf_files:
        print("ℹ️  PDF файлы для перемещения не найдены.")
        return

    print(f"📦 Найдено {len(pdf_files)} PDF файлов. Начинаю перемещение...")

    moved_count = 0
    for pdf in pdf_files:
        target_path = destination_dir / pdf.name

        # Проверка на дубликаты
        if target_path.exists():
            print(f"⏩ Пропуск: {pdf.name} уже находится в целевой папке.")
            continue

        try:
            # Перемещение (move)
            shutil.move(str(pdf), str(target_path))
            print(f"✅ Перемещено: {pdf.name}")
            moved_count += 1
        except Exception as e:
            print(f"💥 Ошибка при перемещении {pdf.name}: {e}")

    print(f"\n✨ Готово! Перемещено файлов: {moved_count}")


if __name__ == "__main__":
    # Ваш путь
    books_path = Path("/Users/lesianich/Shishka/Book_organizer/Books")
    consolidate_pdfs(books_path)
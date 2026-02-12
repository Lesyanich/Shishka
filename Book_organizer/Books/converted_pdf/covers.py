import fitz  # PyMuPDF
from pathlib import Path


def extract_covers():
    # Пути
    base_path = Path("/Users/lesianich/Shishka/Book_organizer/Books/converted_pdf")
    covers_path = base_path / "Covers"
    covers_path.mkdir(exist_ok=True)

    # Список всех PDF
    books = list(base_path.glob("*.pdf"))
    print(f"📸 Найдено книг для обработки: {len(books)}")

    for book in books:
        # Пропускаем папку Covers и саму папку
        if "Covers" in str(book) or book.is_dir(): continue

        # Берем ID из начала имени: "B001 - Title.pdf" -> "B001"
        book_id = book.name.split(' - ')[0] if ' - ' in book.name else book.stem
        output_file = covers_path / f"{book_id}.jpg"

        if output_file.exists():
            continue

        try:
            doc = fitz.open(book)
            if len(doc) > 0:
                page = doc[0]  # Обложка всегда на 1-й странице
                # Качество 1.5x достаточно для превью в Notion
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                pix.save(str(output_file))
                print(f"✅ Готово: {book_id}")
            doc.close()
        except Exception as e:
            print(f"❌ Ошибка в {book.name}: {e}")


if __name__ == "__main__":
    extract_covers()
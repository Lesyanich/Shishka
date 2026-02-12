## запуск с терминала лучше

import sys
import shutil
from pathlib import Path

# Импортируем функцию 'run' под уникальным псевдонимом 'execute_cmd'
# Это гарантирует, что даже если в системе есть другой 'subprocess', мы не запутаемся
try:
    from subprocess import run as execute_cmd
except ImportError:
    # Запасной вариант для странных конфигураций окружения
    import subprocess

    execute_cmd = subprocess.run


def get_converter_path():
    """Ищет путь к исполняемому файлу Calibre."""
    cmd = shutil.which("ebook-convert")
    if cmd:
        return cmd
    mac_path = Path("/Applications/calibre.app/Contents/MacOS/ebook-convert")
    return str(mac_path) if mac_path.exists() else None


def convert_epub_to_pdf(books_dir: Path):
    converter = get_converter_path()

    if not converter:
        print("❌ Calibre не найден. Установите его и попробуйте снова.")
        return

    output_dir = books_dir / "converted_pdf"
    output_dir.mkdir(exist_ok=True)

    epubs = list(books_dir.glob("*.epub"))
    if not epubs:
        print(f"ℹ️  В папке {books_dir} нет .epub файлов.")
        return

    print(f"🚀 Найдено {len(epubs)} книг. Работаю...")

    for src in epubs:
        dst = output_dir / f"{src.stem}.pdf"

        if dst.exists():
            print(f"⏩ Пропуск: {dst.name}")
            continue

        print(f"🔄 Конвертирую: {src.name}...")

        try:
            # Используем наш псевдоним execute_cmd вместо subprocess.run
            result = execute_cmd(
                [converter, str(src), str(dst)],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                print(f"✅ Готово: {dst.name}")
            else:
                # Выводим ошибку, если Calibre не смог обработать файл
                short_err = result.stderr[:200].replace('\n', ' ')
                print(f"⚠️ Ошибка Calibre: {short_err}")

        except Exception as e:
            print(f"💥 Сбой скрипта: {e}")


if __name__ == "__main__":
    books_path = Path("/Users/lesianich/Shishka/Book_organizer/Books")
    convert_epub_to_pdf(books_path)
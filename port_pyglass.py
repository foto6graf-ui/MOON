from pathlib import Path


PROJECT_DIR = Path(__file__).parent
PYGLASS_DIR = PROJECT_DIR / "pyglass_pyside"


def convert_file(file_path: Path) -> None:
    """Конвертирует PyQt6 импорты в PySide6."""

    text = file_path.read_text(
        encoding="utf-8"
    )

    original_text = text

    # Основная замена Qt binding
    text = text.replace(
        "PyQt6",
        "PySide6"
    )

    # Сигналы PyQt6 -> PySide6
    text = text.replace(
        "pyqtSignal",
        "Signal"
    )

    text = text.replace(
        "pyqtSlot",
        "Slot"
    )

    text = text.replace(
        "pyqtProperty",
        "Property"
    )

    if text != original_text:

        file_path.write_text(
            text,
            encoding="utf-8"
        )

        print(
            f"[OK] {file_path.name}"
        )

    else:

        print(
            f"[SKIP] {file_path.name}"
        )


def main():

    print()
    print("=" * 50)
    print("PYGLASS -> PYSIDE6 CONVERTER")
    print("=" * 50)
    print()

    if not PYGLASS_DIR.exists():

        print("ОШИБКА!")
        print("Папка не найдена:")

        print(PYGLASS_DIR)

        return

    files = list(
        PYGLASS_DIR.glob("*.py")
    )

    print(
        f"Найдено файлов: {len(files)}"
    )

    print()

    for file_path in files:

        # demo.py нам пока не нужен
        # desktop.py тоже пока не нужен

        if file_path.name in (
            "demo.py",
            "desktop.py",
        ):
            print(
                f"[SKIP] {file_path.name}"
            )
            continue

        convert_file(
            file_path
        )

    print()
    print("=" * 50)
    print("ГОТОВО")
    print("=" * 50)
    print()

    print(
        "PyGlass сконвертирован "
        "для PySide6."
    )


if __name__ == "__main__":
    main()
import logging
import os
from pathlib import Path

SOURCE_DIR = Path(".")  # Корень проекта
DEST_DIR = Path("codex_dump")
MAX_LINES_PER_FILE = 10_000
INCLUDE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".json", ".html", ".css", ".env", ".txt", ".md", ".ini", ".toml", ".yml", ".yaml"
}
EXCLUDE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", "node_modules",
    ".mypy_cache", ".pytest_cache", ".venv", "venv", "dist", "build", ".coverage"
}

logger = logging.getLogger(__name__)

def should_include_file(path: Path) -> bool:
    return path.suffix in INCLUDE_EXTENSIONS

def add_file_header(rel_path: Path, lines: list[str]):
    return [f"# {rel_path}\n"] + lines + ["\n\n"]

def add_empty_folder_notice(rel_path: Path):
    return [f"# {rel_path}/ (empty directory)\n\n"]


def main() -> None:
    all_chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_line_count = 0

    for dirpath, dirnames, filenames in os.walk(SOURCE_DIR):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        rel_dir = Path(dirpath).relative_to(SOURCE_DIR)

        # пустая директория
        if not filenames and not dirnames:
            current_chunk += add_empty_folder_notice(rel_dir)
            current_line_count += 2

        for fname in filenames:
            path = Path(dirpath) / fname
            rel_path = path.relative_to(SOURCE_DIR)

            if rel_path.parts[0] in EXCLUDE_DIRS or not should_include_file(path):
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    file_lines = f.readlines()
            except Exception:
                file_lines = ["# (unable to read file)\n"]

            file_block = add_file_header(rel_path, file_lines)

            if current_line_count + len(file_block) > MAX_LINES_PER_FILE:
                all_chunks.append(current_chunk)
                current_chunk = []
                current_line_count = 0

            current_chunk += file_block
            current_line_count += len(file_block)

    # Добавляем последний кусок
    if current_chunk:
        all_chunks.append(current_chunk)

    # Создание выходной директории и сохранение
    DEST_DIR.mkdir(exist_ok=True)
    for i, chunk in enumerate(all_chunks, 1):
        out_file = DEST_DIR / f"project_dump_part{i}.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.writelines(chunk)

    logger.info("\n✅ Сохранил %d файл(ов) в папке %s", len(all_chunks), DEST_DIR)


if __name__ == "__main__":
    main()

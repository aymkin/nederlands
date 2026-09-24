#!/usr/bin/env python3
"""
Shared Anki utilities for audio_to_anki.py and text_to_speech.py.

Functions for finding Anki profiles, validating media folders,
copying audio files into Anki's collection.media directory, and importing
an _anki.txt TSV straight into the running Anki via AnkiConnect.

    python3 scripts/anki_utils.py import FILE_anki.txt
"""

import json
import shutil
import sys
import urllib.request
from pathlib import Path

# Базовые пути к Anki2 (кроссплатформенно)
ANKI_BASE_PATHS = [
    Path.home() / "Library/Application Support/Anki2",  # macOS
    Path.home() / ".local/share/Anki2",  # Linux
    Path.home() / "AppData/Roaming/Anki2",  # Windows
]

# Системные папки Anki (не профили)
ANKI_SYSTEM_DIRS = {"addons21", "logs", "crash_reports"}


def find_anki_profiles(base_path: Path) -> list[Path]:
    """Находит все профили пользователей в директории Anki2."""
    profiles = []

    if not base_path.exists():
        return profiles

    for item in base_path.iterdir():
        # Пропускаем системные папки и файлы
        if not item.is_dir() or item.name in ANKI_SYSTEM_DIRS:
            continue

        # Профиль — это папка с collection.media внутри
        media_dir = item / "collection.media"
        if media_dir.exists():
            profiles.append(media_dir)

    return profiles


def find_anki_media_folder() -> Path | None:
    """
    Ищет Anki media folder на текущей машине.
    Если профиль один — использует его автоматически.
    """
    for base_path in ANKI_BASE_PATHS:
        profiles = find_anki_profiles(base_path)

        if len(profiles) == 1:
            # Один профиль — используем его
            return profiles[0]
        elif len(profiles) > 1:
            # Несколько профилей — используем первый, но предупреждаем
            print(f"   ⚠️  Найдено {len(profiles)} профилей, использую: {profiles[0].parent.name}")
            return profiles[0]

    return None


def validate_anki_media(media_path: Path | None) -> Path | None:
    """Валидирует путь к Anki media folder."""
    if media_path is None:
        return None

    if not media_path.exists():
        return None

    if not media_path.is_dir():
        return None

    # Проверяем что это похоже на Anki media (можно писать файлы)
    try:
        test_file = media_path / ".write_test"
        test_file.touch()
        test_file.unlink()
        return media_path
    except PermissionError:
        return None


def copy_to_anki_media(source_dir: Path, media_path: Path, prefix: str) -> int:
    """Копирует аудио файлы в Anki media folder."""
    copied = 0
    for audio_file in source_dir.glob("*.mp3"):
        # Файлы уже имеют префикс: h07_oefening_02_sentence_001.mp3
        dest_file = media_path / audio_file.name
        shutil.copy2(audio_file, dest_file)
        copied += 1
    return copied


ANKICONNECT = "http://127.0.0.1:8765"


def ankiconnect(action: str, **params):
    """Вызов AnkiConnect; Anki должен быть запущен с этим аддоном."""
    body = json.dumps({"action": action, "version": 6, "params": params}).encode()
    with urllib.request.urlopen(ANKICONNECT, body, timeout=10) as r:
        reply = json.load(r)
    if reply["error"]:
        raise RuntimeError(f"AnkiConnect {action}: {reply['error']}")
    return reply["result"]


def import_tsv(path: Path) -> tuple[int, list[str]]:
    """Импорт _anki.txt по его директивам #notetype / #deck / #columns /
    #tags column. Дубли (первое поле уже есть у этого note type) пропускаются —
    так повторный импорт безопасен. Возвращает (добавлено, пропущенные)."""
    head, rows = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            key, _, val = line[1:].partition(":")
            head[key] = val
        elif line.strip():
            rows.append(line.split("\t"))
    columns = head["columns"].split("\t")
    tags_col = int(head["tags column"]) - 1
    ankiconnect("createDeck", deck=head["deck"])
    notes = [
        {
            "deckName": head["deck"],
            "modelName": head["notetype"],
            "fields": {c: r[i] for i, c in enumerate(columns) if i != tags_col},
            "tags": r[tags_col].split(),
        }
        for r in rows
    ]
    ok = ankiconnect("canAddNotesWithErrorDetail", notes=notes)
    fresh = [n for n, o in zip(notes, ok) if o["canAdd"]]
    skipped = [n["fields"][columns[0]] for n, o in zip(notes, ok) if not o["canAdd"]]
    if fresh:
        ankiconnect("addNotes", notes=fresh)
    return len(fresh), skipped


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "import":
        sys.exit("usage: anki_utils.py import FILE_anki.txt")
    added, skipped = import_tsv(Path(sys.argv[2]))
    print(f"✅ добавлено {added}" + (f", уже были: {', '.join(skipped)}" if skipped else ""))

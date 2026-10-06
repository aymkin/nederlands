#!/usr/bin/env python3
"""
Shared Anki utilities for audio_to_anki.py and text_to_speech.py.

Functions for finding Anki profiles, validating media folders,
copying audio files into Anki's collection.media directory, and importing
an _anki.txt TSV straight into the running Anki via AnkiConnect.

    python3 scripts/anki_utils.py import FILE_anki.txt
    python3 scripts/anki_utils.py lint     # Twenty Rules по всей коллекции
    python3 scripts/anki_utils.py herorden [--droog]   # позиция новой Kern = Rank
"""

import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

# Базовые пути к Anki2 (кроссплатформенно)
ANKI_BASE_PATHS = [
    Path.home() / "Library/Application Support/Anki2",  # macOS
    Path.home() / ".local/share/Anki2",  # Linux
    Path.home() / "AppData/Roaming/Anki2",  # Windows
]

# Системные папки Anki (не профили)
ANKI_SYSTEM_DIRS = {"addons21", "logs", "crash_reports"}

# Профиль, в котором живут колоды репо (CLAUDE.md, «Anki Integration»)
ANKI_PROFILE = "alex"


def find_anki_profiles(base_path: Path) -> list[Path]:
    """Находит все профили пользователей в директории Anki2."""
    profiles: list[Path] = []

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


def find_anki_media_folder(profile: str = ANKI_PROFILE) -> Path | None:
    """
    Ищет collection.media профиля `profile` — того же, куда пишет import_tsv.
    Не первый найденный: при двух профилях порядок iterdir() случаен, и аудио
    ушло в один профиль, а заметки — в другой (2026-09-28).
    """
    for base_path in ANKI_BASE_PATHS:
        media = base_path / profile / "collection.media"
        if media.is_dir():
            return media

    names = [m.parent.name for base in ANKI_BASE_PATHS for m in find_anki_profiles(base)]
    if names:
        print(f"   ⚠️  Профиля {profile} нет, есть: {', '.join(names)}")
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
    try:
        with urllib.request.urlopen(ANKICONNECT, body, timeout=10) as r:
            reply = json.load(r)
    except urllib.error.URLError as e:
        raise AnkiFout(f"AnkiConnect {ANKICONNECT} не отвечает ({e.reason}) — запусти Anki") from e
    if reply["error"]:
        raise RuntimeError(f"AnkiConnect {action}: {reply['error']}")
    return reply["result"]


FREQUENTIE = "Frequentie NL"
KERN = "Frequentie::Kern"
MAX_BETEKENISSEN = 2
# Единственный отказ canAdd, который значит «уже есть» (AnkiConnect createNote)
DUBBEL = "cannot create note because it is a duplicate"


class KaartFout(ValueError):
    """Партия нарушает Twenty Rules или повторяет первое поле — импорт не начат."""


class AnkiFout(RuntimeError):
    """Anki не запущен, чужой профиль, нет заметок или note type, отказ canAdd —
    до первой записи."""


def betekenissen(translation: str) -> list[str]:
    """`вдруг, внезапно; сразу (разг.)` → три значения. Скобки — пояснение."""
    kaal = re.sub(r"\([^)]*\)", "", translation)
    return [s.strip().lower() for s in re.split(r"[;,]", kaal) if s.strip()]


def twenty_rules(nieuw: dict[str, str], bestaand: dict[str, str]) -> list[str]:
    """Word → Translation новой партии против уже лежащих в Anki.

    Правило 4 (минимум информации): не больше двух значений. Правило 10
    (интерференция): первое значение — это ключ на лицевой стороне RU → NL,
    и если он совпал с другим словом, верны оба ответа, а Anki засчитает
    ошибку. Возвращает список нарушений, пустой — можно импортировать."""
    fouten: list[str] = []
    sleutels: dict[str, str] = {}
    for word, tr in bestaand.items():
        if b := betekenissen(tr):
            sleutels.setdefault(b[0], word)
    for word, tr in nieuw.items():
        b = betekenissen(tr)
        if len(b) > MAX_BETEKENISSEN:
            fouten.append(f"{word}: {len(b)} значений — «{tr}» (правило 4)")
        if not b:
            continue
        ander = sleutels.setdefault(b[0], word)
        if ander != word:
            fouten.append(f"{word}: ключ «{b[0]}» уже у {ander} (правило 10)")
    return fouten


def eis_profiel(profile: str) -> None:
    """AnkiConnect работает с профилем, открытым в Anki: в чужом проверки идут
    вхолостую, а запись уходит не в ту коллекцию. Поэтому это первый вызов."""
    actief = ankiconnect("getActiveProfile")
    if actief != profile:
        nu = f"открыт профиль {actief}" if actief else "не открыт ни один профиль"
        raise AnkiFout(f"в Anki {nu}, нужен {profile} — переключи профиль и запусти снова")


def import_tsv(path: Path, profile: str = ANKI_PROFILE) -> tuple[int, list[str]]:
    """Импорт _anki.txt по его директивам #notetype / #deck / #columns /
    #tags column в профиль `profile`. Дубли (первое поле уже есть у этого note
    type) пропускаются — так повторный импорт безопасен. Возвращает
    (добавлено, пропущенные).

    Повтор первого поля внутри партии — `KaartFout` ещё до Anki: в Twenty
    Rules второй перевод затёр бы первый, а canAdd сверяет заметку только с
    коллекцией — addNotes упал бы на втором экземпляре и откатил всю партию.

    Первый вызов — `eis_profiel`. Дубль — только отказ `DUBBEL`; любой
    другой отказ Anki (нет note type, пустое поле) — `AnkiFout` до записи.
    Колода создаётся последней и только когда есть что добавить (инцидент
    2026-09-28, `tasks/lessons.md`).

    Для «Frequentie NL» сперва `twenty_rules` против всей коллекции этого
    типа; нарушение — `KaartFout`, в Anki ничего не пишется. Проверять до
    импорта обязательно: повторный импорт заметку с тем же Word пропускает,
    так что исправленный перевод туда уже не попадёт."""
    head: dict[str, str] = {}
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            key, _, val = line[1:].partition(":")
            head[key] = val
        elif line.strip():
            rows.append(line.split("\t"))
    columns = head["columns"].split("\t")
    tags_col = int(head["tags column"]) - 1
    notes: list[dict[str, Any]] = [
        {
            "deckName": head["deck"],
            "modelName": head["notetype"],
            "fields": {c: r[i] for i, c in enumerate(columns) if i != tags_col},
            "tags": r[tags_col].split(),
        }
        for r in rows
    ]
    aantal = Counter(n["fields"][columns[0]] for n in notes)
    if herhaald := [w for w, k in aantal.items() if w and k > 1]:
        raise KaartFout(f"{columns[0]} повторяется в партии: {', '.join(herhaald)}")
    eis_profiel(profile)
    if head["notetype"] == FREQUENTIE:
        ids = ankiconnect("findNotes", query=f'"note:{FREQUENTIE}"')
        bestaand = {
            n["fields"]["Word"]["value"]: n["fields"]["Translation"]["value"]
            for n in ankiconnect("notesInfo", notes=ids)
        }
        nieuw = {n["fields"]["Word"]: n["fields"]["Translation"] for n in notes}
        if fouten := twenty_rules(nieuw, bestaand):
            raise KaartFout("\n".join(fouten))
    # Новую колоду canAdd не проверит: AnkiConnect ищет колоду раньше дубля. Дубль
    # же он ищет по note type во всей коллекции, а не в колоде (пока у заметок нет
    # options.duplicateScope), — поэтому проверяем на любой существующей колоде.
    decks = ankiconnect("deckNames")
    proef = head["deck"] if head["deck"] in decks else decks[0]
    ok = ankiconnect(
        "canAddNotesWithErrorDetail", notes=[{**n, "deckName": proef} for n in notes]
    )
    fresh: list[dict[str, Any]] = []
    skipped: list[str] = []
    weigering: dict[str, list[str]] = {}
    for i, (n, o) in enumerate(zip(notes, ok), 1):
        word = n["fields"][columns[0]] or f"заметка {i}"
        if o["canAdd"]:
            fresh.append(n)
        elif o["error"] == DUBBEL:
            skipped.append(word)
        else:
            weigering.setdefault(o["error"], []).append(word)
    if weigering:
        raise AnkiFout("\n".join(f"{e} — {', '.join(w)}" for e, w in weigering.items()))
    if fresh:
        ankiconnect("createDeck", deck=head["deck"])
        ankiconnect("addNotes", notes=fresh)
    return len(fresh), skipped


def lint(profile: str = ANKI_PROFILE) -> list[str]:
    """twenty_rules по всей коллекции «Frequentie NL» — после ручной правки.
    Ноль заметок — отказ, а не «нарушений нет»: так выглядит и чужой профиль,
    и переименованный note type."""
    eis_profiel(profile)
    ids = ankiconnect("findNotes", query=f'"note:{FREQUENTIE}"')
    if not ids:
        raise AnkiFout(f"в профиле {profile} нет заметок «{FREQUENTIE}» — проверять нечего")
    alle = {
        n["fields"]["Word"]["value"]: n["fields"]["Translation"]["value"]
        for n in ankiconnect("notesInfo", notes=ids)
    }
    return twenty_rules(alle, {})


def herorden(profile: str = ANKI_PROFILE, droog: bool = False) -> tuple[int, int]:
    """Позиция каждой новой карточки Kern = её Rank: пресет собирает новые по
    колоде в порядке due, так Anki вводит слова строго по рангу (решение
    2026-10-06). Пишет только due и только там, где он ≠ Rank, — повторный
    запуск ничего не меняет. droog — посчитать, не записывая.

    `deck:` находит и карточки, временно лежащие в фильтрованной колоде; там
    due — место в ней, а не позиция, поэтому они пропускаются.
    setSpecificValueOfCard при отказе не ставит error, а возвращает False —
    поэтому результат сверяется с [True], а после записи позиции читаются
    заново. Отмены у записи нет (skip_undo_entry): перед ней — бэкап.

    Возвращает (новых карточек Kern, позиций к записи или записано)."""
    eis_profiel(profile)
    kaarten = [
        k for k in ankiconnect("cardsInfo", cards=ankiconnect(
            "findCards", query=f'"deck:{KERN}" is:new'))
        if k["deckName"] == KERN
    ]
    scheef = []
    for k in kaarten:
        rank = k["fields"]["Rank"]["value"].strip()
        if not rank.isdigit():
            word = k["fields"]["Word"]["value"]
            raise AnkiFout(f"{word}: Rank «{rank}» — не число, позицию не поставить")
        if k["due"] != int(rank):
            scheef.append((k["cardId"], int(rank), k["fields"]["Word"]["value"]))
    if droog or not scheef:
        return len(kaarten), len(scheef)
    for card, rank, word in scheef:
        if ankiconnect("setSpecificValueOfCard", card=card, keys=["due"],
                       newValues=[rank]) != [True]:
            raise AnkiFout(f"{word}: позиция {rank} не записана")
    ids = [card for card, _, _ in scheef]
    blijft = [k["fields"]["Word"]["value"]
              for k in ankiconnect("cardsInfo", cards=ids)
              if k["due"] != int(k["fields"]["Rank"]["value"])]
    if blijft:
        raise AnkiFout(f"после записи due ≠ Rank: {', '.join(blijft)}")
    return len(kaarten), len(scheef)


if __name__ == "__main__":
    if sys.argv[1:2] == ["herorden"] and set(sys.argv[2:]) <= {"--droog"}:
        droog = "--droog" in sys.argv
        try:
            nieuw, scheef = herorden(droog=droog)
        except AnkiFout as e:
            sys.exit(f"❌ Anki, позиции не тронуты или тронуты не все:\n{e}")
        if droog:
            print(f"новых Kern: {nieuw}, due ≠ Rank у {scheef} — запись без --droog")
        else:
            print(f"✅ новых Kern: {nieuw}, позиция = Rank выставлена у {scheef}")
        sys.exit(0)
    if sys.argv[1:] == ["lint"]:
        try:
            fouten = lint()
        except AnkiFout as e:
            sys.exit(f"❌ Anki, проверка не начата:\n{e}")
        print("\n".join(fouten) or "✅ Twenty Rules: нарушений нет")
        sys.exit(1 if fouten else 0)
    if len(sys.argv) != 3 or sys.argv[1] != "import":
        sys.exit("usage: anki_utils.py import FILE_anki.txt | lint | herorden [--droog]")
    try:
        added, skipped = import_tsv(Path(sys.argv[2]))
    except KaartFout as e:
        sys.exit(f"❌ Twenty Rules, импорт не начат:\n{e}")
    except AnkiFout as e:
        sys.exit(f"❌ Anki, импорт не начат:\n{e}")
    print(f"✅ добавлено {added}" + (f", уже были: {', '.join(skipped)}" if skipped else ""))

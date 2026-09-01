#!/usr/bin/env python3
"""
Text to Speech for Dutch Anki Cards

Генерирует аудио из текстовых файлов (MD, Anki TSV) через edge-tts
и создаёт/обновляет Anki карточки.

Использование:
    # Из транскрипции (Speaker: text)
    python scripts/text_to_speech.py thema_7/2/h07_oefening_02.md --theme gezondheid

    # Из упражнения (plain markdown)
    python scripts/text_to_speech.py thema_7/22_opdracht.md --theme separabel

    # Из существующего Anki файла (добавить аудио)
    python scripts/text_to_speech.py thema_7/vocab_anki.txt --theme wonen --update-anki

TTS-движок: edge-tts (бесплатный, без API-ключей)
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("❌ edge-tts не установлен!")
    print("   Установи: pip install edge-tts")
    sys.exit(1)

from anki_utils import find_anki_media_folder, validate_anki_media, copy_to_anki_media

# Голоса edge-tts для нидерландского
# Темп речи edge-tts: "-10%" = 0.9x от скорости носителя.
# Замерено: rate=-X% даёт длительность в 1/(1-X/100) раз больше,
# то есть -10% -> 0.9x, -20% -> 0.8x, -30% -> 0.7x.
DEFAULT_RATE = "-10%"

VOICES = {
    "colette": "nl-NL-ColetteNeural",
    "fenna": "nl-NL-FennaNeural",
    "maarten": "nl-NL-MaartenNeural",
}


# ═══════════════════════════════════════════════════════════════════════
# FORMAT DETECTION
# ═══════════════════════════════════════════════════════════════════════


def detect_input_format(file_path: Path) -> str:
    """
    Определяет формат входного файла.

    Returns:
        "anki"       — TSV файл с заголовком #separator:tab
        "transcript"  — MD файл с форматом Speaker: text
        "plain"       — всё остальное (упражнения, plain text)
    """
    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Убираем пустые строки для анализа
    non_empty = [l.strip() for l in lines if l.strip()]

    if not non_empty:
        return "plain"

    # Anki TSV: первая непустая строка — #separator:tab
    if non_empty[0] == "#separator:tab":
        return "anki"

    # Transcript: 2+ строки с форматом "Speaker: text"
    speaker_pattern = re.compile(r"^[A-Za-zА-Яа-яё]+\s*:\s*.+$")
    speaker_lines = sum(1 for l in non_empty if speaker_pattern.match(l))
    if speaker_lines >= 2:
        return "transcript"

    return "plain"


# ═══════════════════════════════════════════════════════════════════════
# PARSERS
# ═══════════════════════════════════════════════════════════════════════


def parse_transcript_sentences(path: Path) -> list[dict]:
    """
    Парсит MD файл с транскрипцией (Speaker: text).

    Returns: [{"text": "...", "speaker": "Mila"}, ...]
    """
    sentences = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Пропускаем ремарки типа (смех), (пауза)
            if line.startswith("(") and line.endswith(")"):
                continue

            match = re.match(r"^([A-Za-zА-Яа-яё]+)\s*:\s*(.+)$", line)
            if match:
                text = match.group(2).strip()
                if text:
                    sentences.append({
                        "text": text,
                        "speaker": match.group(1),
                    })

    return sentences


def parse_plain_sentences(path: Path) -> list[dict]:
    """
    Парсит упражнения и plain text из MD файлов.

    Читает MD файл, отфильтровывает служебные строки (заголовки, разделители,
    таблицы, HTML-комментарии), очищает markdown-форматирование и возвращает
    список предложений для озвучки.

    Returns: [{"text": "чистый нидерландский текст"}, ...]
    """
    sentences = []

    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Split into paragraphs (blank line = break), joining wrapped lines
    paragraphs = [p.replace("\n", " ").strip() for p in content.split("\n\n")]

    for para in paragraphs:
        if not para:
            continue
        # Skip headers, separators, tables, comments, blockquotes, placeholders
        if para.startswith(("#", "---", "|", ">", "<!--")):
            continue
        if "..." in para:
            continue
        # Skip lines that are purely italic meta-text (subtitle, woordenlijst note)
        if re.match(r"^_[^_]+_$", para):
            continue

        # Clean markdown formatting
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", para)
        text = re.sub(r"_(.+?)_", r"\1", text)
        text = text.replace('"', "")
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) < 5:
            continue

        sentences.append({"text": text})

    return sentences


def parse_anki_sentences(path: Path) -> list[dict]:
    """
    Парсит существующий Anki TSV файл.

    Returns: [{"text": "...", "translation": "...", "audio": "...",
               "tags": "...", "line_num": int}, ...]
    """
    sentences = []

    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip("\n")

            # Пропускаем заголовки и пустые строки
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            text = parts[0].strip()

            if not text or len(text) < 3:
                continue

            entry = {
                "text": text,
                "translation": parts[1].strip() if len(parts) > 1 else "",
                "audio": parts[2].strip() if len(parts) > 2 else "",
                "tags": parts[3].strip() if len(parts) > 3 else "",
                "line_num": line_num,
            }
            sentences.append(entry)

    return sentences


# ═══════════════════════════════════════════════════════════════════════
# TTS GENERATION
# ═══════════════════════════════════════════════════════════════════════


async def generate_whole_audio(
    sentences: list[dict],
    voice: str,
    output_path: Path,
    rate: str = DEFAULT_RATE,
) -> None:
    """
    Генерирует один MP3 файл из всех предложений.

    Предложения склеиваются через двойной перенос строки,
    чтобы edge-tts добавлял естественные паузы между ними.
    """
    full_text = "\n\n".join(s["text"] for s in sentences)
    communicate = edge_tts.Communicate(full_text, voice, rate=rate)
    await communicate.save(str(output_path))


async def generate_all_audio(
    sentences: list[dict],
    voice: str,
    output_dir: Path,
    prefix: str,
    rate: str = DEFAULT_RATE,
) -> list[str]:
    """
    Генерирует MP3 для каждого предложения через edge-tts.

    Последовательная генерация чтобы не попасть под rate limit.

    Returns: список имён файлов ['prefix_sentence_001.mp3', ...]
    """
    output_dir.mkdir(exist_ok=True)
    audio_files = []

    for i, sent in enumerate(sentences, 1):
        filename = f"{prefix}_sentence_{i:03d}.mp3"
        output_path = output_dir / filename

        communicate = edge_tts.Communicate(sent["text"], voice, rate=rate)
        await communicate.save(str(output_path))

        audio_files.append(filename)

        # Прогресс
        if i % 5 == 0 or i == len(sentences):
            print(f"   {i}/{len(sentences)} предложений озвучено")

    return audio_files


# ═══════════════════════════════════════════════════════════════════════
# ANKI FILE OUTPUT
# ═══════════════════════════════════════════════════════════════════════


def generate_anki_file(
    sentences: list[dict],
    audio_files: list[str],
    output_path: Path,
    theme: str,
    level: str,
):
    """
    Генерирует новый Anki import файл.

    Формат: Dutch text | Russian (or TODO) | Audio | Tags
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags column:4\n\n")

        for sent, audio_file in zip(sentences, audio_files):
            nl_text = sent["text"]
            translation = sent.get("translation", "") or "[TODO: перевод]"
            audio_ref = f"[sound:{audio_file}]"
            tags = f"sententiae::{theme}::{level}::audio"

            f.write(f"{nl_text}\t{translation}\t{audio_ref}\t{tags}\n")


def update_anki_file(
    path: Path,
    sentences: list[dict],
    audio_files: list[str],
    theme: str,
    level: str,
):
    """
    Обновляет существующий Anki файл: добавляет/заменяет audio column.

    Сохраняет оригинальную структуру, заголовки и переводы.
    """
    with open(path, encoding="utf-8") as f:
        original_lines = f.readlines()

    # Маппинг line_num -> audio_file
    audio_map = {}
    for sent, audio_file in zip(sentences, audio_files):
        audio_map[sent["line_num"]] = audio_file

    # Проверяем/добавляем tags column header
    has_tags_header = any("#tags column:" in l for l in original_lines)

    updated_lines = []
    for line_num, line in enumerate(original_lines, 1):
        line = line.rstrip("\n")

        # Добавляем #tags column:4 после #html: если отсутствует
        if not has_tags_header and line.startswith("#html:"):
            updated_lines.append(line)
            updated_lines.append("#tags column:4")
            has_tags_header = True
            continue

        if line_num in audio_map:
            parts = line.split("\t")
            nl_text = parts[0]
            translation = parts[1] if len(parts) > 1 else "[TODO: перевод]"
            audio_ref = f"[sound:{audio_map[line_num]}]"
            tags = f"sententiae::{theme}::{level}::audio"

            updated_lines.append(f"{nl_text}\t{translation}\t{audio_ref}\t{tags}")
        else:
            updated_lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines) + "\n")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Generate Dutch TTS audio for Anki cards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
    # Из транскрипции (Speaker: text)
    python scripts/text_to_speech.py thema_7/2/h07_oefening_02.md --theme gezondheid

    # Из упражнения (plain markdown)
    python scripts/text_to_speech.py thema_7/22_opdracht.md --theme separabel

    # Из Anki файла (добавить аудио к существующим карточкам)
    python scripts/text_to_speech.py vocab_anki.txt --theme wonen --update-anki

    # Цельная озвучка (один MP3 файл вместо отдельных предложений)
    python scripts/text_to_speech.py link/thema_1/verhaal_kennismaken.md --whole

    # С другим голосом + автокопирование
    python scripts/text_to_speech.py file.md --voice maarten --copy-to-anki
        """,
    )
    parser.add_argument("input", type=Path, help="MD или _anki.txt файл")
    parser.add_argument(
        "--theme", default="general", help="Тема для тегов (например: gezondheid)"
    )
    parser.add_argument("--level", default="A2", help="Уровень CEFR (A1, A2, B1)")
    parser.add_argument(
        "--voice",
        default="colette",
        choices=VOICES.keys(),
        help="Голос TTS: colette (жен.), fenna (жен.), maarten (муж.)",
    )
    parser.add_argument(
        "--rate",
        default=DEFAULT_RATE,
        help="Темп речи: -10%% = 0.9x, +0%% = скорость носителя "
        "(по умолчанию: %(default)s)",
    )
    parser.add_argument(
        "--copy-to-anki",
        action="store_true",
        help="Автоматически копировать аудио в Anki media folder",
    )
    parser.add_argument(
        "--update-anki",
        action="store_true",
        help="Обновить существующий anki.txt (добавить audio refs)",
    )
    parser.add_argument(
        "--whole",
        action="store_true",
        help="Один MP3 файл (цельная история) вместо отдельных предложений",
    )

    args = parser.parse_args()

    input_path = args.input.resolve()

    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        return 1

    voice_id = VOICES[args.voice]

    # Валидируем Anki media folder если нужно копирование
    anki_media = None
    if args.copy_to_anki:
        print("🔍 Ищу Anki media folder...")
        anki_media = validate_anki_media(find_anki_media_folder())
        if anki_media is None:
            print("❌ Anki media folder не найден!")
            print("   Проверь что Anki установлен и запускался хотя бы раз.")
            return 1
        print(f"   ✅ Найден: {anki_media}")

    # Определяем формат
    fmt = detect_input_format(input_path)
    print(f"📄 Формат: {fmt}")
    print(f"🎤 Голос: {args.voice} ({voice_id}), темп: {args.rate}")

    # Парсим предложения
    if fmt == "transcript":
        sentences = parse_transcript_sentences(input_path)
    elif fmt == "anki":
        sentences = parse_anki_sentences(input_path)
    elif fmt == "plain":
        sentences = parse_plain_sentences(input_path)
        if sentences is None:
            print("❌ parse_plain_sentences() ещё не реализован!")
            print("   Смотри TODO(human) в scripts/text_to_speech.py")
            return 1
    else:
        print(f"❌ Неизвестный формат: {fmt}")
        return 1

    if not sentences:
        print("❌ Не найдено предложений для озвучки!")
        return 1

    print(f"   Найдено предложений: {len(sentences)}")

    prefix = input_path.stem  # 22_opdracht или h07_oefening_02

    # ── Whole mode: один MP3 файл ──
    if args.whole:
        output_path = input_path.parent / f"{prefix}.mp3"
        print(f"\n🔊 Генерирую цельное аудио ({len(sentences)} предложений)...")
        asyncio.run(
            generate_whole_audio(sentences, voice_id, output_path, args.rate)
        )
        print(f"   ✅ Создан: {output_path}")
        print(f"\n✅ Готово!")
        print(f"   Аудио: {output_path}")
        return 0

    # ── Sentence mode: отдельные MP3 ──
    output_dir = input_path.parent / f"{prefix}_sentences"
    anki_file = input_path.parent / f"sententiae_{args.theme}_anki.txt"

    print(f"\n🔊 Генерирую аудио ({len(sentences)} предложений)...")
    audio_files = asyncio.run(
        generate_all_audio(sentences, voice_id, output_dir, prefix, args.rate)
    )
    print(f"   ✅ Создано файлов: {len(audio_files)}")

    # Anki файл
    if args.update_anki and fmt == "anki":
        print(f"\n📝 Обновляю {input_path.name}...")
        update_anki_file(input_path, sentences, audio_files, args.theme, args.level)
        anki_file = input_path
    else:
        print(f"\n📝 Генерирую Anki файл...")
        generate_anki_file(sentences, audio_files, anki_file, args.theme, args.level)

    # Копируем в Anki
    if anki_media:
        print(f"\n📦 Копирую в Anki media...")
        copied = copy_to_anki_media(output_dir, anki_media, prefix)
        print(f"   Скопировано файлов: {copied}")

    # Итоги
    print(f"\n✅ Готово!")
    print(f"   Аудио:  {output_dir}/")
    print(f"   Anki:   {anki_file}")
    if anki_media:
        print(f"   Media:  {anki_media}/")

    print(f"\n📌 Следующие шаги:")
    if not anki_media:
        print(f"   1. Скопируй в Anki media folder:")
        print(f"      cp {output_dir}/*.mp3 ~/Library/Application\\ Support/Anki2/alex/collection.media/")
    step = 1 if anki_media else 2
    if not args.update_anki or fmt != "anki":
        print(f"   {step}. Заполни переводы в {anki_file.name}")
        step += 1
    print(f"   {step}. Импортируй в Anki: File → Import")
    step += 1
    print(f"   {step}. В Anki: Tools → Check Media")

    # Превью
    print(f"\n📋 Превью (первые 3):")
    for i, (sent, af) in enumerate(zip(sentences[:3], audio_files[:3]), 1):
        text = sent["text"][:60]
        print(f"   {i}. {text}{'...' if len(sent['text']) > 60 else ''}")
        print(f"      → {af}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

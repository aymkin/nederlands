#!/usr/bin/env python3
"""daily_audio.py — аудио дейли для дороги: один mp3 из четырёх частей.

Вход — .txt с парами «нидерландская фраза / русский перевод»: блок из двух строк,
блоки разделены пустой строкой, строки с `#` — комментарии. (.txt, не .md:
Prettier с proseWrap склеил бы две строки пары в один абзац.)

    Gisteren heb ik ticket 2553 afgerond.
    Вчера я закончил тикет 2553.

    Daar ben ik nu mee bezig.
    Сейчас я над ним работаю.

Части (русский голос коротко объявляет каждую):
  1  весь текст по-нидерландски, нормальный темп
  2  по предложению: нидерландский → русский
  3  весь текст по-нидерландски, медленно
  4  русская фраза → пауза, чтобы сказать самому → нидерландская фраза-проверка;
     весь текст два круга

Пауза части 4 пропорциональна фразе: factor × длина NL-фразы + 2 с. У каждого
озвученного куска тишина по краям обрезана, так что и паузы, и длина фразы
настоящие.

Зависимости: pip install edge-tts, ffmpeg. Текст уходит в сервис Microsoft Edge
TTS — как у werk_woorden.py; имена коллег и названия проектов в файл не класть.
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

import edge_tts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anki_utils import AudioFout, duur, keur_mp3

NL_VOICES = {
    "colette": "nl-NL-ColetteNeural",
    "fenna": "nl-NL-FennaNeural",
    "maarten": "nl-NL-MaartenNeural",
}
RU_VOICES = {
    "svetlana": "ru-RU-SvetlanaNeural",
    "dmitry": "ru-RU-DmitryNeural",
}

NORMAAL = "+0%"
LANGZAAM = "-30%"  # -X% даёт длительность в 1/(1-X/100) раз больше: ≈1,43×
RU_RATE = "+0%"

GAP_ZIN = 0.7      # между предложениями части 1
GAP_PAAR = 0.5     # между NL и RU в части 2
GAP_NA = 1.0       # после предложения или пары
GAP_TITEL = 0.8    # после объявления части
GAP_DEEL = 1.5     # перед следующей частью
PAUZE_EXTRA = 2.0
PAUZE_FACTOR = 1.6
MIN_PIECE_SEC = 0.2
MAX_DRIFT = 1.0

DEEL = [
    "Часть первая. Нидерландский, обычный темп.",
    "Часть вторая. Нидерландский и русский.",
    "Часть третья. Нидерландский, медленно.",
    "Часть четвёртая. Говори по-нидерландски после русской фразы. Круг первый.",
]
RONDE_TWEE = "Круг второй."

CYRILLIC = re.compile("[А-Яа-яЁё]")


# ─── Разбор файла ─────────────────────────────────────────────────────


def parse_pairs(path: Path) -> list[tuple[str, str]]:
    """→ [(nl, ru)]. ValueError с номером строки, если файл не по формату."""
    pairs: list[tuple[str, str]] = []
    block: list[tuple[int, str]] = []

    def flush():
        if not block:
            return
        first = block[0][0]
        if len(block) != 2:
            raise ValueError(f"{path.name}:{first}: в блоке {len(block)} строк, "
                             "нужно две (нидерландская и русская)")
        (_, nl), (_, ru) = block
        if CYRILLIC.search(nl):
            raise ValueError(f"{path.name}:{first}: в первой строке кириллица — "
                             "первой идёт нидерландская фраза")
        if not CYRILLIC.search(ru):
            raise ValueError(f"{path.name}:{first + 1}: во второй строке нет "
                             "кириллицы — второй идёт русский перевод")
        pairs.append((nl, ru))
        block.clear()

    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = " ".join(raw.split())
        if line.startswith("#"):
            continue
        if line:
            block.append((n, line))
        else:
            flush()
    flush()
    if not pairs:
        raise ValueError(f"{path.name}: нет ни одной пары")
    return pairs


# ─── План озвучки ─────────────────────────────────────────────────────


class Spraak(NamedTuple):
    taal: str   # "nl" | "ru"
    tekst: str
    rate: str


class Stilte(NamedTuple):
    sec: float


class Antwoord(NamedTuple):
    """Тишина на ответ: длина зависит от озвучки этой NL-фразы."""
    tekst: str


class Merk(NamedTuple):
    """Метка начала части, звука не даёт."""
    label: str


def pauze(sec_nl: float, factor: float = PAUZE_FACTOR) -> float:
    return factor * sec_nl + PAUZE_EXTRA


def plan(pairs: list[tuple[str, str]], normaal: str = NORMAAL,
         langzaam: str = LANGZAAM) -> list:
    def nl(t, rate=normaal):
        return Spraak("nl", t, rate)

    def ru(t):
        return Spraak("ru", t, RU_RATE)

    def kop(i):
        return [Merk(f"deel {i + 1}"), ru(DEEL[i]), Stilte(GAP_TITEL)]

    seg: list = kop(0)
    for i, (n, _) in enumerate(pairs):
        if i:
            seg.append(Stilte(GAP_ZIN))
        seg.append(nl(n))

    seg += [Stilte(GAP_DEEL)] + kop(1)
    for n, r in pairs:
        seg += [nl(n), Stilte(GAP_PAAR), ru(r), Stilte(GAP_NA)]

    seg += [Stilte(GAP_DEEL)] + kop(2)
    for n, _ in pairs:
        seg += [nl(n, langzaam), Stilte(GAP_NA)]

    seg += [Stilte(GAP_DEEL)] + kop(3)
    for ronde in (1, 2):
        if ronde == 2:
            seg += [Stilte(GAP_DEEL), Merk("deel 4, круг 2"), ru(RONDE_TWEE),
                    Stilte(GAP_TITEL)]
        for n, r in pairs:
            seg += [ru(r), Antwoord(n), nl(n), Stilte(GAP_NA)]

    while isinstance(seg[-1], Stilte):
        seg.pop()
    return seg


# ─── Озвучка и склейка ────────────────────────────────────────────────


def _check_piece(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise AudioFout(f"{path.name}: пустой файл")
    sec = duur(path)
    if sec is None:
        raise AudioFout("ffprobe не найден: без него не посчитать паузы")
    if sec < MIN_PIECE_SEC:
        raise AudioFout(f"{path.name}: {sec:.2f} с — слишком коротко")


async def _save(text: str, voice: str, rate: str, path: Path) -> None:
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


# У edge-tts в куске ≈0,25 с тишины в начале и ≈0,9 с в конце (замерено 2026-10-27).
# Без обрезки заданные паузы звучат на ≈1,1 с длиннее, а пауза ответа считается от
# длины фразы вместе с этой тишиной.
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")


def _trim(path: Path) -> None:
    tmp = path.with_name(f"trim_{path.name}")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", TRIM,
                    "-q:a", "4", str(tmp), "-y"], check=True)
    os.replace(tmp, path)


def synth(text: str, voice: str, rate: str, path: Path, tries: int = 2) -> None:
    last: Exception | None = None
    for _ in range(tries):
        try:
            asyncio.run(_save(text, voice, rate, path))
            _trim(path)
            _check_piece(path)
            return
        except Exception as e:  # сеть, 403 edge-tts, брак файла: пробуем ещё раз
            last = e
    raise AudioFout(f"синтез упал: «{text[:40]}» — {type(last).__name__}: {last}")


def _silence(sec: float, path: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", f"{sec:.3f}",
                    "-i", "anullsrc=r=24000:cl=mono", "-q:a", "4", str(path), "-y"],
                   check=True)


def _fmt(sec: float) -> str:
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def build(segments: list, nl_voice: str, ru_voice: str, out_mp3: Path,
          normaal: str = NORMAAL, factor: float = PAUZE_FACTOR,
          title: str = "") -> list[tuple[str, float]]:
    """Озвучивает план, склеивает, пишет out_mp3 только годным. → [(метка, начало)]."""
    voices = {"nl": NL_VOICES[nl_voice], "ru": RU_VOICES[ru_voice]}
    out_mp3 = out_mp3.resolve()  # ffmpeg идёт с cwd=tmp, относительный путь уехал бы туда
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)

        speech: dict[Spraak, tuple[Path, float]] = {}
        todo = list(dict.fromkeys(s for s in segments if isinstance(s, Spraak)))
        for i, s in enumerate(todo, 1):
            path = tmp / f"s{i:03d}.mp3"
            synth(s.tekst, voices[s.taal], s.rate, path)
            speech[s] = (path, duur(path))
            print(f"  озвучено {i:>3}/{len(todo)}  {s.taal} {s.rate:>4}  {s.tekst[:48]}")

        silences: dict[int, tuple[Path, float]] = {}

        def stilte(sec: float) -> tuple[Path, float]:
            ms = round(sec * 1000)
            if ms not in silences:
                p = tmp / f"z{ms}.mp3"
                _silence(ms / 1000, p)
                silences[ms] = (p, duur(p))
            return silences[ms]

        parts: list[tuple[Path, float]] = []
        marks: list[tuple[str, float]] = []
        clock = 0.0
        for s in segments:
            if isinstance(s, Merk):
                marks.append((s.label, clock))
                continue
            if isinstance(s, Spraak):
                p = speech[s]
            elif isinstance(s, Stilte):
                p = stilte(s.sec)
            else:
                p = stilte(pauze(speech[Spraak("nl", s.tekst, normaal)][1], factor))
            parts.append(p)
            clock += p[1]

        listing = tmp / "parts.txt"
        listing.write_text("".join(f"file '{p.name}'\n" for p, _ in parts))
        part = out_mp3.with_name(f".{out_mp3.name}.part")
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
                            "-i", str(listing), "-c:a", "libmp3lame", "-q:a", "4",
                            "-metadata", f"title={title or out_mp3.stem}",
                            "-f", "mp3", str(part), "-y"], cwd=tmp, check=True)
            total = duur(part)
            if (fout := keur_mp3(part)):
                raise AudioFout(f"{out_mp3.name}: {fout}")
            if abs(total - clock) > MAX_DRIFT:
                raise AudioFout(f"склейка уехала на {abs(total - clock):.2f} с "
                                f"(части {clock:.1f} с, файл {total:.1f} с)")
            os.replace(part, out_mp3)
        finally:
            part.unlink(missing_ok=True)

    print(f"\n  итог {_fmt(total)}  →  {out_mp3}")
    return marks


# ─── CLI ──────────────────────────────────────────────────────────────


def _rate(value: str) -> str:
    if not re.fullmatch(r"[+-]\d{1,3}%", value):
        raise argparse.ArgumentTypeError(f"темп вида +0% или -30%, а не {value!r}")
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description="Аудио дейли из четырёх частей")
    ap.add_argument("file", type=Path, help=".txt с парами NL / RU")
    ap.add_argument("--out", type=Path, help="куда писать mp3 (рядом с файлом)")
    ap.add_argument("--nl", choices=NL_VOICES, default="maarten")
    ap.add_argument("--ru", choices=RU_VOICES, default="svetlana")
    ap.add_argument("--normaal", type=_rate, default=NORMAAL)
    ap.add_argument("--langzaam", type=_rate, default=LANGZAAM)
    ap.add_argument("--pauze-factor", type=float, default=PAUZE_FACTOR,
                    help="пауза ответа = factor × длина NL-фразы + 2 с")
    ap.add_argument("--dry-run", action="store_true", help="план без озвучки")
    args = ap.parse_args()

    try:
        pairs = parse_pairs(args.file)
    except (OSError, ValueError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    segments = plan(pairs, args.normaal, args.langzaam)
    unique = len({s for s in segments if isinstance(s, Spraak)})
    print(f"{len(pairs)} предложений, {len(segments)} сегментов, "
          f"{unique} вызовов озвучки")
    if args.dry_run:
        return 0

    out = args.out or args.file.with_suffix(".mp3")
    try:
        marks = build(segments, args.nl, args.ru, out, args.normaal,
                      args.pauze_factor, title=args.file.stem)
    except (AudioFout, subprocess.CalledProcessError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    for label, start in marks:
        print(f"  {label:<16} {_fmt(start)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Werk-woorden: леммы из рабочей почты Alex → колода Anki `Frequentie::Werk`.

Индекс `werk/lemmas.json` считает, сколько раз лемма встретилась в
обезличенных письмах `werk/mail/`. Каждый день 5 самых частых новых лемм
становятся карточками note type «Frequentie NL» (поле Rank = число встреч).
Порядок дня — скилл `werk-woorden`.

    werk_woorden.py due                   # для хука SessionStart
    werk_woorden.py merge VOORKOMENS.json # влить леммы писем в индекс
    werk_woorden.py kies [-n 5]           # кандидаты дня, JSON в stdout
    werk_woorden.py markeer bekend LEMMA… # Alex знает — больше не предлагать
    werk_woorden.py kaarten KAARTEN.json [--audio] [--anki]

VOORKOMENS.json — одна запись на каждое словоупотребление:
    [{"lemma": "aangeven", "form": "aangegeven", "zin": "...",
      "bron": "mail/2026-09-22_reispas-vertraging.md"}]
KAARTEN.json — по записи на выбранную лемму:
    [{"lemma": "vertraging", "word": "de vertraging", "zin": "...",
      "vertaling": "задержка", "zin_vertaling": "..."}]

Stdlib; `--audio` требует edge-tts, `--anki` — запущенный Anki с AnkiConnect.
"""

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WERK = ROOT / "werk"
INDEX = WERK / "lemmas.json"
KERN_DECKS = sorted((ROOT / "frequentie").glob("*_anki.txt"))
CURSUS_INDEXEN = [ROOT / c / "woordenlijst_index.txt" for c in ("link", "de_opmaat")]
LIDWOORDEN = ("de ", "het ", "de/het ")

TSV_HEADER = (
    "#separator:tab\n#html:true\n#notetype:Frequentie NL\n#deck:Frequentie::Werk\n"
    "#columns:Word\tRank\tExample\tTranslation\tTranslationExample\tAudio\tTags\n"
    "#tags column:7\n"
)


def vandaag() -> str:
    # Anki и anki_vandaag.py переворачивают день в 04:00 — так же и здесь,
    # иначе ночная сессия засчитает прогон вчерашним числом.
    return (dt.datetime.now() - dt.timedelta(hours=4)).date().isoformat()


def kaal(word: str) -> str:
    """`het gebruik` → `gebruik`: ключ индекса — лемма без lidwoord."""
    w = word.strip().lower()
    for lw in LIDWOORDEN:
        if w.startswith(lw):
            return w[len(lw):]
    return w


def load() -> dict:
    if INDEX.exists():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {"laatste_run": None, "verwerkt": [], "lemmas": {}}


def save(idx: dict) -> None:
    INDEX.write_text(
        json.dumps(idx, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def kern_lemmas() -> set[str]:
    """Первые поля колод frequentie/ — эти слова уже живут в Anki."""
    out = set()
    for deck in KERN_DECKS:
        for line in deck.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                out.add(kaal(line.split("\t", 1)[0]))
    return out


def cursus_woorden() -> dict[str, list[str]]:
    """Слово → курсы Alex, где оно было в woordenlijst. Только подсказка:
    встретить слово в курсе ≠ знать его (daily/frequentie_2026/plan.md, 2.4)."""
    out: dict[str, list[str]] = {}
    for path in CURSUS_INDEXEN:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            for w in line.replace(",", " ").split():
                w = w.lower()
                if path.parent.name not in out.setdefault(w, []):
                    out[w].append(path.parent.name)
    return out


def cmd_due(_args) -> int:
    last = load()["laatste_run"]
    if last != vandaag():
        print(
            f"📬 werk-woorden: сегодня прогона ещё не было (последний: {last or '—'}). "
            "До задачи пользователя загрузи скилл werk-woorden и пройди его."
        )
    return 0


def cmd_merge(args) -> int:
    idx = load()
    kern = kern_lemmas()
    records = json.loads(Path(args.file).read_text(encoding="utf-8"))
    nieuw_bronnen = {r["bron"] for r in records} - set(idx["verwerkt"])
    skipped = {r["bron"] for r in records} - nieuw_bronnen
    for bron in sorted(skipped):
        print(f"⏭  {bron} уже в индексе — пропущен (повторный merge удвоил бы счёт)")

    added = 0
    for r in records:
        if r["bron"] not in nieuw_bronnen:
            continue
        key = kaal(r["lemma"])
        e = idx["lemmas"].setdefault(
            key, {"count": 0, "vormen": [], "zinnen": [], "status": "nieuw"}
        )
        e["count"] += 1
        if r["form"] not in e["vormen"]:
            e["vormen"].append(r["form"])
        ctx = {"zin": r["zin"], "bron": r["bron"]}
        if ctx not in e["zinnen"]:
            e["zinnen"].append(ctx)
        if e["status"] == "nieuw" and key in kern:
            e["status"] = "kern"
        added += 1

    idx["verwerkt"] = sorted(set(idx["verwerkt"]) | nieuw_bronnen)
    idx["laatste_run"] = vandaag()
    save(idx)
    lemmas = idx["lemmas"].values()
    print(
        f"✅ +{added} употреблений из {len(nieuw_bronnen)} писем. Индекс: "
        f"{len(idx['lemmas'])} лемм, из них nieuw "
        f"{sum(e['status'] == 'nieuw' for e in lemmas)}, kern "
        f"{sum(e['status'] == 'kern' for e in lemmas)}, kaart "
        f"{sum(e['status'] == 'kaart' for e in lemmas)}."
    )
    return 0


def cmd_kies(args) -> int:
    idx = load()
    lemmas = idx["lemmas"]
    # Kern растёт партиями уже после merge — сверяемся с ним на момент выбора.
    kern = kern_lemmas()
    for k, e in lemmas.items():
        if e["status"] == "nieuw" and k in kern:
            e["status"] = "kern"
    save(idx)
    # Порядок: частота, затем в скольких письмах встретилась, затем кто раньше
    # попал в индекс — dict хранит порядок вставки, sorted() стабилен.
    kandidaten = sorted(
        (k for k, e in lemmas.items() if e["status"] == "nieuw"),
        key=lambda k: (
            -lemmas[k]["count"],
            -len({z["bron"] for z in lemmas[k]["zinnen"]}),
        ),
    )[: args.n]
    cursus = cursus_woorden()
    print(
        json.dumps(
            [{"lemma": k, "cursus": cursus.get(k, []), **lemmas[k]} for k in kandidaten],
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


def cmd_markeer(args) -> int:
    idx = load()
    missing = [w for w in args.lemmas if kaal(w) not in idx["lemmas"]]
    if missing:
        print(f"❌ не в индексе: {', '.join(missing)}")
        return 1
    for w in args.lemmas:
        idx["lemmas"][kaal(w)]["status"] = args.status
    save(idx)
    print(f"✅ {len(args.lemmas)} лемм → {args.status}")
    return 0


async def synth(items: list[tuple[str, Path]]) -> None:
    import edge_tts

    from text_to_speech import DEFAULT_RATE, VOICES

    for text, path in items:
        await edge_tts.Communicate(text, VOICES["colette"], rate=DEFAULT_RATE).save(
            str(path)
        )


def cmd_kaarten(args) -> int:
    idx = load()
    kaarten = json.loads(Path(args.file).read_text(encoding="utf-8"))
    dag = vandaag()
    unknown = [k["lemma"] for k in kaarten if kaal(k["lemma"]) not in idx["lemmas"]]
    if unknown:
        print(f"❌ леммы не в индексе: {', '.join(unknown)} — сначала merge")
        return 1

    out = WERK / f"werk_dag{dag}_anki.txt"
    rows = []
    for k in kaarten:
        key = kaal(k["lemma"])
        e = idx["lemmas"][key]
        audio = f"werk_{key.replace(' ', '_')}.mp3"
        rows.append(
            "\t".join([
                k["word"], str(e["count"]), k["zin"], k["vertaling"],
                k["zin_vertaling"], f"[sound:{audio}]",
                f"frequentie::werk frequentie::werk::dag{dag}",
            ])
        )
        e["status"], e["kaart_dag"] = "kaart", dag
    out.write_text(TSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    save(idx)
    print(f"✅ {len(rows)} карточек → {out.relative_to(ROOT)}")

    if args.audio:
        from anki_utils import find_anki_media_folder, validate_anki_media

        media = validate_anki_media(find_anki_media_folder())
        if media is None:
            print("❌ папка Anki media не найдена — аудио не создано")
            return 1
        items = [
            (k["zin"], media / f"werk_{kaal(k['lemma']).replace(' ', '_')}.mp3")
            for k in kaarten
        ]
        asyncio.run(synth(items))
        print(f"🔊 {len(items)} mp3 → {media}")

    if args.anki:
        from anki_utils import import_tsv

        added, skipped = import_tsv(out)
        print(f"📥 Anki: +{added}" + (f", уже были: {', '.join(skipped)}" if skipped else ""))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("due", help="одна строка, если сегодня прогона ещё не было")
    m = sub.add_parser("merge", help="влить VOORKOMENS.json в индекс")
    m.add_argument("file")
    k = sub.add_parser("kies", help="топ новых лемм, JSON")
    k.add_argument("-n", type=int, default=5)
    mk = sub.add_parser("markeer", help="сменить status лемм (bekend | nieuw)")
    mk.add_argument("status", choices=["bekend", "nieuw"])
    mk.add_argument("lemmas", nargs="+")
    c = sub.add_parser("kaarten", help="KAARTEN.json → TSV дня, status=kaart")
    c.add_argument("file")
    c.add_argument("--audio", action="store_true", help="edge-tts → Anki media")
    c.add_argument("--anki", action="store_true", help="импорт через AnkiConnect")
    args = p.parse_args()
    return {"due": cmd_due, "merge": cmd_merge, "kies": cmd_kies,
            "markeer": cmd_markeer, "kaarten": cmd_kaarten}[args.cmd](args)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())

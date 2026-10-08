#!/usr/bin/env python3
"""anki_vandaag.py — the words Alex worked on in Anki today, for the Fluent bridge.

Morning: Anki session on the frequency deck (note type "Frequentie NL").
Later:   /fluent-review builds its grammar exercises around those words.
This script is the bridge: it reads a COPY of the Anki collection (so an open
Anki is fine, and a closed one too — the file keeps every review), and writes
a markdown list in three tiers, the first non-empty ones winning:

    Новые         cards whose FIRST review falls on the day
    Повторены     cards reviewed on the day that were first seen earlier
    Последние     fallback when the day has neither: the last N words reviewed
                  before it, each with its date

The header line always states how fresh the collection is (file mtime, last
review in it), so an empty day is never mistaken for "no Anki today": a
session done on a phone shows up only after the desktop Anki has synced.

Only Python 3 stdlib. Never writes to the Anki collection.

    python3 scripts/anki_vandaag.py                       # today, "Frequentie NL"
    python3 scripts/anki_vandaag.py --date 2026-06-30 \
        --notetype "LINK Vocabulary"                      # any day, any note type
    python3 scripts/anki_vandaag.py --out private/frequentie/vandaag.md

Anki's day rolls over at 04:00 by default (col.conf "rollover"); the same
offset is applied here, so a 23:30 session and a 00:30 session land on one day.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from anki_utils import ANKI_BASE_PATHS, ANKI_PROFILE, find_anki_profiles  # same dir

ROLLOVER_HOURS = 4
DEFAULT_NOTETYPE = "Frequentie NL"
LAATST_DEFAULT = 20  # one Kern day
TAG_RE = re.compile(r"<[^>]+>")
SOUND_RE = re.compile(r"\[sound:[^\]]+\]")


def clean(field: str) -> str:
    field = SOUND_RE.sub("", field)
    field = TAG_RE.sub(" ", field)
    return html.unescape(field).replace("\xa0", " ").strip()


def collection_path(profile: str) -> Path:
    # find_anki_profiles returns each profile's collection.media dir.
    profiles = [m.parent for base in ANKI_BASE_PATHS for m in find_anki_profiles(base)]
    if not profiles:
        sys.exit("Anki profile not found (see anki_utils.find_anki_profiles)")
    match = [p for p in profiles if p.name == profile]
    if not match:
        sys.exit(f"profile {profile!r} not among {[p.name for p in profiles]}")
    return match[0] / "collection.anki2"


def day_bounds_ms(day: date) -> tuple[int, int]:
    # Naive on purpose: local 04:00 → 04:00, so a DST day spans 23 or 25 hours.
    start = datetime(day.year, day.month, day.day, ROLLOVER_HOURS)  # noqa: DTZ001
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


@contextmanager
def kopie(col: Path):
    """A read-only connection to a snapshot of the collection; the copy is deleted
    on exit. Never touches the original."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "col.anki2"
        shutil.copy2(col, copy)  # Anki may hold the original open/locked
        # Anki runs SQLite in WAL mode: a running Anki keeps recent changes in
        # collection.anki2-wal and checkpoints them into the main file only
        # later. Copying the main file alone yields a snapshot that can be
        # minutes old — exactly long enough to miss the morning's session,
        # which is the one this script exists to report. Copy the journal too.
        for suffix in ("-wal", "-shm"):
            side = col.with_name(col.name + suffix)
            if side.exists():
                shutil.copy2(side, copy.with_name(copy.name + suffix))
        con = sqlite3.connect(copy)
        # Anki registers a custom collation the plain sqlite3 module lacks.
        con.create_collation(
            "unicase", lambda a, b: (a.lower() > b.lower()) - (a.lower() < b.lower())
        )
        try:
            yield con
        finally:
            con.close()


Note = tuple  # (notetype name, field names, cleaned field values)


@dataclass
class Dag:
    day: date
    nieuw: list[Note] = field(default_factory=list)
    herhaald: list[Note] = field(default_factory=list)
    laatst: list[tuple[datetime, Note]] = field(default_factory=list)
    reviews_op_dag: int = 0          # revlog rows on the day, any note type
    collectie_bijgewerkt: datetime | None = None
    laatste_herhaling: datetime | None = None


def _filter(notetypes: list[str] | None) -> tuple[str, tuple]:
    if not notetypes:
        return "", ()
    return f" AND nt.name IN ({','.join('?' * len(notetypes))})", tuple(notetypes)


def _note(fields: dict[int, list[str]], ntid: int, name: str, flds: str) -> Note:
    return (name, fields.get(ntid, []), [clean(x) for x in flds.split("\x1f")])


def _mtime(col: Path) -> datetime:
    """Newest write to the collection, WAL included: Anki keeps fresh reviews
    in the -wal file for a while, so the main file alone can look hours old."""
    parts = [col, col.with_name(col.name + "-wal")]
    return datetime.fromtimestamp(max(p.stat().st_mtime for p in parts if p.exists()))


def werkdag(col: Path, day: date, notetypes: list[str] | None,
            laatst: int = LAATST_DEFAULT) -> Dag:
    """The day's three tiers; `laatst` is filled only when the first two are empty."""
    lo, hi = day_bounds_ms(day)
    nt_sql, nt_args = _filter(notetypes)
    dag = Dag(day=day, collectie_bijgewerkt=_mtime(col))
    with kopie(col) as con:
        fields: dict[int, list[str]] = {}
        for ntid, name in con.execute("SELECT ntid, name FROM fields ORDER BY ntid, ord"):
            fields.setdefault(ntid, []).append(name)

        last = con.execute("SELECT MAX(id) FROM revlog").fetchone()[0]
        if last:
            dag.laatste_herhaling = datetime.fromtimestamp(last / 1000)
        dag.reviews_op_dag = con.execute(
            "SELECT COUNT(*) FROM revlog WHERE id >= ? AND id < ?", (lo, hi)
        ).fetchone()[0]

        nieuw = con.execute(
            f"""
            WITH first AS (SELECT cid, MIN(id) AS fid FROM revlog GROUP BY cid)
            SELECT n.id, nt.id, nt.name, n.flds, MIN(f.fid)
            FROM first f
            JOIN cards c ON c.id = f.cid
            JOIN notes n ON n.id = c.nid
            JOIN notetypes nt ON nt.id = n.mid
            WHERE f.fid >= ? AND f.fid < ?{nt_sql}
            GROUP BY n.id ORDER BY MIN(f.fid)
            """,
            (lo, hi, *nt_args),
        ).fetchall()
        nieuw_ids = {row[0] for row in nieuw}
        dag.nieuw = [_note(fields, r[1], r[2], r[3]) for r in nieuw]

        herhaald = con.execute(
            f"""
            SELECT n.id, nt.id, nt.name, n.flds, MIN(r.id)
            FROM revlog r
            JOIN cards c ON c.id = r.cid
            JOIN notes n ON n.id = c.nid
            JOIN notetypes nt ON nt.id = n.mid
            WHERE r.id >= ? AND r.id < ?{nt_sql}
            GROUP BY n.id ORDER BY MIN(r.id)
            """,
            (lo, hi, *nt_args),
        ).fetchall()
        dag.herhaald = [_note(fields, r[1], r[2], r[3])
                        for r in herhaald if r[0] not in nieuw_ids]

        if not dag.nieuw and not dag.herhaald and laatst > 0:
            rows = con.execute(
                f"""
                SELECT nt.id, nt.name, n.flds, MAX(r.id)
                FROM revlog r
                JOIN cards c ON c.id = r.cid
                JOIN notes n ON n.id = c.nid
                JOIN notetypes nt ON nt.id = n.mid
                WHERE r.id < ?{nt_sql}
                GROUP BY n.id ORDER BY MAX(r.id) DESC LIMIT ?
                """,
                (lo, *nt_args, laatst),
            ).fetchall()
            dag.laatst = [(datetime.fromtimestamp(r[3] / 1000), _note(fields, *r[:3]))
                          for r in rows]
    return dag


def _regel(note: Note) -> str:
    name, field_names, values = note
    get = dict(zip(field_names, values)).get
    word = get("Word") or get("Nederlands") or get("Front") or values[0]
    translation = get("Translation") or get("Русский") or get("Back") or ""
    example = get("Example") or ""
    line = f"- **{word}**"
    if translation:
        line += f" — {translation}"
    if example:
        line += f" · _{example}_"
    return line


def _status(dag: Dag) -> list[str]:
    def t(x: datetime | None) -> str:
        return x.strftime("%d.%m %H:%M") if x else "—"

    return [
        f"Коллекция обновлена {t(dag.collectie_bijgewerkt)} · последнее повторение "
        f"в ней {t(dag.laatste_herhaling)} · повторений за {dag.day.isoformat()}: "
        f"{dag.reviews_op_dag}.",
    ]


def render(dag: Dag) -> str:
    lines = [f"# Anki — {dag.day.isoformat()}", ""] + _status(dag) + [""]

    if dag.nieuw or dag.herhaald:
        lines += ["Fluent: строй упражнения на этих словах; НЕ заводить их в",
                  "new_vocabulary (повторение ведёт Anki).", ""]
        for kop, notes in (("Новые", dag.nieuw), ("Повторены сегодня", dag.herhaald)):
            if notes:
                lines += [f"## {kop} ({len(notes)})", ""] + [_regel(n) for n in notes] + [""]
    elif dag.laatst:
        if dag.reviews_op_dag:
            lines += ["⚠ Повторения за этот день есть, но не по заданному типу заметок.", ""]
        else:
            lines += [
                "⚠ За этот день в коллекции нет ни одного повторения. Закрытая Anki",
                "не причина — файл хранит все повторения. Причина — занятие на другом",
                "устройстве: открой Anki на компьютере, дай синхронизироваться и",
                "перезапусти скрипт. Пока — слова, которые Alex видел последними.",
                "",
            ]
        lines += ["Fluent: это опора, а не слова дня; НЕ заводить в new_vocabulary.", "",
                  f"## Последние из коллекции ({len(dag.laatst)})", ""]
        lines += [f"{_regel(n)} · {when:%d.%m}" for when, n in dag.laatst]
        lines.append("")
    else:
        lines += ["⚠ В коллекции нет ни одного повторения по этому типу заметок.", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--date", type=date.fromisoformat, default=None,
                    help="YYYY-MM-DD (default: today, with 04:00 rollover)")
    ap.add_argument("--notetype", action="append",
                    help=f"note type(s) to include (default: {DEFAULT_NOTETYPE!r})")
    ap.add_argument("--all", action="store_true", help="every note type")
    ap.add_argument("--profile", default=ANKI_PROFILE,
                    help=f"Anki profile name (default: {ANKI_PROFILE})")
    ap.add_argument("--laatst", type=int, default=LAATST_DEFAULT,
                    help="fallback list length when the day has no cards (0 = off)")
    ap.add_argument("--out", type=Path, help="also write the markdown here")
    args = ap.parse_args()

    now = datetime.now().astimezone() - timedelta(hours=ROLLOVER_HOURS)
    day = args.date or now.date()
    notetypes = None if args.all else (args.notetype or [DEFAULT_NOTETYPE])

    dag = werkdag(collection_path(args.profile), day, notetypes, args.laatst)
    text = render(dag)
    sys.stdout.write(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"→ {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

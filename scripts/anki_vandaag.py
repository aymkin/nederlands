#!/usr/bin/env python3
"""anki_vandaag.py — words Alex introduced in Anki today, for the Fluent bridge.

Morning: Anki session on the frequency deck (note type "Frequentie NL").
Later:   /fluent-review builds its grammar exercises around those words.
This script is the bridge: it reads a COPY of the Anki collection (so an open
Anki is fine), finds notes whose cards got their FIRST review on the given
day, and writes them as a markdown list.

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
from datetime import date, datetime, timedelta
from pathlib import Path

from anki_utils import ANKI_BASE_PATHS, find_anki_profiles  # same dir

ROLLOVER_HOURS = 4
DEFAULT_NOTETYPE = "Frequentie NL"
TAG_RE = re.compile(r"<[^>]+>")
SOUND_RE = re.compile(r"\[sound:[^\]]+\]")


def clean(field: str) -> str:
    field = SOUND_RE.sub("", field)
    field = TAG_RE.sub(" ", field)
    return html.unescape(field).replace("\xa0", " ").strip()


def collection_path(profile: str | None) -> Path:
    # find_anki_profiles returns each profile's collection.media dir.
    profiles = [m.parent for base in ANKI_BASE_PATHS for m in find_anki_profiles(base)]
    if not profiles:
        sys.exit("Anki profile not found (see anki_utils.find_anki_profiles)")
    if profile:
        match = [p for p in profiles if p.name == profile]
        if not match:
            sys.exit(f"profile {profile!r} not among {[p.name for p in profiles]}")
        return match[0] / "collection.anki2"
    return profiles[0] / "collection.anki2"


def day_bounds_ms(day: date) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, ROLLOVER_HOURS)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def introduced_on(col: Path, day: date, notetypes: list[str] | None):
    """Notes whose cards had their first-ever review inside `day`.

    Returns (notetype_name, field_names, field_values) per note.
    """
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "col.anki2"
        shutil.copy2(col, copy)  # Anki may hold the original open/locked
        con = sqlite3.connect(copy)
        # Anki registers a custom collation the plain sqlite3 module lacks.
        con.create_collation(
            "unicase", lambda a, b: (a.lower() > b.lower()) - (a.lower() < b.lower())
        )
        lo, hi = day_bounds_ms(day)
        rows = con.execute(
            """
            WITH first AS (SELECT cid, MIN(id) AS fid FROM revlog GROUP BY cid)
            SELECT DISTINCT nt.id, nt.name, n.flds
            FROM first f
            JOIN cards c ON c.id = f.cid
            JOIN notes n ON n.id = c.nid
            JOIN notetypes nt ON nt.id = n.mid
            WHERE f.fid >= ? AND f.fid < ?
            ORDER BY f.fid
            """,
            (lo, hi),
        ).fetchall()
        fields = {}
        for ntid, ord_, name in con.execute(
            "SELECT ntid, ord, name FROM fields ORDER BY ntid, ord"
        ):
            fields.setdefault(ntid, []).append(name)
        con.close()
    out = []
    for ntid, name, flds in rows:
        if notetypes and name not in notetypes:
            continue
        values = [clean(x) for x in flds.split("\x1f")]
        out.append((name, fields.get(ntid, []), values))
    return out


def render(day: date, notes) -> str:
    lines = [f"# Anki — nieuw op {day.isoformat()}", ""]
    if not notes:
        lines.append("_Geen nieuwe kaarten._")
        return "\n".join(lines) + "\n"
    lines.append(f"{len(notes)} nieuwe woorden. Fluent: gebruik ze in de")
    lines.append("grammatica-oefeningen; NIET als new_vocabulary opslaan (Anki")
    lines.append("bezit hun herhaling).")
    lines.append("")
    for name, field_names, values in notes:
        get = dict(zip(field_names, values)).get
        word = get("Word") or get("Nederlands") or get("Front") or values[0]
        translation = get("Translation") or get("Русский") or get("Back") or ""
        example = get("Example") or ""
        line = f"- **{word}**"
        if translation:
            line += f" — {translation}"
        if example:
            line += f" · _{example}_"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--date", type=date.fromisoformat, default=None,
                    help="YYYY-MM-DD (default: today, with 04:00 rollover)")
    ap.add_argument("--notetype", action="append",
                    help=f"note type(s) to include (default: {DEFAULT_NOTETYPE!r})")
    ap.add_argument("--all", action="store_true", help="every note type")
    ap.add_argument("--profile", help="Anki profile name (default: first found)")
    ap.add_argument("--out", type=Path, help="also write the markdown here")
    args = ap.parse_args()

    now = datetime.now() - timedelta(hours=ROLLOVER_HOURS)
    day = args.date or now.date()
    notetypes = None if args.all else (args.notetype or [DEFAULT_NOTETYPE])

    notes = introduced_on(collection_path(args.profile), day, notetypes)
    text = render(day, notes)
    sys.stdout.write(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"→ {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

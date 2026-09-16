#!/usr/bin/env python3
"""frequentie_fluent.py — Fluent SR under the frequency-core plan.

Division of labour (plan decision 4.2, refined 2026-09-14): Anki owns the
WORDS, Fluent owns the SENTENCES built from them plus the learner's own error
patterns. Nothing lives in both SRS — a word reviewed twice costs double and
buys nothing (Mondria & Wiersma 2004).

Two modes:

    --reset              keep only error_pattern items, wipe their history,
                         drop everything else (Link vocab/grammar backlog)
    --zinnen DAGFILE     seed today's sentences from the "## Zinnen" section
                         of private/frequentie/vandaag.md

Both back up spaced-repetition.json to .backups/pre-frequentie-<stamp>/ and
write atomically, the same contract as scripts/fluent_import.py. Stdlib only.

Sentence lines in the day file look like:

    - Иногда я работаю дома. → Soms werk ik thuis. · инверсия

i.e. `- <russisch> → <nederlands> · <hint>`, the hint optional.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SR_PATH = Path(os.path.expanduser("~/.claude/fluent-data/spaced-repetition.json"))
ZIN_RE = re.compile(r"^-\s*(?P<ru>.+?)\s*→\s*(?P<nl>.+?)(?:\s*·\s*(?P<hint>.+?))?\s*$")

# history fields a reset must clear; content/answer/category survive
HISTORY_DEFAULTS = {
    "interval_days": 1, "repetitions": 0, "easiness_factor": 2.5,
    "stability": None, "fsrs_difficulty": None, "consecutive_correct": 0,
    "consecutive_incorrect": 0, "last_quality": 3, "mastery_level": 0,
    "total_reviews": 0, "review_history": [],
}


def load() -> dict:
    return json.loads(SR_PATH.read_text(encoding="utf-8"))


def save(sr: dict, tag: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup = SR_PATH.parent / ".backups" / f"pre-frequentie-{tag}-{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SR_PATH, backup / SR_PATH.name)
    tmp = SR_PATH.with_name(f"{SR_PATH.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(sr, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SR_PATH)
    return backup


def rebuild_queue(sr: dict, today: str) -> None:
    """Same bucketing as fluent_import.rebuild_queue — keep them in step."""
    items = sr.setdefault("items", {})
    tom = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    week = (date.fromisoformat(today) + timedelta(days=7)).isoformat()
    q = {"today": [], "tomorrow": [], "this_week": [], "later": []}
    for iid, it in items.items():
        due = it.get("due_date", today)
        bucket = ("today" if due <= today else "tomorrow" if due == tom
                  else "this_week" if due <= week else "later")
        q[bucket].append(iid)
    sr["review_queue"] = q
    sr.setdefault("metadata", {})["last_updated"] = today
    sr["metadata"]["total_items_tracked"] = len(items)


def do_reset(sr: dict, today: str) -> dict:
    items = sr.get("items", {})
    kept, dropped = {}, {}
    for iid, it in items.items():
        if it.get("type") == "error_pattern":
            it = {**it, **HISTORY_DEFAULTS, "due_date": today, "last_reviewed": today}
            kept[iid] = it
        else:
            dropped[it.get("type", "?")] = dropped.get(it.get("type", "?"), 0) + 1
    sr["items"] = kept
    return {"kept": len(kept), "dropped": dropped}


def parse_zinnen(path: Path) -> list[tuple[str, str, str]]:
    out, inside = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip().lower().startswith("## zinnen")
            continue
        if inside and line.strip().startswith("-"):
            m = ZIN_RE.match(line.strip())
            if m:
                out.append((m["ru"].strip(), m["nl"].strip(), (m["hint"] or "").strip()))
    return out


def do_zinnen(sr: dict, zinnen: list, today: str) -> dict:
    items = sr.setdefault("items", {})
    added = skipped = 0
    for n, (ru, nl, hint) in enumerate(zinnen, 1):
        iid = f"freq_zin_{today.replace('-', '')}_{n:02d}"
        if iid in items:
            skipped += 1
            continue
        items[iid] = {
            "id": iid,
            "type": "grammar_rule",          # Fluent serves these as production
            "content": f"{ru}" + (f" ({hint})" if hint else ""),
            "answer": nl,
            "category": "frequentie_zinnen",
            "difficulty": "A2",
            "created_date": today,
            "due_date": today,               # today's sentence trains today
            "interval_days": 1,
            "repetitions": 0,
            "easiness_factor": 2.5,
            "stability": None,
            "fsrs_difficulty": None,
            "consecutive_correct": 0,
            "consecutive_incorrect": 0,
            "last_reviewed": today,
            "last_quality": 3,
            "mastery_level": 0,
            "total_reviews": 0,
            # "critical" is the only rank that clears a backlog of "high"
            # items: read-db sorts by priority, then caps at the daily
            # limit, so anything below the cap is simply never served.
            "priority": "critical",
        }
        added += 1
    return {"added": added, "skipped": skipped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--reset", action="store_true",
                    help="drop everything except error_pattern items")
    ap.add_argument("--zinnen", type=Path,
                    help="day file with a '## Zinnen' section")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()
    if not args.reset and not args.zinnen:
        ap.error("nothing to do: pass --reset and/or --zinnen")

    today = date.today().isoformat()
    sr = load()
    before = len(sr.get("items", {}))
    report = {}
    if args.reset:
        report["reset"] = do_reset(sr, today)
    if args.zinnen:
        zinnen = parse_zinnen(args.zinnen)
        if not zinnen:
            sys.exit(f"no '## Zinnen' lines found in {args.zinnen}")
        report["zinnen"] = do_zinnen(sr, zinnen, today)
    rebuild_queue(sr, today)

    print(f"items {before} → {len(sr['items'])}")
    for k, v in report.items():
        print(f"  {k}: {v}")
    print(f"  queue.today: {len(sr['review_queue']['today'])}")
    if args.dry_run:
        print("dry run — nothing written")
        return 0
    backup = save(sr, "reset" if args.reset else "zinnen")
    print(f"backup → {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

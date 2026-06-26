#!/usr/bin/env python3
"""Импорт лексики/грамматики активной темы курса в spaced-repetition Fluent."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def today_str() -> str:
    return date_str(datetime.now())


def tomorrow(s: str) -> str:
    return date_str(parse_date(s) + timedelta(days=1))


def date_plus_days(s: str, n: int) -> str:
    return date_str(parse_date(s) + timedelta(days=n))


def load_manifest(course_dir: Path) -> dict:
    return json.loads((course_dir / "curriculum.json").read_text(encoding="utf-8"))


def active_unit(manifest: dict) -> dict:
    actives = [u for u in manifest["units"] if u.get("status") == "active"]
    if len(actives) != 1:
        raise ValueError(f"expected exactly 1 active unit, got {len(actives)}")
    return actives[0]


def unit_prefix(course: str, unit_id: str) -> str:
    # "thema_8" -> "8"; устойчивый префикс для idempotency + фильтра гейта
    num = unit_id.split("_")[-1]
    return f"{course}_t{num}_"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_woordenlijst(anki_path: Path) -> list:
    rows = []
    for line in anki_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 3:
            continue  # ponytail: woordenlijst rows have 5 cols; <3 = malformed, skip
        word = cols[0].strip()
        translation = cols[2].strip()  # Word | Example | Translation | ...
        if word:
            rows.append((word, translation))
    return rows


def _taak_from_name(name: str) -> str:
    m = re.search(r"taak(\d+)", name)
    return f"taak{m.group(1)}" if m else "taak0"


def vocab_items(course: str, unit: dict, course_dir: Path) -> list:
    num = unit["id"].split("_")[-1]
    prefix = unit_prefix(course, unit["id"])
    unit_dir = course_dir / unit["id"]
    items = []
    files = sorted(unit_dir.rglob(f"*woordenlijst*thema{num}*_anki.txt"))
    for f in files:
        taak = _taak_from_name(f.name)
        for word, translation in parse_woordenlijst(f):
            items.append({
                "item_id": f"{prefix}voc_{taak}_{slug(word)}",
                "item_type": "vocabulary",
                "content": word,
                "answer": translation,
                "category": f"{course}_thema{num}",
                "priority": "medium",
            })
    return items

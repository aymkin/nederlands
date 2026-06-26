#!/usr/bin/env python3
"""Импорт лексики/грамматики активной темы курса в spaced-repetition Fluent."""
import json
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

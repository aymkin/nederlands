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


_SECTION_RE = re.compile(r"^##\s+(\d+\.\d+)\s+(.+?)\s*$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _split_sections(md_text: str) -> list:
    """[(section_num, title, body_lines), ...] по заголовкам '## N.N Title'."""
    sections, cur = [], None
    for line in md_text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            cur = {"num": m.group(1), "title": m.group(2), "lines": []}
            sections.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    return sections


def _voorbeelden_lines(body_lines: list) -> list:
    """Буллеты блока 'Voorbeelden uit oefeningen' секции."""
    out, collecting = [], False
    for line in body_lines:
        s = line.strip()
        if s.startswith("###"):
            collecting = s.lower().startswith("### voorbeelden")
            continue
        if collecting and s.startswith("- "):
            out.append(s[2:].strip())
    return out


def parse_grammar_clozes(md_text: str, modules, prefix: str) -> tuple:
    items, skipped = [], []
    for sec in _split_sections(md_text):
        if modules != "all" and sec["num"] not in modules:
            continue
        examples = _voorbeelden_lines(sec["lines"])
        made = 0
        for ex in examples:
            m = _BOLD_RE.search(ex)
            if not m:
                continue
            answer = m.group(1)
            content = (ex[:m.start()] + "___" + ex[m.end():]).strip()
            made += 1
            items.append({
                "item_id": f"{prefix}gram_{sec['num']}_{made}",
                "item_type": "grammar_rule",
                "content": f"{content} ({sec['title']})",
                "answer": answer,
                "priority": "medium",
            })
        if made == 0:
            skipped.append(f"{sec['num']} {sec['title']}")
    return items, skipped


def grammar_items(course: str, unit: dict, gramatica_dir: Path) -> tuple:
    num = unit["id"].split("_")[-1]
    prefix = unit_prefix(course, unit["id"])
    md = (gramatica_dir / unit["grammar_file"]).read_text(encoding="utf-8")
    items, skipped = parse_grammar_clozes(md, unit.get("grammar_modules", "all"), prefix)
    for it in items:
        it["category"] = f"grammar_thema{num}"
    return items, skipped

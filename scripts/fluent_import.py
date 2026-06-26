#!/usr/bin/env python3
"""Импорт лексики/грамматики активной темы курса в spaced-repetition Fluent."""
import argparse
import json
import os
import re
import shutil
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


def save_manifest(course_dir: Path, manifest: dict) -> None:
    tmp = course_dir / "curriculum.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(course_dir / "curriculum.json")


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
        if s.startswith("##"):
            break  # граница секции — дальше не собираем
        if collecting and s.startswith("- "):
            out.append(s[2:].strip())
    return out


def parse_grammar_clozes(md_text: str, modules, prefix: str) -> tuple:
    items, skipped = [], []
    for sec in _split_sections(md_text):
        if modules != "all" and sec["num"] not in modules:
            continue
        examples = _voorbeelden_lines(sec["lines"])
        idx = 0
        for ex in examples:
            m = _BOLD_RE.search(ex)
            if not m:
                continue
            answer = m.group(1)
            content = (ex[:m.start()] + "___" + ex[m.end():]).strip()
            idx += 1
            items.append({
                "item_id": f"{prefix}gram_{sec['num']}_{idx}",
                "item_type": "grammar_rule",
                "content": f"{content} ({sec['title']})",
                "answer": answer,
                "priority": "medium",
            })
        if idx == 0:
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


def new_sr_item(item: dict, today: str) -> dict:
    return {
        "id": item["item_id"],
        "type": item.get("item_type", "vocabulary"),
        "content": item.get("content", ""),
        "answer": item.get("answer", ""),
        "category": item.get("category", ""),
        "difficulty": "",
        "created_date": today,
        "due_date": tomorrow(today),
        "interval_days": 1,
        "repetitions": 0,
        "easiness_factor": 2.5,
        "consecutive_correct": 0,
        "consecutive_incorrect": 0,
        "last_reviewed": today,
        "last_quality": 3,
        "mastery_level": 0,
        "total_reviews": 0,
        "priority": item.get("priority", "medium"),
    }


def add_items(sr: dict, items: list, today: str) -> int:
    store = sr.setdefault("items", {})
    added = 0
    for it in items:
        if it["item_id"] not in store:
            store[it["item_id"]] = new_sr_item(it, today)
            added += 1
    return added


def rebuild_queue(sr: dict, today: str) -> None:
    items = sr.setdefault("items", {})
    q = {"today": [], "tomorrow": [], "this_week": [], "later": []}
    tom = tomorrow(today)
    week_end = date_plus_days(today, 7)
    for item_id, item in items.items():
        due = item.get("due_date", today)
        if due <= today:
            q["today"].append(item_id)
        elif due == tom:
            q["tomorrow"].append(item_id)
        elif due <= week_end:
            q["this_week"].append(item_id)
        else:
            q["later"].append(item_id)
    sr["review_queue"] = q
    sr.setdefault("metadata", {})["last_updated"] = today
    sr["metadata"]["total_items_tracked"] = len(items)


def write_sr(sr: dict, sr_path: Path) -> None:
    if sr_path.exists():
        stamp = today_str() + datetime.now().strftime("-%H%M%S")
        backup_dir = sr_path.parent / ".backups" / f"pre-import-{stamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sr_path, backup_dir / sr_path.name)
    tmp = sr_path.with_name(f"{sr_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(sr, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(sr_path)


MASTERY_THRESHOLD = 0.80


def check(course: str, repo_root: Path, sr_path: Path) -> dict:
    manifest = load_manifest(repo_root / course)
    unit = active_unit(manifest)
    prefix = unit_prefix(course, unit["id"])
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    unit_items = [it for i, it in sr.get("items", {}).items() if i.startswith(prefix)]
    total = len(unit_items)
    mastered = sum(1 for it in unit_items if it.get("mastery_level", 0) >= 3)
    red = sum(1 for it in unit_items if it.get("consecutive_incorrect", 0) >= 2)
    pct = (mastered / total) if total else 0.0
    ready = total > 0 and pct >= MASTERY_THRESHOLD and red == 0
    mark = "✅ готов дальше — запусти --advance" if ready else "⏳ продолжай"
    report = (f"{unit['id']} — {total} карточек | mastery≥3: {mastered}/{total} "
              f"({pct:.1%}) | красных: {red}\n{mark}")
    return {"unit": unit["id"], "total": total, "mastered": mastered,
            "red": red, "ready": ready, "report": report}


def fluent_data_dir() -> Path:
    return Path.home() / ".claude" / "fluent-data"


def do_import(course: str, repo_root: Path, sr_path: Path, today: str) -> dict:
    course_dir = repo_root / course
    manifest = load_manifest(course_dir)
    unit = active_unit(manifest)
    vocab = vocab_items(course, unit, course_dir)
    grammar, skipped = grammar_items(course, unit, course_dir / "gramatica")
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    added = add_items(sr, vocab + grammar, today)
    rebuild_queue(sr, today)
    write_sr(sr, sr_path)
    return {"unit": unit["id"], "vocab": len(vocab), "grammar": len(grammar),
            "added": added, "skipped": skipped}


def advance(course: str, repo_root: Path, sr_path: Path, today: str) -> dict:
    course_dir = repo_root / course
    manifest = load_manifest(course_dir)
    units = manifest["units"]
    idx = next(i for i, u in enumerate(units) if u.get("status") == "active")
    if idx + 1 >= len(units):
        raise ValueError("course complete — нет следующего юнита")
    units[idx]["status"] = "done"
    units[idx + 1]["status"] = "active"
    save_manifest(course_dir, manifest)
    return do_import(course, repo_root, sr_path, today)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Curriculum → Fluent bridge")
    ap.add_argument("--course", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--advance", action="store_true")
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    sr_path = fluent_data_dir() / "spaced-repetition.json"
    today = today_str()

    if args.check:
        print(check(args.course, repo_root, sr_path)["report"])
        return
    if args.advance:
        s = advance(args.course, repo_root, sr_path, today)
        print(f"→ active: {s['unit']} | added {s['added']}")
        return
    s = do_import(args.course, repo_root, sr_path, today)
    print(f"Импорт {s['unit']}: лексика {s['vocab']}, грамматика {s['grammar']}, "
          f"новых {s['added']}")
    if s["skipped"]:
        print("Пропущены модули без жирных примеров: " + "; ".join(s["skipped"]))


if __name__ == "__main__":
    main()

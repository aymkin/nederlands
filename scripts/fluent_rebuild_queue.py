#!/usr/bin/env python3
"""Пересобрать бакеты review_queue под сегодняшнюю дату.

ЗАЧЕМ. `read-db.py --review` подаёт СОХРАНЁННЫЙ список
`review_queue.today` — он его только сортирует по priority и режет по
`daily_limits`, но не перестраивает. Бакеты перестраивает исключительно
`update-db.py`, и только в конце сессии.

Отсюда однодневный лаг: карточка с `due_date` = завтра лежит в бакете
`tomorrow` и переедет в `today` лишь после того, как завтрашняя сессия
ЗАКОНЧИТСЯ. То есть подадут её послезавтра. Правило дня приходит на день
позже назначенного — систематически, а не иногда.

Скрипт закрывает разрыв: гонять в начале сессии, рядом с
`anki_vandaag.py`.

    python3 scripts/anki_vandaag.py --out private/frequentie/vandaag.md
    python3 scripts/fluent_rebuild_queue.py --apply

Бакетинг здесь не свой: `rebuild_queue` импортируется из
`fluent_import.py`, чтобы в репозитории жила одна реализация правил
today/tomorrow/this_week/later, а не третья копия (вторая — в
`.claude/skills/fluent-backlog-campaign/scripts/defer_dues.py`).

БЕЗОПАСНОСТЬ:
  - dry-run по умолчанию, запись только по `--apply`;
  - если бакеты уже совпадают с расчётными — не пишет ничего и не делает
    бэкап (обычный день сразу после сессии — no-op);
  - перед записью снимает бэкап в `.backups/pre-rebuild-<timestamp>/`;
  - атомарная запись (tmp + os.replace);
  - трогает только `review_queue` и `metadata` — расписание FSRS
    (`due_date`, `stability`, `repetitions`, `mastery_level`) не
    пересчитывается и не читается никем, кроме бакетизатора.

Только stdlib.
"""
import argparse
import copy
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fluent_import as fi  # noqa: E402  — только ради rebuild_queue

BUCKETS = ("today", "tomorrow", "this_week", "later")


def plan(sr: dict, today: str):
    """Вернуть (было, станет, изменилось ли). Входной sr не мутируется."""
    before = {b: list(sr.get("review_queue", {}).get(b, [])) for b in BUCKETS}
    probe = copy.deepcopy(sr)
    fi.rebuild_queue(probe, today)
    after = {b: list(probe["review_queue"][b]) for b in BUCKETS}
    return before, after, before != after


def moved_into_today(before: dict, after: dict) -> list:
    """Карточки, которые попадут в подачу только после ребилда."""
    was = set(before["today"])
    return [i for i in after["today"] if i not in was]


def apply_rebuild(sr: dict, sr_path: Path, today: str) -> Path:
    """Бэкап, ребилд, атомарная запись. Возвращает каталог бэкапа."""
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    bdir = sr_path.parent / ".backups" / f"pre-rebuild-{stamp}"
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sr_path, bdir / sr_path.name)

    fi.rebuild_queue(sr, today)

    tmp = sr_path.with_name(f"{sr_path.name}.{os.getpid()}.tmp")
    # без хвостового перевода строки — так пишут update-db.py и defer_dues.py
    tmp.write_text(json.dumps(sr, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(sr_path)
    return bdir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="записать (по умолчанию — сухой прогон)")
    ap.add_argument("--data-dir", default=None,
                    help="каталог Fluent (по умолчанию ~/.claude/fluent-data)")
    ap.add_argument("--date", default=None,
                    help="считать этот день сегодняшним, YYYY-MM-DD")
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else fi.fluent_data_dir()
    sr_path = data_dir / "spaced-repetition.json"
    if not sr_path.exists():
        print(f"нет файла: {sr_path}", file=sys.stderr)
        return 2

    today = args.date or fi.today_str()
    # бакетинг сравнивает даты как строки: не-ISO дата разложит всё молча и неверно
    try:
        datetime.strptime(today, "%Y-%m-%d")
    except ValueError:
        print(f"--date должен быть YYYY-MM-DD, получено: {today}", file=sys.stderr)
        return 2

    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    before, after, changed = plan(sr, today)

    print(f"дата: {today}")
    for b in BUCKETS:
        n, m = len(before[b]), len(after[b])
        mark = "" if n == m else f"  ({m - n:+d})"
        print(f"  {b:10} {n:4} → {m:4}{mark}")

    if not changed:
        print("бакеты уже актуальны — ничего не делаю")
        return 0

    new = moved_into_today(before, after)
    if new:
        print(f"\nвойдут в подачу ({len(new)}):")
        for i in new:
            item = sr.get("items", {}).get(i, {})
            print(f"  {i:44} due={item.get('due_date')} "
                  f"prio={item.get('priority')}")

    if not args.apply:
        print("\nсухой прогон — повтори с --apply, чтобы записать")
        return 0

    bdir = apply_rebuild(sr, sr_path, today)
    print(f"\nзаписано | бэкап: {bdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

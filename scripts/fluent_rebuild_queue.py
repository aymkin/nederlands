#!/usr/bin/env python3
"""Подготовить очередь Fluent к сессии: приоритеты правил и бакеты.

Главное — приоритеты карточек правил (`gram_lp_*`, `gram_sk_*`):
`read-db.py --review` берёт в раунд срочные карточки по `priority`, затем по
самой старой дате, и режет по потолку сессии. Правило с `high` тонет за
просроченными карточками, а `critical` не снимается само. Расстановка —
`grammatica_fluent.prioriteit()`: одно новое правило в день на профиль, один
повтор проваленного, остальные — `high`.

Бакеты `review_queue` пересобираются для сводок; подачу Fluent 0.6.0+ берёт
прямо из карточек. Бакетинг — из `fluent_import.py`, одна реализация на
репозиторий. Расписание FSRS не трогается. Гонять в начале сессии, следом за
`anki_vandaag.py`. Подробности — `scripts/README.md`.
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fluent_import as fi  # noqa: E402  — только ради rebuild_queue
import grammatica_fluent as gf  # noqa: E402  — только ради prioriteit


def iso(s: str) -> str:
    """Бакетинг сравнивает даты как строки: не-ISO разложит всё молча и неверно."""
    return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="записать (по умолчанию — сухой прогон)")
    ap.add_argument("--data-dir",
                    help="каталог Fluent (по умолчанию ~/.claude/fluent-data)")
    ap.add_argument("--date", type=iso,
                    help="считать этот день сегодняшним, YYYY-MM-DD")
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else fi.fluent_data_dir()
    sr_path = data_dir / "spaced-repetition.json"
    if not sr_path.exists():
        print(f"нет файла: {sr_path}", file=sys.stderr)
        return 2

    today = args.date or fi.today_str()
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    before = sr.get("review_queue", {})
    fi.rebuild_queue(sr, today)   # присваивает новый dict — before остаётся прежним
    after = sr["review_queue"]
    wijzigingen = gf.prioriteit(sr, today)

    print(f"дата: {today}")
    for bucket, ids in after.items():
        was, now = len(before.get(bucket, [])), len(ids)
        delta = "" if was == now else f"  ({now - was:+d})"
        print(f"  {bucket:10} {was:4} → {now:4}{delta}")
    if wijzigingen:
        print("приоритеты правил:")
        for iid, oud, nieuw in wijzigingen:
            print(f"  {iid:15} {oud or '—'} → {nieuw}")

    if before == after and not wijzigingen:
        print("бакеты и приоритеты уже актуальны — ничего не делаю")
        return 0
    if not args.apply:
        print("сухой прогон — повтори с --apply, чтобы записать")
        return 0

    bdir = sr_path.parent / ".backups" / f"pre-rebuild-{datetime.now():%Y-%m-%d-%H%M%S}"
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sr_path, bdir / sr_path.name)

    tmp = sr_path.with_name(f"{sr_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(sr, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(sr_path)
    print(f"записано | бэкап: {bdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

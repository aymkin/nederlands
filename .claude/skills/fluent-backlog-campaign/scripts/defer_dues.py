#!/usr/bin/env python3
"""Defer (push forward) due_dates of selected Fluent SR items — triage
option (b) of the fluent-backlog-campaign skill.

DRY-RUN BY DEFAULT: prints what would change and exits without writing.
Pass --apply to write. On --apply it:
  1. backs up spaced-repetition.json to
     ~/.claude/fluent-data/.backups/pre-defer-<YYYY-MM-DD-HHMMSS>/
  2. sets due_date = today + --days for every DUE item whose id starts
     with one of --prefix (repeatable)
  3. rebuilds review_queue buckets exactly like
     scripts/fluent_import.py:rebuild_queue (today/tomorrow/this_week/
     later) so read-db.py --review serves the new reality
  4. atomic write (tmp + os.replace)

Safety rails:
  - never touches items with consecutive_incorrect >= 2 (red cards must
    be reviewed, not hidden)
  - never touches items that are not yet due
  - refuses to run without at least one --prefix
  - stdlib only; owns no scheduling math — a deferral is an explicit,
    documented intervention, reversible from the backup

Usage:
  python3 defer_dues.py --prefix link_t4_ --prefix link_t12_ --days 14
  python3 defer_dues.py --prefix vocab_ --days 90 --apply
"""
import argparse
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix", action="append", required=True,
                    help="item_id prefix to defer (repeatable)")
    ap.add_argument("--days", type=int, required=True,
                    help="push due_date to today + N days")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default: dry-run)")
    ap.add_argument("--data-dir",
                    default=str(Path.home() / ".claude" / "fluent-data"))
    args = ap.parse_args()

    sr_path = Path(args.data_dir) / "spaced-repetition.json"
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    items = sr.get("items", {})
    today = datetime.now().strftime("%Y-%m-%d")
    new_due = (datetime.now() + timedelta(days=args.days)).strftime("%Y-%m-%d")

    deferred, skipped_red = [], []
    for iid, item in items.items():
        if not any(iid.startswith(p) for p in args.prefix):
            continue
        if item.get("due_date", today) > today:
            continue  # not due — leave scheduling alone
        if item.get("consecutive_incorrect", 0) >= 2:
            skipped_red.append(iid)
            continue  # red card: must be reviewed, not hidden
        deferred.append(iid)

    print(f"due items matching {args.prefix}: {len(deferred)} "
          f"-> due_date {new_due} (+{args.days}d)")
    if skipped_red:
        print(f"SKIPPED {len(skipped_red)} red cards (consecutive_incorrect"
              f">=2): {', '.join(sorted(skipped_red)[:5])} ...")
    if not args.apply:
        print("dry-run only — re-run with --apply to write")
        return

    # backup all-or-nothing snapshot of the one file we touch
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    bdir = sr_path.parent / ".backups" / f"pre-defer-{stamp}"
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sr_path, bdir / sr_path.name)

    for iid in deferred:
        items[iid]["due_date"] = new_due

    # rebuild queue exactly like fluent_import.rebuild_queue
    q = {"today": [], "tomorrow": [], "this_week": [], "later": []}
    tom = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    week_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    for iid, item in items.items():
        due = item.get("due_date", today)
        if due <= today:
            q["today"].append(iid)
        elif due == tom:
            q["tomorrow"].append(iid)
        elif due <= week_end:
            q["this_week"].append(iid)
        else:
            q["later"].append(iid)
    sr["review_queue"] = q
    sr.setdefault("metadata", {})["last_updated"] = today
    sr["metadata"]["total_items_tracked"] = len(items)

    tmp = sr_path.with_name(f"{sr_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(sr, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(sr_path)
    print(f"applied: {len(deferred)} deferred | backup: {bdir}")
    print("queue rebuilt:", {k: len(v) for k, v in q.items()})


if __name__ == "__main__":
    main()

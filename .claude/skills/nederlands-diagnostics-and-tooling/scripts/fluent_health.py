#!/usr/bin/env python3
"""One-shot health dashboard for the Fluent spaced-repetition database.

Read-only. Stdlib only. Reads:
  ~/.claude/fluent-data/spaced-repetition.json
  ~/.claude/fluent-data/session-log.json

Reports: item count, queue bucket sizes (with staleness check against
recomputed due dates), per-prefix census (voc/gram split), mastery
histogram, red cards, the two-review_history-keys trap (top-level legacy
list vs per-item sum), daily_limits, scheduler metadata, days since last
session, and a backlog burn-down estimate at the current daily cap.

Usage:
    python3 fluent_health.py [--data-dir DIR]

Exit code 0 always (it is a dashboard, not a gate).
"""
import argparse
import collections
import json
import math
import re
from datetime import date, datetime
from pathlib import Path

PREFIX_RE = re.compile(r"^([a-z_]+_t\d+)_(voc|gram)_")


def classify(item_id: str):
    m = PREFIX_RE.match(item_id)
    if m:
        return m.group(1) + "_", m.group(2)
    if item_id.startswith("vocab_"):
        return "vocab_* (legacy)", "voc"
    return "error-pattern/other", "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir",
                    default=str(Path.home() / ".claude" / "fluent-data"))
    args = ap.parse_args()
    data = Path(args.data_dir)

    sr = json.loads((data / "spaced-repetition.json").read_text("utf-8"))
    items = sr.get("items", {})
    meta = sr.get("metadata", {})
    today = date.today().isoformat()

    print(f"=== Fluent health — {today} ===")
    print(f"data dir: {data}")

    # --- metadata / scheduler state ---
    print("\n[scheduler metadata]")
    for k in ("scheduler", "algorithm", "target_retention", "weights",
              "last_optimized", "reviews_at_last_optimize",
              "total_items_tracked", "last_updated"):
        if k in meta:
            print(f"  {k}: {meta[k]}")
    if meta.get("weights") is None:
        print("  -> weights null: FSRS hook falls back to DEFAULT_W "
              "(built-in defaults; personal optimizer has not fired)")
    if meta.get("total_items_tracked") != len(items):
        print(f"  !! total_items_tracked ({meta.get('total_items_tracked')}) "
              f"!= actual items ({len(items)}) — stale metadata")

    # --- items & queue ---
    q = sr.get("review_queue", {})
    print(f"\n[items] {len(items)} items")
    print("[queue buckets]")
    for b in ("today", "tomorrow", "this_week", "later"):
        print(f"  {b}: {len(q.get(b, []))}")
    actually_due = sum(1 for it in items.values()
                       if it.get("due_date", today) <= today)
    q_today = len(q.get("today", []))
    print(f"  recomputed due<=today from items: {actually_due}")
    if actually_due != q_today:
        print(f"  !! queue.today ({q_today}) != recomputed due "
              f"({actually_due}) — queue is STALE (rebuilt only on "
              "import/update, not nightly)")

    # --- daily limits & burn-down ---
    cap = sr.get("daily_limits", {}).get("review_items_per_day", 20)
    print(f"\n[daily_limits] review_items_per_day = {cap} "
          "(code default is 20 if key missing; cap is PROMPT-enforced only)")
    if cap > 0:
        base_days = math.ceil(actually_due / cap)
        inflow = len(q.get("tomorrow", [])) + len(q.get("this_week", []))
        print(f"[burn-down] {actually_due} due / {cap} per day = "
              f"{base_days} review days minimum;")
        print(f"  plus {inflow} more coming due within 7 days -> "
              f"~{math.ceil((actually_due + inflow) / cap)} days "
              "(optimistic: ignores lapses re-entering the queue)")

    # --- prefix census ---
    print("\n[prefix census]  (voc = vocabulary, gram = grammar cloze)")
    census = collections.defaultdict(lambda: collections.Counter())
    for iid in items:
        pref, kind = classify(iid)
        census[pref][kind] += 1
    for pref in sorted(census):
        c = census[pref]
        total = sum(c.values())
        detail = " + ".join(f"{n} {k}" for k, n in sorted(c.items()))
        print(f"  {pref:<24} {total:>4}  ({detail})")

    # --- mastery & red cards ---
    hist = collections.Counter(it.get("mastery_level", 0)
                               for it in items.values())
    print("\n[mastery histogram]  (gate needs level>=3 on 80% of a unit)")
    for lvl in sorted(hist):
        print(f"  level {lvl}: {hist[lvl]}")
    red = [iid for iid, it in items.items()
           if it.get("consecutive_incorrect", 0) >= 2]
    print(f"[red cards] consecutive_incorrect>=2: {len(red)}"
          + (f"  -> {', '.join(sorted(red)[:8])}" if red else ""))

    # --- the two review_history keys trap ---
    top_hist = len(sr.get("review_history", []))
    per_item = sum(len(it.get("review_history", []))
                   for it in items.values())
    print(f"\n[review_history] top-level key: {top_hist} entries "
          f"(LEGACY, expected empty) | per-item sum: {per_item} (REAL)")
    if top_hist:
        print("  !! top-level review_history is non-empty — something "
              "wrote to the legacy key; investigate before trusting counts")
    print("  -> always count reviews per-item; the optimizer guard "
          "(>=400) counts per-item too")

    # --- sessions ---
    try:
        sl = json.loads((data / "session-log.json").read_text("utf-8"))
        sessions = sl.get("sessions", [])
        print(f"\n[sessions] {len(sessions)} total")
        if sessions:
            last = sessions[-1]
            last_date = last.get("date", "?")
            try:
                delta = (date.today()
                         - datetime.strptime(last_date, "%Y-%m-%d").date())
                days = delta.days
            except ValueError:
                days = "?"
            print(f"  last: {last.get('session_id')} on {last_date} "
                  f"({days} days ago), accuracy "
                  f"{last.get('accuracy', '?')}")
    except FileNotFoundError:
        print("\n[sessions] session-log.json not found")

    # --- optimizer readiness ---
    print(f"\n[optimizer] guard: needs >=400 per-item reviews AND >=50 new "
          f"since last optimize; current {per_item}/400, "
          f"+{per_item - meta.get('reviews_at_last_optimize', 0)} new")


if __name__ == "__main__":
    main()

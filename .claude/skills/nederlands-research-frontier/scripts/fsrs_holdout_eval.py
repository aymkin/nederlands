#!/usr/bin/env python3
"""Held-out evaluation harness for FSRS weight vectors (CANDIDATE tool).

Status: research-frontier candidate, not an accepted production tool.
It answers ONE question: on a chronological held-out slice of this
learner's real reviews, does weight vector W predict recall better than
another vector? Run it twice (DEFAULT_W vs fitted) and compare log-loss.

Read-only: never writes to ~/.claude/fluent-data/.

Method
  - Replay each item's review_history chronologically with fsrs.py
    (imported from the live plugin cache, so the exact production
    formulas are used — no re-implementation drift).
  - For every review after an item's first, with elapsed >= 1 day,
    prediction p = retrievability(elapsed, stability_so_far, W).
    Label y = 1 if quality >= 3 else 0 (same fail boundary as the
    optimizer's _rating(): quality < 3 maps to rating 1 = Again).
  - State replay always uses ALL reviews (state is not leakage — it is
    the information the scheduler legitimately has at prediction time).
    Only predictions dated >= --split-date are SCORED as held-out.
  - Same-day repeats (elapsed 0) are skipped: fsrs.py is day-granular
    and predicts p=1.0 there, which would blow up log-loss.

Caveats (do not oversell results)
  - First reviews are never scored: with N items reviewed ~once, the
    scorable set is far smaller than total reviews. Check `scored` in
    the output before drawing conclusions.
  - One learner, one period. A win here is personalization evidence,
    not a general FSRS claim.
  - Baselines printed: base-rate predictor (constant p = train-slice
    recall rate) — any weight vector must beat that to mean anything.

Usage
  python3 fsrs_holdout_eval.py --split-date 2026-07-01
  python3 fsrs_holdout_eval.py --split-date 2026-07-01 \
      --weights '[0.2,1.3,...21 floats...]'
  python3 fsrs_holdout_eval.py --split-date 2026-07-01 \
      --weights-file fitted.json
"""
import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path

DATA = Path(os.path.expanduser("~/.claude/fluent-data/spaced-repetition.json"))
CACHE_GLOB = os.path.expanduser("~/.claude/plugins/cache/m98/fluent/*/.claude/hooks")

EPS = 1e-6  # clamp p into (EPS, 1-EPS) for log-loss


def import_fsrs():
    hooks = sorted(glob.glob(CACHE_GLOB))
    if not hooks:
        sys.exit(f"no plugin cache hooks dir matches {CACHE_GLOB}")
    sys.path.insert(0, hooks[-1])  # highest version
    import fsrs  # noqa
    return fsrs


def replay(items, fsrs_mod, w):
    """Yield (date, p_predicted, y_actual) for every scorable review."""
    from datetime import date as _date

    for _id, card in items.items():
        history = sorted(card.get("review_history", []),
                         key=lambda e: e["date"])
        state = {"stability": None, "difficulty": None,
                 "last_reviewed": None}
        for e in history:
            q = e.get("quality", 3)
            rating = 1 if q < 3 else 2 if q == 3 else 3 if q == 4 else 4
            if state["stability"] is not None:
                elapsed = (_date.fromisoformat(e["date"])
                           - _date.fromisoformat(state["last_reviewed"])).days
                if elapsed >= 1:
                    p = fsrs_mod.retrievability(
                        elapsed, state["stability"], w)
                    yield e["date"], p, 1 if q >= 3 else 0
            nxt = fsrs_mod.schedule(state, rating, e["date"], weights=w)
            state = {"stability": nxt["stability"],
                     "difficulty": nxt["difficulty"],
                     "last_reviewed": e["date"]}


def score(preds):
    n = len(preds)
    if n == 0:
        return None
    ll = -sum(y * math.log(max(p, EPS))
              + (1 - y) * math.log(max(1 - p, EPS))
              for _, p, y in preds) / n
    rmse = math.sqrt(sum((p - y) ** 2 for _, p, y in preds) / n)
    return {"n": n, "log_loss": ll, "rmse": rmse,
            "mean_p": sum(p for _, p, _ in preds) / n,
            "recall_rate": sum(y for _, _, y in preds) / n}


def main():
    ap = argparse.ArgumentParser(
        description="Held-out log-loss/RMSE for an FSRS weight vector")
    ap.add_argument("--split-date", required=True,
                    help="reviews on/after this date are the held-out set")
    ap.add_argument("--weights", help="JSON list of 21 floats")
    ap.add_argument("--weights-file",
                    help="JSON file containing a list of 21 floats")
    args = ap.parse_args()

    fsrs_mod = import_fsrs()
    w = fsrs_mod.DEFAULT_W
    label = "DEFAULT_W"
    if args.weights or args.weights_file:
        raw = (json.loads(Path(args.weights_file).read_text())
               if args.weights_file else json.loads(args.weights))
        if len(raw) != 21:
            sys.exit(f"expected 21 weights, got {len(raw)}")
        w, label = [float(x) for x in raw], "candidate"

    sr = json.loads(DATA.read_text(encoding="utf-8"))
    preds = list(replay(sr["items"], fsrs_mod, w))
    train = [p for p in preds if p[0] < args.split_date]
    held = [p for p in preds if p[0] >= args.split_date]

    total_reviews = sum(len(c.get("review_history", []))
                        for c in sr["items"].values())
    print(f"weights: {label}")
    print(f"total per-item reviews: {total_reviews}; "
          f"scorable predictions: {len(preds)} "
          f"(train {len(train)} / held-out {len(held)})")
    for name, part in (("train", train), ("held-out", held)):
        s = score(part)
        if s is None:
            print(f"{name}: EMPTY — adjust --split-date")
            continue
        print(f"{name}: n={s['n']} log_loss={s['log_loss']:.4f} "
              f"rmse={s['rmse']:.4f} mean_p={s['mean_p']:.3f} "
              f"actual_recall={s['recall_rate']:.3f}")
    if train:
        base = sum(y for _, _, y in train) / len(train)
        base = min(max(base, EPS), 1 - EPS)
        held_base = [(d, base, y) for d, _, y in held]
        s = score(held_base)
        if s:
            print(f"baseline (constant p={base:.3f} from train): "
                  f"held-out log_loss={s['log_loss']:.4f} "
                  f"rmse={s['rmse']:.4f}")


if __name__ == "__main__":
    main()

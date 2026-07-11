# FSRS-6 Scheduler + Guarded Weight Optimizer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Fluent plugin's SM-2 scheduler with a stdlib FSRS-6 port,
migrate existing cards, and add a weekly guarded offline optimizer that re-fits
FSRS-6 weights once enough review data accrues.

**Architecture:** The runtime hook stays stdlib-only: a new `fsrs.py` module
does FSRS-6 forward math; `update-db.py` calls it with weights read from
`spaced_repetition.metadata`. A one-time migration seeds
`stability`/`difficulty` from current intervals. An offline optimizer (separate
venv, `fsrs-optimizer`) runs weekly via a LaunchAgent but no-ops until ≥400
reviews exist, writing new weights back to metadata. All code lives on a fork of
`m98/fluent`.

**Tech Stack:** Python 3 stdlib (hook), `py-fsrs` (dev cross-check only),
`fsrs-optimizer` + `torch` (offline venv only), macOS `launchd`, `gh` CLI.

## Global Constraints

- **Runtime hooks are stdlib-only.** `fsrs.py`, `update-db.py`,
  `migrate_to_fsrs.py`, and the stdlib parts of `optimize_weights.py` must
  import nothing outside the Python 3 standard library.
- **Do not hand-transcribe FSRS weights or formulas.** `DEFAULT_W` is extracted
  programmatically from a pinned `py-fsrs`; the cross-check test is the
  correctness gate.
- **FSRS version is FSRS-6** (21 parameters) for both scheduler and optimizer.
- **Source of truth is the fork**, not the upstream marketplace clone.
- **No attribution footers in commit messages** (no "Generated with", etc.).
- **Back up all six DBs before any write** to the data dir (reuse the plugin's
  existing backup helper).
- **`git` never runs interactive flags** (`-i`); use `gh` for GitHub ops.

## Paths (resolve once, reuse everywhere)

- **DEV** (fork working copy): `~/Projects/fluent`
- **MARKETPLACE** (Claude's tracked clone): `~/.claude/plugins/marketplaces/m98`
- **CACHE** (what Claude executes): `~/.claude/plugins/cache/m98/fluent/0.3.0`
- **DATA** (the six DB JSON files): `~/.claude/fluent-data`
- **HOOKS** (inside DEV): `~/Projects/fluent/.claude/hooks`

## File Structure

| File                                            | Repo       | Responsibility                             |
| ----------------------------------------------- | ---------- | ------------------------------------------ |
| `.claude/hooks/fsrs.py`                         | fork       | FSRS-6 forward math + `schedule()` (new)   |
| `.claude/hooks/update-db.py`                    | fork       | call `fsrs.schedule` in review loop (edit) |
| `.claude/hooks/migrate_to_fsrs.py`              | fork       | one-time S/D backfill (new)                |
| `.claude/hooks/optimize_weights.py`             | fork       | offline weekly optimizer (new)             |
| `tests/test_fsrs.py`                            | fork       | FSRS invariants (new, stdlib)              |
| `tests/test_fsrs_crosscheck.py`                 | fork       | numeric parity vs py-fsrs (new, dev)       |
| `tests/test_optimize_weights.py`                | fork       | optimizer guard + extract (new)            |
| `tests/test_update_db.py`                       | fork       | extend for FSRS fields (edit)              |
| `CHANGELOG.md`                                  | fork       | one `### Changed` entry (edit)             |
| `scripts/fluent_import.py`                      | nederlands | new-card `stability/difficulty` (edit)     |
| `launchd/com.aymkin.fluent-fsrs-optimize.plist` | dotfiles   | weekly job (new)                           |

---

# Phase 1 — FSRS-6 scheduler live (immediately useful)

## Task 1: Fork the plugin and set up the dev clone

**Files:** none edited; repo/remote setup only.

**Interfaces:**

- Produces: a fork `github.com/<you>/fluent`, a dev clone at `~/Projects/fluent`
  on branch `fsrs` with `upstream` = `m98/fluent`, baseline tests green.

- [ ] **Step 1: Fork upstream to your account**

```bash
gh repo fork m98/fluent --clone=false
```

Expected: prints "Created fork <you>/fluent" (or "already exists").

- [ ] **Step 2: Clone the fork to the dev path and add upstream**

```bash
git clone "git@github.com:$(gh api user -q .login)/fluent.git" ~/Projects/fluent
cd ~/Projects/fluent
git remote add upstream git@github.com:m98/fluent.git
git checkout -b fsrs
```

Expected: on branch `fsrs`, `git remote -v` shows `origin`=fork,
`upstream`=m98/fluent.

- [ ] **Step 3: Verify baseline tests pass (pre-change green)**

Run: `cd ~/Projects/fluent && python3 tests/test_update_db.py` Expected: `OK`
(all existing tests pass before we touch anything).

- [ ] **Step 4: Commit the branch marker (empty tree change is fine to skip)**

No commit yet — code tasks below commit their own work. Proceed to Task 2.

## Task 2: `fsrs.py` — FSRS-6 forward math (stdlib), gated by cross-check

**Files:**

- Create: `~/Projects/fluent/.claude/hooks/fsrs.py`
- Test: `~/Projects/fluent/tests/test_fsrs.py`,
  `~/Projects/fluent/tests/test_fsrs_crosscheck.py`

**Interfaces:**

- Produces:
  - `DEFAULT_W: list[float]` (21 FSRS-6 params)
  - `TARGET_RETENTION: float`
  - `retrievability(elapsed_days: float, stability: float, w=DEFAULT_W) -> float`
  - `interval_from_stability(stability: float, w=DEFAULT_W) -> float`
  - `schedule(item: dict, rating: int, today: str, weights: list | None = None) -> dict`
    returning keys `stability, difficulty, interval_days, due_date`.
  - `item` uses `stability`, `difficulty`, `last_reviewed` ("YYYY-MM-DD").

- [ ] **Step 1: Create a dev venv and pin py-fsrs; extract DEFAULT_W**

```bash
python3 -m venv ~/Projects/fluent/.devvenv
~/Projects/fluent/.devvenv/bin/pip install -q "fsrs>=5,<7"
~/Projects/fluent/.devvenv/bin/python - <<'PY'
import fsrs, inspect
# Print the exact pinned version and the 21 default parameters.
print("VERSION", fsrs.__version__)
try:
    from fsrs import Scheduler
    print("PARAMS", list(Scheduler().parameters))
except Exception:
    from fsrs import DEFAULT_PARAMETERS
    print("PARAMS", list(DEFAULT_PARAMETERS))
PY
```

Expected: one `VERSION x.y.z` line and one `PARAMS [ ... 21 floats ... ]` line.
Record both — the floats become `DEFAULT_W`, the version goes in the PIN
comment.

- [ ] **Step 2: Write the failing invariant test**

Create `tests/test_fsrs.py`:

```python
#!/usr/bin/env python3
"""Invariant tests for the stdlib FSRS-6 port. Run: python3 tests/test_fsrs.py"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
import fsrs


class TestFsrsInvariants(unittest.TestCase):
    def test_retrievability_at_stability_is_target(self):
        # R(t=S) must equal the target retention (~0.90).
        self.assertAlmostEqual(fsrs.retrievability(10.0, 10.0), 0.90, places=2)

    def test_interval_equals_stability_at_target(self):
        self.assertAlmostEqual(fsrs.interval_from_stability(10.0), 10.0, delta=0.5)

    def test_good_review_grows_stability(self):
        item = {"stability": 10.0, "difficulty": 5.0, "last_reviewed": "2026-07-01"}
        out = fsrs.schedule(item, rating=3, today="2026-07-11")
        self.assertGreater(out["stability"], 10.0)
        self.assertGreaterEqual(out["interval_days"], 1)

    def test_again_shrinks_stability_and_short_interval(self):
        item = {"stability": 10.0, "difficulty": 5.0, "last_reviewed": "2026-07-01"}
        out = fsrs.schedule(item, rating=1, today="2026-07-11")
        self.assertLess(out["stability"], 10.0)
        self.assertEqual(out["interval_days"], 1)

    def test_difficulty_clamped(self):
        for g in (1, 2, 3, 4):
            item = {"stability": None, "difficulty": None, "last_reviewed": "2026-07-01"}
            out = fsrs.schedule(item, rating=g, today="2026-07-01")
            self.assertGreaterEqual(out["difficulty"], 1.0)
            self.assertLessEqual(out["difficulty"], 10.0)

    def test_new_card_initializes(self):
        item = {"stability": None, "difficulty": None, "last_reviewed": "2026-07-01"}
        out = fsrs.schedule(item, rating=3, today="2026-07-01")
        self.assertIsNotNone(out["stability"])
        self.assertEqual(out["due_date"], "2026-07-01")  # +interval, min 1... see note

    def test_weights_are_used(self):
        item = {"stability": 10.0, "difficulty": 5.0, "last_reviewed": "2026-07-01"}
        base = fsrs.schedule(item, 3, "2026-07-11")
        bumped = list(fsrs.DEFAULT_W)
        bumped[8] += 0.5  # perturb a stability-growth weight
        alt = fsrs.schedule(item, 3, "2026-07-11", weights=bumped)
        self.assertNotAlmostEqual(base["stability"], alt["stability"], places=3)


if __name__ == "__main__":
    unittest.main()
```

Note on `test_new_card_initializes`: a new card's first-review interval is
`max(1, round(interval(S0)))`; the assertion on `due_date` may be `today+1` or
more. Replace the exact `due_date` assert with
`self.assertGreaterEqual(out["interval_days"], 1)` if S0 rounds above 0.

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd ~/Projects/fluent && python3 tests/test_fsrs.py` Expected: FAIL —
`ModuleNotFoundError: No module named 'fsrs'` (the hook module does not exist
yet).

- [ ] **Step 4: Write `fsrs.py` (paste DEFAULT_W from Step 1)**

Create `.claude/hooks/fsrs.py`:

```python
"""FSRS-6 spaced-repetition scheduler — stdlib-only port.

Ported from py-fsrs Scheduler; PINNED fsrs==<VERSION FROM TASK 2 STEP 1>.
DEFAULT_W is the parameter vector printed in that step (do NOT hand-edit).
Correctness gate: tests/test_fsrs_crosscheck.py must match py-fsrs.
"""
import math
from datetime import date, timedelta

# <<< paste the 21 floats printed by Task 2 Step 1 >>>
DEFAULT_W = [ ...21 floats from Step 1... ]

TARGET_RETENTION = 0.90
_S_MIN = 0.01


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _decay(w):
    return -w[20]


def _factor(w):
    d = _decay(w)
    return 0.9 ** (1.0 / d) - 1.0


def retrievability(elapsed_days, stability, w=DEFAULT_W):
    return (1.0 + _factor(w) * elapsed_days / stability) ** _decay(w)


def interval_from_stability(stability, w=DEFAULT_W):
    d = _decay(w)
    return (stability / _factor(w)) * (TARGET_RETENTION ** (1.0 / d) - 1.0)


def _init_stability(w, g):
    return max(w[g - 1], _S_MIN)


def _init_difficulty(w, g):
    return _clamp(w[4] - math.exp(w[5] * (g - 1)) + 1.0, 1.0, 10.0)


def _next_difficulty(w, d, g):
    delta = -w[6] * (g - 3)
    damped = d + delta * (10.0 - d) / 9.0            # linear damping
    reverted = w[7] * _init_difficulty(w, 4) + (1.0 - w[7]) * damped  # -> D0(Easy)
    return _clamp(reverted, 1.0, 10.0)


def _next_stability_recall(w, d, s, r, g):
    hard = w[15] if g == 2 else 1.0
    easy = w[16] if g == 4 else 1.0
    return s * (1.0 + math.exp(w[8]) * (11.0 - d) * (s ** -w[9])
                * (math.exp((1.0 - r) * w[10]) - 1.0) * hard * easy)


def _next_stability_forget(w, d, s, r):
    sf = w[11] * (d ** -w[12]) * ((s + 1.0) ** w[13] - 1.0) * math.exp((1.0 - r) * w[14])
    return min(sf, s)  # a lapse must not increase stability


def _parse(d):
    return date.fromisoformat(d)


def schedule(item, rating, today, weights=None):
    w = weights if weights else DEFAULT_W
    s = item.get("stability")
    d = item.get("difficulty")
    if s is None or d is None:
        # New card: initialize from the first rating.
        s2 = _init_stability(w, rating)
        d2 = _init_difficulty(w, rating)
    else:
        last = item.get("last_reviewed") or today
        elapsed = max((_parse(today) - _parse(last)).days, 0)
        r = retrievability(elapsed, s, w)
        d2 = _next_difficulty(w, d, rating)
        if rating == 1:
            s2 = _next_stability_forget(w, d, s, r)
        else:
            s2 = _next_stability_recall(w, d, s, r, rating)
    s2 = max(s2, _S_MIN)
    interval = max(1, round(interval_from_stability(s2, w)))
    due = _parse(today) + timedelta(days=interval)
    return {
        "stability": round(s2, 4),
        "difficulty": round(d2, 4),
        "interval_days": interval,
        "due_date": due.isoformat(),
    }


if __name__ == "__main__":  # smoke self-check
    assert abs(retrievability(5, 5) - 0.9) < 0.01
    it = {"stability": 5.0, "difficulty": 5.0, "last_reviewed": "2026-01-01"}
    assert schedule(it, 3, "2026-01-06")["stability"] > 5.0
    assert schedule(it, 1, "2026-01-06")["interval_days"] == 1
    print("fsrs.py self-check OK")
```

- [ ] **Step 5: Run invariant tests to verify they pass**

Run: `cd ~/Projects/fluent && python3 tests/test_fsrs.py` Expected: `OK`. If
`test_new_card_initializes` fails on the `due_date` assert, apply the note in
Step 2 and re-run.

- [ ] **Step 6: Write the cross-check test (dev-only, skips without fsrs)**

Create `tests/test_fsrs_crosscheck.py`:

```python
#!/usr/bin/env python3
"""Numeric parity vs py-fsrs. Correctness gate. Run in the dev venv:
   ~/Projects/fluent/.devvenv/bin/python tests/test_fsrs_crosscheck.py"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
import fsrs

try:
    from fsrs import Scheduler, Card, Rating, ReviewLog  # py-fsrs
    from datetime import datetime, timezone, timedelta
    HAVE_FSRS = True
except Exception:
    HAVE_FSRS = False


@unittest.skipUnless(HAVE_FSRS, "py-fsrs not installed (dev-only gate)")
class TestCrossCheck(unittest.TestCase):
    def test_sequences_match_pyfsrs(self):
        sched = Scheduler(desired_retention=fsrs.TARGET_RETENTION)
        for seq in ([3, 3, 3], [3, 1, 3], [2, 3, 4], [4, 4, 1, 3]):
            card = Card()
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            item = {"stability": None, "difficulty": None, "last_reviewed": "2026-01-01"}
            t = "2026-01-01"
            for g in seq:
                card, _ = sched.review_card(card, Rating(g), now)
                out = fsrs.schedule(item, g, t, weights=list(sched.parameters))
                # advance our clock to py-fsrs's next due, capped for the next elapsed
                item = {"stability": card.stability, "difficulty": card.difficulty,
                        "last_reviewed": t}
                self.assertAlmostEqual(out["stability"], card.stability, delta=card.stability * 0.02)
                self.assertGreaterEqual(out["difficulty"], 1.0)
                now = card.due
                t = card.due.date().isoformat()


if __name__ == "__main__":
    unittest.main()
```

Note: py-fsrs's public API varies by version — adjust `review_card`/`Card` field
names to the pinned version (Step 1). The assertion that matters:
`out["stability"]` within 2% of py-fsrs's `card.stability` for each step.

- [ ] **Step 7: Run the cross-check and reconcile until green**

Run: `~/Projects/fluent/.devvenv/bin/python tests/test_fsrs_crosscheck.py`
Expected: `OK`. If any assertion fails, the port has a transcription error —
compare `fsrs.py` line-by-line against the pinned `py-fsrs` `Scheduler` source
(`~/Projects/fluent/.devvenv/lib/python*/site-packages/fsrs/`) and fix `fsrs.py`
(sign, coefficient, or clamp) until parity holds. This is the gate; do not
proceed until it passes.

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/fluent
echo ".devvenv/" >> .gitignore
git add .claude/hooks/fsrs.py tests/test_fsrs.py tests/test_fsrs_crosscheck.py .gitignore
git commit -m "feat(fsrs): stdlib FSRS-6 scheduler port with py-fsrs cross-check"
```

## Task 3: Wire FSRS into `update-db.py` + schema defaults

**Files:**

- Modify: `~/Projects/fluent/.claude/hooks/update-db.py` (review loop ~384;
  new-card defaults ~430 and ~455)
- Test: `~/Projects/fluent/tests/test_update_db.py` (extend)

**Interfaces:**

- Consumes: `fsrs.schedule(item, rating, today, weights)` from Task 2.
- Produces: reviewed items carry `stability`, `difficulty`, `last_rating`;
  `metadata.weights` (if present, 21 floats) is honored.

- [ ] **Step 1: Add the failing assertion to the smoke test**

In `tests/test_update_db.py`, inside the existing post-run assertions on the
spaced-repetition output, add (adapt variable names to the file's fixtures):

```python
# FSRS fields present on a reviewed item
reviewed = sr["items"][REVIEWED_ID]
self.assertIn("stability", reviewed)
self.assertIn("fsrs_difficulty", reviewed)          # NOT "difficulty" (that is CEFR)
self.assertIn("last_rating", reviewed)
self.assertIsInstance(reviewed["stability"], (int, float))
self.assertIsInstance(reviewed["fsrs_difficulty"], (int, float))
# CEFR difficulty must survive untouched (regression for the field collision)
self.assertEqual(reviewed["difficulty"], REVIEWED_CEFR)  # e.g. "A1", unchanged
# due_date is interval_days after the session date
from datetime import date, timedelta
exp = (date.fromisoformat(SESSION_DATE) + timedelta(days=reviewed["interval_days"])).isoformat()
self.assertEqual(reviewed["due_date"], exp)
```

Ensure the fixture session includes a `review_results` entry for `REVIEWED_ID`
with a `score`, and that `REVIEWED_ID`'s fixture item has a CEFR `difficulty`
string (e.g. `"A1"`) so the collision regression is meaningful. If the fixture
lacks either, add it.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/fluent && python3 tests/test_update_db.py` Expected: FAIL —
`KeyError: 'stability'` (the loop still writes SM-2 fields).

- [ ] **Step 3: Import fsrs and replace the review-loop scheduling**

At the top of `update-db.py` (with the other imports, after the `sys.path`
insert that already resolves the hooks dir):

```python
import fsrs
```

In the review loop (currently around line 384, the `if item_id in items:` branch
that calls `calculate_sm2`), replace the block:

```python
            result = calculate_sm2(item, quality)
            item["easiness_factor"] = result["easiness_factor"]
            item["interval_days"] = result["interval_days"]
            item["repetitions"] = result["repetitions"]
            item["due_date"] = date_plus_days(today, result["interval_days"])
```

with:

```python
            weights = sr.get("metadata", {}).get("weights")
            score = review.get("score", quality * 2)
            rating = 1 if score <= 4 else 2 if score <= 6 else 3 if score <= 8 else 4
            # NOTE: the item's "difficulty" key holds the CEFR level string
            # (e.g. "A2") — do NOT overwrite it. FSRS difficulty lives under
            # "fsrs_difficulty". Map to fsrs.schedule's dict interface here.
            fsrs_state = {
                "stability": item.get("stability"),
                "difficulty": item.get("fsrs_difficulty"),
                "last_reviewed": item.get("last_reviewed"),
            }
            r = fsrs.schedule(fsrs_state, rating, today, weights)
            item["stability"] = r["stability"]
            item["fsrs_difficulty"] = r["difficulty"]
            item["interval_days"] = r["interval_days"]
            item["due_date"] = r["due_date"]
            item["last_rating"] = rating
            item["repetitions"] = item.get("repetitions", 0) + 1 if quality >= 3 else 0
```

(Leave the subsequent `last_reviewed`, `last_quality`, `total_reviews`,
`consecutive_*`, `mastery_level`, `priority`, and `review_history` lines
unchanged. `calculate_sm2` stays defined in the file as the rollback branch.
This block must run BEFORE `item["last_reviewed"] = today` so fsrs reads the
prior review date to compute elapsed days.)

- [ ] **Step 4: Add `stability`/`fsrs_difficulty` to new-card defaults**

In the vocabulary new-item dict (~line 430) and the error-pattern new-item dict
(~line 455), add these two keys next to `"easiness_factor": 2.5,` — note it is
`fsrs_difficulty` (NOT `difficulty`, which already holds the CEFR level):

```python
                "stability": None,
                "fsrs_difficulty": None,
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd ~/Projects/fluent && python3 tests/test_update_db.py` Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/fluent
git add .claude/hooks/update-db.py tests/test_update_db.py
git commit -m "feat(fsrs): schedule reviews with FSRS-6; add stability/difficulty to schema"
```

## Task 4: One-time migration `migrate_to_fsrs.py`

**Files:**

- Create: `~/Projects/fluent/.claude/hooks/migrate_to_fsrs.py`
- Test: `~/Projects/fluent/tests/test_optimize_weights.py` is Phase 2; add a
  focused migration test inline here as `tests/test_migrate_to_fsrs.py`.

**Interfaces:**

- Consumes: `spaced-repetition.json` in DATA; the plugin's `ensure_data_dir` /
  `backup` helpers from `fluent_paths` / `update-db.py`.
- Produces: every item gains `stability`/`difficulty` (or stays null if never
  reviewed); `metadata` stamped with the FSRS-6 config, `weights` = null.

- [ ] **Step 1: Write the failing migration test**

Create `tests/test_migrate_to_fsrs.py`:

```python
#!/usr/bin/env python3
"""Run: python3 tests/test_migrate_to_fsrs.py"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
import migrate_to_fsrs as m


class TestSeed(unittest.TestCase):
    def test_reviewed_card_seeded_from_interval(self):
        card = {"interval_days": 48, "easiness_factor": 2.5, "repetitions": 3}
        s, d = m.seed(card)
        self.assertAlmostEqual(s, 48.0, delta=0.5)
        self.assertGreaterEqual(d, 1.0)
        self.assertLessEqual(d, 10.0)

    def test_never_reviewed_card_stays_null(self):
        card = {"interval_days": 1, "easiness_factor": 2.5, "repetitions": 0}
        s, d = m.seed(card)
        self.assertIsNone(s)
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/fluent && python3 tests/test_migrate_to_fsrs.py` Expected:
FAIL — `ModuleNotFoundError: No module named 'migrate_to_fsrs'`.

- [ ] **Step 3: Write `migrate_to_fsrs.py`**

Create `.claude/hooks/migrate_to_fsrs.py`:

```python
#!/usr/bin/env python3
"""One-time SM-2 -> FSRS-6 migration. Idempotent. Backs up before writing.

Usage: python3 .claude/hooks/migrate_to_fsrs.py
Seeds stability/difficulty for reviewed cards; stamps metadata.
"""
import json, os, shutil, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fluent_paths import ensure_data_dir, ensure_backups_dir, force_utf8_io

force_utf8_io()
DATA = ensure_data_dir()
BACKUPS = ensure_backups_dir()
SR_PATH = DATA / "spaced-repetition.json"

DEFAULT_WEIGHTS = None  # optimizer fills this later; hook falls back to fsrs.DEFAULT_W


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def seed(card):
    """Return (stability, fsrs_difficulty), or (None, None) for never-reviewed
    cards. Never-reviewed cards stay null so the first FSRS review initializes
    them. NOTE: the returned difficulty is the FSRS numeric difficulty; it is
    stored under the item key "fsrs_difficulty" (the "difficulty" key already
    holds the CEFR level string and must not be touched)."""
    if card.get("repetitions", 0) <= 0:
        return None, None
    interval = card.get("interval_days", 1)
    ef = card.get("easiness_factor", 2.5)
    stability = max(float(interval), 0.5)
    difficulty = _clamp(10.0 - (ef - 1.3) / 1.4 * 9.0, 1.0, 10.0)
    return round(stability, 4), round(difficulty, 4)


def main():
    if not SR_PATH.exists():
        print("[migrate] no spaced-repetition.json; nothing to do")
        return 0
    sr = json.loads(SR_PATH.read_text(encoding="utf-8"))
    items = sr.get("items", {})

    # backup
    stamp = date.today().isoformat()
    dest = BACKUPS / f"pre-migrate-fsrs-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for f in DATA.glob("*.json"):
        shutil.copy2(f, dest / f.name)

    seeded = 0
    for card in items.values():
        if card.get("stability") is not None:
            continue  # idempotent
        s, d = seed(card)
        if s is not None:
            card["stability"], card["fsrs_difficulty"] = s, d
            seeded += 1
        else:
            card.setdefault("stability", None)
            card.setdefault("fsrs_difficulty", None)

    meta = sr.setdefault("metadata", {})
    meta.update({
        "scheduler": "fsrs-6",
        "target_retention": 0.9,
        "weights": None,
        "last_optimized": None,
        "reviews_at_last_optimize": 0,
    })

    tmp = SR_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, SR_PATH)
    print(f"[migrate] seeded {seeded} cards; backup at {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: the `seed` guard simplifies to "repetitions <= 0 → (None, None)". Keep the
function shape the test asserts; drop the tangled first `if` if it reads
awkwardly — the two `return`s the test checks are what matter.

- [ ] **Step 4: Run the migration test to verify it passes**

Run: `cd ~/Projects/fluent && python3 tests/test_migrate_to_fsrs.py` Expected:
`OK`.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/fluent
git add .claude/hooks/migrate_to_fsrs.py tests/test_migrate_to_fsrs.py
git commit -m "feat(fsrs): one-time SM-2 -> FSRS-6 migration script"
```

## Task 5: New-card defaults in the importer (nederlands repo)

**Files:**

- Modify: `~/Projects/nederlands/scripts/fluent_import.py:new_sr_item`
  (~line 192)

**Interfaces:**

- Produces: items created by the importer carry
  `stability: None, fsrs_difficulty: None`, consistent with `update-db.py`
  new-card defaults.

- [ ] **Step 1: Add the two fields**

In `new_sr_item`, next to `"easiness_factor": 2.5,` — use `fsrs_difficulty` (NOT
`difficulty`; if `new_sr_item` already sets a `difficulty` CEFR level, leave it
untouched):

```python
        "stability": None,
        "fsrs_difficulty": None,
```

- [ ] **Step 2: Sanity-run the importer check (no write)**

Run:
`cd ~/Projects/nederlands && python3 scripts/fluent_import.py --course link --check`
Expected: prints the mastery-gate check without error (fields are inert until a
review runs).

- [ ] **Step 3: Commit (on a nederlands branch)**

```bash
cd ~/Projects/nederlands
git add scripts/fluent_import.py
git commit -m "feat(fluent): seed stability/difficulty on imported SR items"
```

## Task 6: Deploy Phase 1 + run migration once

**Files:** none edited; deployment + one-time data migration.

**Interfaces:**

- Consumes: committed fork branch `fsrs`; the runtime CACHE and DATA dirs.
- Produces: the cache runs FSRS-6; existing 404 cards migrated; marketplace
  repointed to the fork.

- [ ] **Step 1: Push the fork branch and merge to the fork's default branch**

```bash
cd ~/Projects/fluent
python3 tests/test_fsrs.py && python3 tests/test_migrate_to_fsrs.py && python3 tests/test_update_db.py
git push -u origin fsrs
gh pr create --repo "$(gh api user -q .login)/fluent" --base main --head fsrs \
  --title "FSRS-6 scheduler + migration" --body "Phase 1: stdlib FSRS-6 + migration." || true
gh pr merge --repo "$(gh api user -q .login)/fluent" fsrs --merge --admin || git checkout main && git merge fsrs && git push
```

Expected: `fsrs` merged into the fork's `main`.

- [ ] **Step 2: Repoint the marketplace clone to the fork and pull**

```bash
cd ~/.claude/plugins/marketplaces/m98
git remote rename origin upstream 2>/dev/null || true
git remote add origin "git@github.com:$(gh api user -q .login)/fluent.git" 2>/dev/null || \
  git remote set-url origin "git@github.com:$(gh api user -q .login)/fluent.git"
git fetch origin && git checkout main && git reset --hard origin/main
```

Expected: marketplace `main` now matches the fork.

- [ ] **Step 3: Sync changed hooks into the runtime cache**

```bash
SRC=~/.claude/plugins/marketplaces/m98/.claude/hooks
DST=~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks
cp "$SRC/fsrs.py" "$SRC/update-db.py" "$SRC/migrate_to_fsrs.py" "$DST/"
ls "$DST"/{fsrs,update-db,migrate_to_fsrs}.py
```

Expected: the three Phase-1 hooks listed (present in the runtime cache).
`optimize_weights.py` is synced in Phase 2 (Task 9), after it exists.

- [ ] **Step 4: Run the migration once against real data**

Run:
`python3 ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/migrate_to_fsrs.py`
Expected: `[migrate] seeded 73 cards; backup at .../pre-migrate-fsrs-<date>` (73
= the reviewed cards; never-reviewed stay null).

- [ ] **Step 5: Verify a review now uses FSRS (read-only sanity)**

```bash
python3 ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/read-db.py \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d['databases']['spaced_repetition']['metadata']; print('scheduler:', m.get('scheduler'))"
```

Expected: `scheduler: fsrs-6`.

- [ ] **Step 6: Update CHANGELOG on the fork and commit**

Add under a new top entry in `~/Projects/fluent/CHANGELOG.md`:

```markdown
## [Unreleased]

### Changed

- Scheduler switched from SM-2 to a stdlib FSRS-6 port
  (`.claude/hooks/fsrs.py`). Cards gain `stability`/`difficulty`;
  `metadata.scheduler = "fsrs-6"` and `metadata.weights` (optional, from the
  offline optimizer). One-time migration in `migrate_to_fsrs.py`.
  `calculate_sm2` retained as a rollback branch.
```

```bash
cd ~/Projects/fluent && git add CHANGELOG.md && git commit -m "docs(changelog): FSRS-6 scheduler" && git push
```

---

# Phase 2 — dormant guarded optimizer (auto-activates at 400 reviews)

## Task 7: `optimize_weights.py` — extract + guard + persist (stdlib, testable)

**Files:**

- Create: `~/Projects/fluent/.claude/hooks/optimize_weights.py`
- Test: `~/Projects/fluent/tests/test_optimize_weights.py`

**Interfaces:**

- Consumes: `spaced-repetition.json`; `fluent_paths` helpers.
- Produces: `extract_logs(sr) -> (logs, total_reviews)`,
  `should_optimize(total, meta) -> bool`, and a `main()` that no-ops below
  threshold. The `torch`-bound training call is isolated in
  `train(logs) -> list[float]` imported lazily.

- [ ] **Step 1: Write the failing guard/extract test**

Create `tests/test_optimize_weights.py`:

```python
#!/usr/bin/env python3
"""Run: python3 tests/test_optimize_weights.py  (no torch needed)"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
import optimize_weights as o


def _sr(n_reviews):
    hist = [{"date": "2026-01-01", "quality": 5, "score": 0} for _ in range(n_reviews)]
    return {"items": {"c1": {"id": "c1", "review_history": hist}},
            "metadata": {"reviews_at_last_optimize": 0}}


class TestGuard(unittest.TestCase):
    def test_extract_maps_quality_not_score(self):
        sr = {"items": {"c1": {"id": "c1", "review_history": [
            {"date": "2026-01-01", "quality": 5, "score": 0},   # score 0 must be ignored
            {"date": "2026-01-02", "quality": 1, "score": 0},
        ]}}, "metadata": {}}
        logs, total = o.extract_logs(sr)
        self.assertEqual(total, 2)
        self.assertEqual([r[2] for r in logs], [4, 1])  # q5->Easy(4), q1->Again(1)

    def test_guard_blocks_below_400(self):
        self.assertFalse(o.should_optimize(165, {"reviews_at_last_optimize": 0}))

    def test_guard_blocks_when_too_few_new(self):
        self.assertFalse(o.should_optimize(420, {"reviews_at_last_optimize": 400}))

    def test_guard_allows_when_ready(self):
        self.assertTrue(o.should_optimize(460, {"reviews_at_last_optimize": 400}))

    def test_main_noops_below_threshold(self):
        # main() with today's real data must not raise and must return 0
        self.assertEqual(o.main(dry_data=_sr(165)), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Projects/fluent && python3 tests/test_optimize_weights.py` Expected:
FAIL — `ModuleNotFoundError: No module named 'optimize_weights'`.

- [ ] **Step 3: Write `optimize_weights.py`**

Create `.claude/hooks/optimize_weights.py`:

```python
#!/usr/bin/env python3
"""Weekly FSRS-6 weight optimizer (offline, guarded).

stdlib for extract/guard/persist; `fsrs-optimizer` (torch) only inside train().
Run from the optimizer venv: <venv>/bin/python optimize_weights.py
"""
import json, os, shutil, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fluent_paths import ensure_data_dir, ensure_backups_dir, force_utf8_io

MIN_TOTAL = 400
MIN_NEW = 50
EXPECTED_WEIGHTS = 21


def _rating(entry):
    q = entry.get("quality", 3)  # ignore score: historical score is unreliably 0
    return 1 if q < 3 else 2 if q == 3 else 3 if q == 4 else 4


def extract_logs(sr):
    logs = []
    for cid, card in sr.get("items", {}).items():
        for e in card.get("review_history", []):
            logs.append((cid, e.get("date"), _rating(e)))
    return logs, len(logs)


def should_optimize(total, meta):
    return total >= MIN_TOTAL and (total - meta.get("reviews_at_last_optimize", 0)) >= MIN_NEW


def train(logs):
    """Fit FSRS-6 weights. Imports fsrs-optimizer lazily (torch)."""
    from fsrs_optimizer import Optimizer  # noqa: import isolated to venv
    opt = Optimizer()
    weights = opt.optimize(logs)  # adapt to fsrs-optimizer's actual API at impl time
    return [float(x) for x in weights]


def main(dry_data=None):
    force_utf8_io()
    data = ensure_data_dir()
    sr_path = data / "spaced-repetition.json"
    sr = dry_data if dry_data is not None else json.loads(sr_path.read_text(encoding="utf-8"))
    meta = sr.setdefault("metadata", {})
    logs, total = extract_logs(sr)

    if not should_optimize(total, meta):
        print(f"[optimize] insufficient data ({total}/{MIN_TOTAL}, "
              f"+{total - meta.get('reviews_at_last_optimize', 0)} new) — no-op")
        return 0
    if dry_data is not None:
        return 0

    try:
        weights = train(logs)
    except Exception as exc:  # broken venv/import must never corrupt scheduling
        print(f"[optimize] training failed, keeping current weights: {exc}", file=sys.stderr)
        return 1
    if len(weights) != EXPECTED_WEIGHTS:
        print(f"[optimize] expected {EXPECTED_WEIGHTS} weights, got {len(weights)} — abort",
              file=sys.stderr)
        return 1

    backups = ensure_backups_dir()
    dest = backups / f"pre-optimize-{date.today().isoformat()}"
    dest.mkdir(parents=True, exist_ok=True)
    for f in data.glob("*.json"):
        shutil.copy2(f, dest / f.name)

    old = meta.get("weights")
    meta["weights"] = weights
    meta["last_optimized"] = date.today().isoformat()
    meta["reviews_at_last_optimize"] = total
    tmp = sr_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, sr_path)
    print(f"[optimize] weights updated ({total} reviews). old={old} new={weights}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Projects/fluent && python3 tests/test_optimize_weights.py` Expected:
`OK` (the guard no-ops on 165; `train` is never called).

- [ ] **Step 5: Verify the no-op against real data**

Run: `python3 ~/Projects/fluent/.claude/hooks/optimize_weights.py` Expected:
`[optimize] insufficient data (165/400, +165 new) — no-op` and exit 0.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/fluent
git add .claude/hooks/optimize_weights.py tests/test_optimize_weights.py
git commit -m "feat(fsrs): guarded weekly weight optimizer (no-op until 400 reviews)"
```

## Task 8: Provision the optimizer venv and wire `train()`

**Files:** none in-repo; environment setup + one manual verification.

**Interfaces:**

- Produces: a venv at `~/.claude/fluent-data/.venv-optimizer` with
  `fsrs-optimizer` installed; `train()` adapted to its real API.

- [x] **Step 1: Create the venv and install fsrs-optimizer**

```bash
python3 -m venv ~/.claude/fluent-data/.venv-optimizer
~/.claude/fluent-data/.venv-optimizer/bin/pip install -q fsrs-optimizer
~/.claude/fluent-data/.venv-optimizer/bin/python -c "import fsrs_optimizer; print('optimizer OK')"
```

Expected: `optimizer OK`.

- [x] **Step 2: Adapt `train()` to the installed API**

Inspect the real entry point and update `train()` in `optimize_weights.py` to
match (the package's optimize call and its expected review-log columns):

```bash
~/.claude/fluent-data/.venv-optimizer/bin/python -c "import fsrs_optimizer, inspect; print([n for n in dir(fsrs_optimizer) if not n.startswith('_')])"
```

Map our `(card_id, date, rating)` logs to the columns the optimizer expects
(typically `card_id`, `review_time`, `review_rating`). Keep the 21-weight sanity
check.

- [x] **Step 3: Dry-run the optimizer in its venv against real data**

Run:
`~/.claude/fluent-data/.venv-optimizer/bin/python ~/Projects/fluent/.claude/hooks/optimize_weights.py`
Expected: still `[optimize] insufficient data (165/400 …) — no-op` (torch
present but the guard blocks; confirms the venv path runs cleanly).

- [x] **Step 4: Commit any `train()` adjustments**

```bash
cd ~/Projects/fluent
git add .claude/hooks/optimize_weights.py
git commit -m "chore(fsrs): adapt optimizer train() to installed fsrs-optimizer API"
git push
```

## Task 9: Weekly LaunchAgent (dotfiles repo)

**Files:**

- Create: `~/.claude/…/dotfiles/launchd/com.aymkin.fluent-fsrs-optimize.plist`
  (the dotfiles repo working copy) and install to `~/Library/LaunchAgents/`.

**Interfaces:**

- Consumes: the optimizer venv + `optimize_weights.py` from Tasks 7-8.
- Produces: a weekly (Sunday 09:05) job that runs the optimizer and logs.

- [x] **Step 0: Push the fork and sync `optimize_weights.py` into the cache**

```bash
cd ~/Projects/fluent && git push
cd ~/.claude/plugins/marketplaces/m98 && git fetch origin && git reset --hard origin/main
cp ~/.claude/plugins/marketplaces/m98/.claude/hooks/optimize_weights.py \
   ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/optimize_weights.py
ls ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/optimize_weights.py
```

Expected: the optimizer path is listed (now in the runtime cache the plist
references).

- [x] **Step 1: Write the plist (keep `/Users/Alex.Naymkin` literal)**

Create `launchd/com.aymkin.fluent-fsrs-optimize.plist` in the dotfiles repo:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.aymkin.fluent-fsrs-optimize</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>/Users/Alex.Naymkin/.claude/fluent-data/.venv-optimizer/bin/python /Users/Alex.Naymkin/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/optimize_weights.py &gt;&gt; /Users/Alex.Naymkin/.claude/logs/fluent-fsrs-optimize.log 2&gt;&amp;1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>0</integer>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>5</integer>
  </dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```

- [x] **Step 2: Install and load it**

```bash
mkdir -p ~/.claude/logs
cp launchd/com.aymkin.fluent-fsrs-optimize.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.aymkin.fluent-fsrs-optimize.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.aymkin.fluent-fsrs-optimize.plist
launchctl list | grep fluent-fsrs-optimize
```

Expected: the label appears in `launchctl list`.

- [x] **Step 3: Trigger once to confirm the wiring (should no-op)**

```bash
launchctl start com.aymkin.fluent-fsrs-optimize
sleep 5 && cat ~/.claude/logs/fluent-fsrs-optimize.log
```

Expected: log shows `[optimize] insufficient data (165/400 …) — no-op`.

- [x] **Step 4: Commit in the dotfiles repo**

```bash
# in the dotfiles repo working copy
git add launchd/com.aymkin.fluent-fsrs-optimize.plist
git commit -m "feat(launchd): weekly FSRS weight optimizer (Sun 09:05)"
```

---

## Verification (whole feature)

- [x] `cd ~/Projects/fluent && python3 tests/test_fsrs.py && python3 tests/test_migrate_to_fsrs.py && python3 tests/test_optimize_weights.py && python3 tests/test_update_db.py`
      → all `OK`.
- [x] `~/Projects/fluent/.devvenv/bin/python tests/test_fsrs_crosscheck.py` →
      `OK`.
- [x] `read-db.py` shows `metadata.scheduler == "fsrs-6"` and migrated cards
      have `stability`.
- [x] A real `/fluent-review` session reschedules via FSRS (item gains
      `stability`, `difficulty`, `last_rating`).
- [x] `launchctl list | grep fluent-fsrs-optimize` present; manual `start` logs
      a no-op.

## Notes for the implementer

- The FSRS-6 cross-check (Task 2 Step 7) is the correctness gate. The port code
  here is faithful but not authoritative — reconcile against the pinned
  `py-fsrs` source until parity holds.
- `fsrs-optimizer` and `py-fsrs` public APIs shift between releases. Task 2 Step
  1 and Task 8 Step 2 pin/inspect the actual installed versions; adapt the
  `Scheduler`/`Optimizer` calls accordingly. The stdlib hook never imports
  either.
- Cache-sync (Task 6 Step 3) copies hook files directly. If a plugin reinstall
  ever regenerates the cache from the fork, that is equivalent and also fine.

```

```

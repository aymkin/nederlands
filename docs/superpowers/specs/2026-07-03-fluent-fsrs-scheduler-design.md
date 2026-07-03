# Design: replace SM-2 with FSRS-6 in the Fluent plugin

**Date:** 2026-07-03 **Status:** approved (design), pending implementation plan
**Author:** Alex + Claude

## Problem

The Fluent spaced-repetition scheduler uses classic SM-2 (`calculate_sm2` in
`.claude/hooks/update-db.py:148`). SM-2 stores a single `easiness_factor` per
card and multiplies the interval blindly on each successful review, ignoring
_how overdue_ the card was when answered. We want the modern Anki scheduler,
**FSRS** (Free Spaced Repetition Scheduler), which models memory explicitly,
targets a fixed retention rate, and — unlike SM-2 — can have its parameters
re-fit from the learner's own review history.

Note: "the Anki mechanism" and "SM-2" are largely the same thing — Anki's
classic scheduler _is_ SM-2. The meaningful upgrade is FSRS (Anki's default
since 23.10), a different algorithm, not a UX layer over SM-2.

## Decisions (locked during brainstorming)

1. **Algorithm:** **FSRS-6** (21 parameters `w[0..20]`, learnable decay
   `w[20]`). FSRS-6 is what the maintained `py-fsrs` / `fsrs-optimizer` packages
   implement, so scheduler and optimizer stay version-consistent and the port
   can be numerically cross-checked against `py-fsrs`. We use one review per
   card per day, so the short-term (same-day) path (`w[17]`, `w[18]`) is never
   exercised — but we port it anyway for parity with the reference.
2. **Runtime port:** self-contained **stdlib-only** FSRS scheduler in the hook,
   **no pip dependency**. `update-db.py` runs unattended in whatever Python the
   user has, with no venv guarantee; every plugin hook is deliberately
   stdlib-only. The FSRS-6 forward math is ~60-80 lines of deterministic
   arithmetic, so a port is _more_ robust than importing `py-fsrs` at hook
   runtime. (The **optimizer** in Decision 5 is separate and _may_ use deps.)
   Correctness is guaranteed by a numerical cross-check test against `py-fsrs`
   (dev-time only), not by hand-transcribing formulas.
3. **Migration:** derive `stability`/`difficulty` for the 404 existing cards
   from their current `interval_days`/`easiness_factor`. No history replay. This
   preserves progress and does not re-flood the (already overloaded) queue.
4. **Weekly guarded weight optimizer.** A scheduled offline job re-fits the 21
   weights from the learner's review history and writes them to
   `spaced_repetition.metadata.weights`, which the runtime hook reads. It is
   **guarded**: it re-trains only when there are **≥ 400 total reviews** (the
   FSRS floor) **and** **≥ 50 new reviews** since the last run; otherwise it
   no-ops and logs "insufficient data (N/400)". Today there are 165 reviews
   across 73 cards, so it no-ops for months and self-activates once enough data
   accrues. Rationale: fitting 21 parameters on ~165 samples overfits and
   produces weights _worse_ than the tuned defaults.
5. **Fork the plugin.** Fork `github.com/m98/fluent` to the learner's account
   and make the fork the source of truth. Editing the upstream marketplace clone
   directly would be clobbered by the daily `git pull` / a plugin reinstall. On
   the fork, upstream fixes are merged **on our terms**
   (`git merge upstream/main`), never auto-applied over our FSRS changes.
6. **Optimizer uses the official `fsrs-optimizer`** (pip, `torch`) in a
   **dedicated venv**, run offline. It trains FSRS-6 (21 weights), matching the
   runtime port. Weight training is real ML (gradient descent with
   loss/clipping/LR schedule) — exactly the thing not to hand-roll. The
   dependency is isolated to the offline job's venv and never reaches the hook.
7. **Scheduled by a weekly macOS LaunchAgent**, mirroring the existing 9:03 /
   9:04 daily jobs (Sunday 09:05). The plist is versioned in the dotfiles repo.

## Where the code lives (deployment — spans three repos)

1. **The fork `github.com/<learner>/fluent`** — source of truth for all hook
   code: `.claude/hooks/fsrs.py`, the `update-db.py` edit, `migrate_to_fsrs.py`,
   `optimize_weights.py`, `tests/`, `CHANGELOG.md`. Created with
   `gh repo fork m98/fluent`. The local marketplace clone at
   `~/.claude/plugins/marketplaces/m98/` gets its `origin` repointed to the fork
   (`m98/fluent` kept as `upstream`); the runtime cache
   `~/.claude/plugins/cache/m98/fluent/0.3.0/` receives the changed hook files
   so Claude Code executes our code. The daily plugin-update automation then
   pulls the **fork**, which is safe.
2. **The dotfiles repo (`~/.claude`)** — the weekly LaunchAgent plist
   (`launchd/com.aymkin.fluent-fsrs-optimize.plist`), the marketplace-repoint
   note, and the optimizer venv location. The daily automation's pull target
   changes from upstream to the fork.
3. **This repo (`nederlands`)** — this spec, the implementation plan, and the
   one-line new-card-default edit in `scripts/fluent_import.py` (Component 3).

**Fork maintenance cost:** merging upstream releases may conflict with our FSRS
changes and needs manual resolution — strictly better than silent clobbering,
and the accepted trade-off.

## Architecture

The runtime scheduling decision is localized in one function today, so the hot
path's blast radius is small. The optimizer is a separate offline component that
feeds weights back through `metadata`.

### Component 1 — new module `.claude/hooks/fsrs.py` (stdlib-only)

Owns the memory model and all FSRS-6 forward math. Imports only `math`. Keeps
`update-db.py` thin and gives the formulas a home for a self-test.

Memory model — three per-card quantities replacing `easiness_factor`:

- **S (stability):** days until recall probability decays to the target
  retention. Effectively the interval.
- **D (difficulty):** intrinsic card difficulty, clamped to `[1, 10]`.
- **R (retrievability):** current probability of recall; a function of elapsed
  days `t` and `S`.

**Porting method (correctness-critical):** do **not** hand-transcribe the FSRS-6
formulas or the 21 default weights from memory. Port the forward math from a
pinned `py-fsrs` release (the `Scheduler` class), and extract `DEFAULT_W`
programmatically from that same package (`fsrs.DEFAULT_PARAMETERS` or
equivalent), pinning the exact version in a code comment. The numerical
cross-check test (see Testing) is the gate: our port must match `py-fsrs`
outputs within tolerance before the code is accepted.

Structure to port (FSRS-6):

- `DECAY = -w[20]`; `FACTOR = 0.9 ** (1 / DECAY) - 1`.
- `R(t, S) = (1 + FACTOR * t / S) ** DECAY`.
- `interval(S) = (S / FACTOR) * (TARGET_RETENTION ** (1 / DECAY) - 1)`,
  `TARGET_RETENTION = 0.90`.
- Initial stability `S0(G) = w[G-1]` (G in 1..4).
- Initial difficulty `D0(G) = clamp(w[4] - exp(w[5] * (G - 1)) + 1, 1, 10)`.
- Difficulty update with linear damping + mean reversion toward `D0(4)` (uses
  `w[6]`, `w[7]`).
- Stability after recall (uses `w[8]..w[10]`, hard penalty `w[15]`, easy bonus
  `w[16]`).
- Stability after lapse (uses `w[11]..w[14]`), floored so a lapse never
  increases stability.
- Short-term/same-day path (`w[17]`, `w[18]`) ported for parity but unused at
  one review/day.

Public API — `schedule` takes the active weights so optimized values flow in:

```python
def schedule(item: dict, rating: int, today: str, weights: list | None = None) -> dict:
    """Return {stability, difficulty, interval_days, due_date}.
    weights: the learner's optimized 21-weight vector, or None -> DEFAULT_W.
    Handles new cards (no stability -> S0/D0) and reviews alike."""
```

`interval_days = max(1, round(interval(S')))`;
`due_date = today + interval_days`.

### Component 2 — edit `.claude/hooks/update-db.py` review loop (~line 384)

Replace the `calculate_sm2` call with a rating mapping + `fsrs.schedule`, using
optimized weights from metadata when present:

```
weights = sr.get("metadata", {}).get("weights")   # None -> fsrs.DEFAULT_W
score   = review.get("score", quality * 2)         # 0-10, richer than floored quality
rating  = 1 if score <= 4 else 2 if score <= 6 else 3 if score <= 8 else 4
# The item "difficulty" key holds the CEFR level (e.g. "A2") — the FSRS
# numeric difficulty lives under "fsrs_difficulty". Map to schedule()'s dict.
fsrs_state = {"stability": item.get("stability"),
              "difficulty": item.get("fsrs_difficulty"),
              "last_reviewed": item.get("last_reviewed")}
r = fsrs.schedule(fsrs_state, rating, today, weights)
item["stability"]      = r["stability"]
item["fsrs_difficulty"] = r["difficulty"]
item["interval_days"]  = r["interval_days"]
item["due_date"]       = r["due_date"]
item["last_rating"]    = rating
# keep maintaining repetitions / consecutive_* exactly as before:
item["repetitions"] = item.get("repetitions", 0) + 1 if quality >= 3 else 0
```

Rating scale: `Again=1 (<=4/10)`, `Hard=2 (5-6)`, `Good=3 (7-8)`,
`Easy=4 (9-10)`. The 50% boundary preserves SM-2's fail/pass split. The
`consecutive_*`, `mastery_level`, and `priority` heuristics and the queue
rebuild (by `due_date`) are **unchanged** — they read
`consecutive_*`/`repetitions`/`mastery_level`, never `easiness_factor`.

`calculate_sm2` stays in the file (dead but retained one version) as the
rollback branch.

### Component 3 — card schema + metadata

Add three fields to every SR item: `stability` (float|null), `fsrs_difficulty`
(float|null), `last_rating` (int 1-4|null). **Field-name collision (caught in
review):** the item schema already uses `difficulty` for the CEFR level string
(e.g. `"A2"`), so FSRS's numeric difficulty MUST live under `fsrs_difficulty` —
never overwrite `difficulty`. Keep `easiness_factor` and `repetitions` (mastery
heuristic reads `repetitions`; `easiness_factor` is the rollback net). New-card
defaults gain `stability: null, fsrs_difficulty: null` in all three creation
sites: `update-db.py` (vocabulary ~line 430, error-pattern ~line 455) and
`scripts/fluent_import.py:new_sr_item` (~line 192, this repo).

`spaced_repetition.metadata` becomes the single source for scheduler config and
the optimizer↔hook loop:

```json
{
  "scheduler": "fsrs-6",
  "target_retention": 0.9,
  "weights": [ ...21 floats... ],
  "last_optimized": "YYYY-MM-DD",
  "reviews_at_last_optimize": 0
}
```

`weights` is written by the optimizer (Component 5) and read by the hook
(Component 2). Absent/`null` → hook falls back to `fsrs.DEFAULT_W`.

### Component 4 — one-time migration `.claude/hooks/migrate_to_fsrs.py`

Backfills `stability`/`fsrs_difficulty` for the 404 existing cards (writing the
FSRS difficulty to `fsrs_difficulty`, never the CEFR `difficulty`). Backs up all
DBs first (same helper `update-db.py` uses). Idempotent: skips any card with a
non-null `stability`.

```
stability  = max(interval_days, 0.5)                    # interval ≈ stability at 0.9
difficulty = clamp(10 - (EF - 1.3) / 1.4 * 9, 1, 10)    # EF 1.3->D10, EF 2.7->D1
# cards never reviewed (repetitions == 0): leave stability/difficulty null;
# they initialize from S0/D0 on the first FSRS review.
```

Also stamps `spaced_repetition.metadata` with the Component 3 config (leaving
`weights` null so the hook uses defaults until the first optimization).

### Component 5 — offline optimizer `.claude/hooks/optimize_weights.py`

Runs in a dedicated venv (Decision 6), invoked by the LaunchAgent (Component 6).
Never imported by the runtime hook.

Flow, split so the guard is testable without `torch`:

1. **Extract** (stdlib): read `spaced-repetition.json`, flatten every card's
   `review_history` into review logs `(card_id, review_date, rating)`. Derive
   `rating` from each entry's **`quality`** (0-5 → 1-4:
   `1 if q<3 else 2 if q==3 else 3 if q==4 else 4`), **not** from `score` —
   existing history stores `score` as `0` even for high-quality reviews, so it
   is unreliable for historical entries. (Only the live Component-2 path uses
   `score`.) Count `total_reviews`.
2. **Guard** (stdlib): if `total_reviews < 400` **or**
   `total_reviews - metadata.reviews_at_last_optimize < 50`, log
   `insufficient data (total/400, +new)` and exit `0` **without writing**.
3. **Train** (deps): hand the logs to `fsrs-optimizer` to fit the 21 FSRS-6
   weights.
4. **Persist** (stdlib): back up all DBs, then write `metadata.weights`,
   `metadata.last_optimized = today`,
   `metadata.reviews_at_last_optimize = total_reviews`. Log old→new weights.

Steps 1, 2, 4 are stdlib and unit-testable; step 3 is the only `torch`-bound
part and sits behind the guard.

### Component 6 — weekly LaunchAgent (dotfiles repo)

`launchd/com.aymkin.fluent-fsrs-optimize.plist`, weekly (Sunday 09:05). Runs the
venv Python against `optimize_weights.py`, logging to
`~/.claude/logs/fluent-fsrs-optimize.log`. Follows dotfiles conventions: inline
bash inside the XML, `/Users/Alex.Naymkin` kept literal (install.sh rewrites to
`$HOME`), loaded via `launchctl`. One-time venv provisioning
(`python3 -m venv … && pip install fsrs-optimizer`) is documented in the plan,
not automated by the plist.

## Data flow

```
Runtime (per session, stdlib hook):
  /fluent-review answer -> tutor score 0-10
    -> update-db.py: score -> rating (1-4); weights = metadata.weights or DEFAULT_W
    -> fsrs.schedule(item, rating, today, weights)
         new card: S0/D0 ;  review: R(elapsed,S) -> S', D'
    -> item.stability/fsrs_difficulty/interval_days/due_date updated
    -> mastery/priority heuristics (unchanged) -> queue rebuilt by due_date

Weekly (offline, venv, LaunchAgent Sun 09:05):
  optimize_weights.py
    -> extract review logs from all cards' review_history
    -> guard: total >= 400 and new >= 50 ?  no -> log + exit 0 (no write)
    -> yes -> fsrs-optimizer fits 21 weights
    -> write metadata.weights + last_optimized + reviews_at_last_optimize
  (next session's hook picks up the new weights automatically)
```

## Error handling / edge cases

- **Missing/zero `score`:** the live hook falls back to `quality * 2`; the
  optimizer ignores `score` entirely and maps from `quality` (historical `score`
  is stored as `0` and cannot be trusted). `quality` is always present.
- **New card (no `stability`):** `schedule` branches on `stability is None` ->
  initialize from `S0`/`D0`.
- **Never-reviewed card at migration (`repetitions == 0`):** leave S/D null;
  first review initializes them. No fabricated stability.
- **`interval_days` clamp:** always `>= 1` so a card never schedules in the
  past.
- **Clamps:** `D` in `[1, 10]`; `S` floored at a small positive value to avoid
  divide-by-zero in `R`; lapse stability floored so it never exceeds pre-lapse
  `S`.
- **Idempotent migration:** re-running skips cards with non-null `stability`.
- **Optimizer below threshold:** no write, exit `0`, log reason — never leaves
  metadata half-updated.
- **Optimizer venv missing / `fsrs-optimizer` import fails:** log error, exit
  non-zero **without writing** — the hook keeps using the last good weights (or
  defaults). A broken optimizer must never corrupt scheduling.
- **Optimizer weight-count sanity:** before writing, assert the trained vector
  has exactly 21 floats; otherwise abort without writing (guards against a
  future `fsrs-optimizer` emitting a different FSRS version).
- **Backup before write:** `update-db.py`, `migrate_to_fsrs.py`, and
  `optimize_weights.py` all back up the six DBs before mutating.

## Testing (one runnable check per non-trivial unit)

Convention: `unittest`, run via `python3 tests/<file>.py`.

- **`tests/test_fsrs.py`** (new, stdlib) — invariants: `R(t=S) ≈ 0.90`;
  `interval(S) ≈ S` at 0.90; `Good` grows `S`, `Again` shrinks it and yields
  `interval_days == 1`; `D` stays in `[1, 10]`; migration seed
  `interval=48, EF=2.5` → `stability ≈ 48`, `D` in `[1, 10]`; `schedule` with
  explicit `weights` differs from `DEFAULT_W` (weights are actually used).
- **`tests/test_fsrs_crosscheck.py`** (new, dev-only, **skips if `fsrs` not
  importable**) — the correctness gate: for a set of rating sequences, assert
  our stdlib `schedule` matches `py-fsrs`'s FSRS-6 `Scheduler` on stability,
  difficulty, and interval within tolerance (e.g. stability within 1%, interval
  within ±1 day). Guarded with `unittest.skipUnless` so CI/hook environments
  without `fsrs` still pass; run in the dev venv during implementation.
- **`tests/test_optimize_weights.py`** (new, stdlib, no torch) — the guard:
  below 400 reviews → exits `0`, writes nothing; review-log extraction maps
  `quality` history to correct 1-4 ratings and counts totals. The
  `fsrs-optimizer` call is behind the guard and not exercised here.
- **`tests/test_update_db.py`** (extend) — after a review, the item carries
  `stability`, `fsrs_difficulty`, `last_rating`, and a `due_date` consistent
  with `interval_days`; the CEFR `difficulty` string is preserved unchanged;
  metadata `weights` (when set) are honored.

## Rollback

`update-db.py` already backs up all six DBs before every write. To revert:

- **Scheduler:** flip `metadata.scheduler` to `"sm2"` and restore the
  `calculate_sm2` call (branch retained).
- **Bad optimized weights:** clear `metadata.weights` (hook falls back to
  `DEFAULT_W`) or restore a backup; disable the LaunchAgent with
  `launchctl unload`.
- **Migration:** restore a pre-migration backup if needed.

## Effort estimate

- `fsrs.py`: ~80 lines incl. `__main__` smoke guard.
- `update-db.py` edit: ~15 lines.
- `migrate_to_fsrs.py`: ~30 lines.
- `optimize_weights.py`: ~80 lines (extract + guard + persist; training is a
  library call).
- LaunchAgent plist: ~40 lines XML + venv provisioning steps in the plan.
- schema defaults: +2 fields in 3 sites.
- tests: `test_fsrs.py` ~50, `test_fsrs_crosscheck.py` ~40,
  `test_optimize_weights.py` ~40, `test_update_db.py` +1 block.
- `CHANGELOG.md`: one `### Changed` entry.

Two new abstractions (the `fsrs` module and the offline optimizer), each
justified: the module by testability + a thin hook, the optimizer by isolating
`torch` off the hot path.

## Out of scope

- **Reimplementing FSRS training.** Delegated to `fsrs-optimizer`; we own only
  extraction, the guard, and persistence.
- **Upstream PR to `m98/fluent`.** We maintain a fork instead.
- **Auto-provisioning the optimizer venv.** One-time manual setup, in the plan.
- **Classic-Anki UX layer** (4 buttons in the session UI, learning steps, leech
  tags). The 0-10 tutor score maps to a rating internally; session UX unchanged.
- **Configurable per-deck retention.** `TARGET_RETENTION` is a single constant.

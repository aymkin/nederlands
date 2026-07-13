---
name: fluent-backlog-campaign
description:
  Use when the Fluent review backlog must be drained or the --advance mastery
  gate seems unreachable — hundreds of cards in review_queue.today,
  fluent_import.py --check prints "⏳ продолжай" at 0% mastery, curriculum.json
  says thema_4 active while real study is thema 13, or someone proposes
  deferring due_dates, raising review_items_per_day, hand-editing mastery_level,
  or repointing/advancing the curriculum. Also for planning promotion
  (--advance) after a gate passes.
---

# Fluent backlog campaign — drain the queue, reach the gate

An executable, decision-gated campaign. Goal: get the Fluent spaced-repetition
system (SR) out of its backlog + mastery-gate deadlock and to a passed
`--advance` gate for the thema Alex actually studies.

**Success is MEASURED, never judged by eye.** The campaign is won when
`python3 scripts/fluent_import.py --course link --check` prints
`✅ готов дальше — запусти --advance` ("ready — run --advance") for the active
unit, and the owner has confirmed promotion. Every phase below has an expected
observation and a branch for when reality differs.

**When NOT to use this skill:** for day-to-day operation of the importer, review
sessions, or backup restore, use `nederlands-run-and-operate`; for one-off
measurement without a campaign, use `nederlands-diagnostics-and-tooling`; for
FSRS/mastery theory, use `nt2-srs-reference`.

## The problem (baseline as of 2026-07-10 — re-measure, do not trust)

| Measured fact                          | Value (2026-07-10)                                                |
| -------------------------------------- | ----------------------------------------------------------------- |
| SR items total                         | 408                                                               |
| `review_queue.today` (stale snapshot)  | 335                                                               |
| Recomputed `due_date <= today`         | 347                                                               |
| Due per prefix                         | t12: 157, t13: 139, t4: 36, error-pattern: 12, legacy `vocab_`: 3 |
| Daily cap `review_items_per_day`       | 30 (live; code default 20)                                        |
| Mastery histogram                      | L0: 361, L1: 19, L2: 21, L3: 7                                    |
| mastery≥3 INSIDE any course unit       | 0 (the 7 are legacy/error items)                                  |
| Red cards (`consecutive_incorrect>=2`) | 3, all error-pattern ids, none inside a unit                      |
| Lifetime reviews (per-item sum)        | 225 across 21 sessions (~10.7 reviews/session)                    |
| curriculum.json active unit            | thema_4 (real study = thema 13)                                   |
| Gate for thema_13                      | needs 112/139 at mastery≥3 + 0 red                                |

The deadlock: the `--advance` gate needs 80% of the active unit at
`mastery_level >= 3` with zero red cards, but the active unit (thema_4) is not
what Alex studies, mastery≥3 is 0 in every unit, and 347 due cards swamp a
30/day cap that history shows is really ~11 reviews per session.

## Fenced-off wrong paths (do NOT do these)

1. **Never hand-edit `mastery_level`, `stability`, `fsrs_difficulty`,
   `repetitions`, or `consecutive_correct`.** It corrupts FSRS state and fakes
   the gate — the campaign's success metric becomes a lie. The only legitimate
   writers are `update-db.py` (reviews) and `fluent_import.py` (new items). See
   `nederlands-architecture-contract`.
2. **Never run `--advance` repeatedly to "walk" the pointer from thema_4 to
   thema_13.** Each `--advance` marks the current unit done, activates the next,
   AND imports it (verified in `scripts/fluent_import.py:advance`). Walking 4→13
   would import thema_5..12 grammar clozes nobody studies, growing the backlog
   by hundreds of cards. Repoint by manifest edit instead (Phase 1).
3. **Never burn the queue by feeding `update-db.py` fabricated
   `review_results`.** The 30/day cap is enforced server-side only in the
   `read-db.py --review` serving path; `update-db.py` accepts any number of
   results. Bypassing `/fluent-review` fakes `review_history`, which poisons the
   future weight optimizer's training data (it trains from per-item history).
4. **Never "fix" `fluent_import.py` to write through `update-db.py` or to touch
   DBs other than spaced-repetition.json.** Two-owner invariant; going through
   the updater falsely increments sessions/streak. See
   `nederlands-architecture-contract`.
5. **Do not build a heavyweight templated study-plan system around this
   campaign.** Owner rule; two such systems died within days
   (`nederlands-failure-archaeology`). This campaign is a checklist, not a
   calendar.

## Phase 0 — measure the baseline

Run both diagnostics (shipped by `nederlands-diagnostics-and-tooling`), from the
repo root. Both are read-only.

```bash
cd /path/to/nederlands   # repo root
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/fluent_health.py
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/gate_report.py --course link
```

Expected shape (numbers WILL drift; these are the 2026-07-10 values):

```
[queue buckets]
  today: 335
  ...
  recomputed due<=today from items: 347
  !! queue.today (335) != recomputed due (347) — queue is STALE ...
[daily_limits] review_items_per_day = 30 ...
[mastery histogram]
  level 0: 361 ... level 3: 7
[red cards] consecutive_incorrect>=2: 3  -> grammar_bijzin_en_conjunct, ...
[review_history] top-level key: 0 entries (LEGACY, ...) | per-item sum: 225 (REAL)
```

```
unit       status   cards  m>=3     pct  red  gate
thema_4    active      51     0   0.0%    0  not ready (need 41 mastered)
thema_12   locked     157     0   0.0%    0  not ready (need 126 mastered)
thema_13   locked     139     0   0.0%    0  not ready (need 112 mastered)
active unit per curriculum.json: ['thema_4'] (exactly one is the invariant)
```

Baseline gate — branch table:

| If you see instead                      | Branch to                                                                                                       |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `queue.today` != recomputed due         | Normal (queue rebuilt only on import/update). Trust the recomputed number.                                      |
| top-level `review_history` non-empty    | STOP. Something wrote the legacy key — `nederlands-debugging-playbook` before trusting any count.               |
| mastery≥3 > 0 inside t13 prefix         | Progress already happened — recompute how many of the 112 remain, shorten Phase 3.                              |
| red > 0 inside a unit column            | Gate is red-blocked: those cards must be REVIEWED (not deferred, not edited) until `consecutive_incorrect < 2`. |
| gate_report exits 1 "cannot import ..." | You are not in a repo checkout with `scripts/fluent_import.py`; fix your cwd/layout.                            |
| active unit is already thema_13         | Phase 1 already done — skip to Phase 2.                                                                         |
| `[sessions] last: ... (>7 days ago)`    | The binding problem is cadence, not math. Fix the daily `/fluent-review` habit first; no data edit will help.   |

Record the four numbers you will steer by: recomputed due, due-per-prefix for
the active-to-be unit, mastery≥3 inside that unit, red inside it.

## Phase 1 — repoint the curriculum (DECISION GATE)

**STOP — owner confirmation required.** The owner approved this repoint in
principle on 2026-07-09 (mark thema_4–12 done, activate thema_13), but the
campaign must re-confirm before writing: study focus may have moved (e.g. to
thema_14) between then and now. Ask, and adjust N below.

Facts that shape the procedure (verified 2026-07-10):

- `fluent_import.py` writes `curriculum.json` ONLY inside `--advance`
  (`save_manifest` has exactly one call site). A manual repoint is a hand-edit —
  so back the manifest up yourself first.
- The one-active invariant is enforced at read time:
  `ValueError: expected exactly 1 active unit, got N`.
- curriculum.json is tracked and auto-publishes to GitHub Pages on commit; put
  the backup OUTSIDE the repo.

```bash
# 1. Backup outside the repo (repo contents publish to Pages)
cp link/curriculum.json ~/.claude/curriculum.json.pre-repoint-$(date +%Y%m%d)

# 2. Repoint (tested on a copy 2026-07-10). Adjust 12/13 if the owner
#    says the current thema moved.
python3 - link/curriculum.json <<'EOF'
import json, sys
p = sys.argv[1]
m = json.load(open(p))
for u in m["units"]:
    n = int(u["id"].split("_")[1])
    if n <= 12:   u["status"] = "done"
    elif n == 13: u["status"] = "active"
    else:         u["status"] = "locked"
open(p, "w").write(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
actives = [u["id"] for u in m["units"] if u["status"] == "active"]
assert actives == ["thema_13"], actives
print("repointed OK; active =", actives)
EOF

# 3. Verify the invariant through the importer's own reader
python3 scripts/fluent_import.py --course link --check
```

Expected `--check` output after repoint (2026-07-10 numbers):

```
thema_13 — 139 карточек | mastery≥3: 0/139 (0.0%) | красных: 0
⏳ продолжай
```

("карточек" = cards, "красных" = red, "продолжай" = keep going.)

Then re-import the active unit — idempotent, and it rebuilds the stale queue as
a side effect:

```bash
python3 scripts/fluent_import.py --course link
```

Expected: `Импорт thema_13: лексика 99, грамматика 40, новых 0` (vocab 99,
grammar 40, 0 new — all t13 cards were already imported; verified by a dry
import against a DB copy on 2026-07-10). It also snapshots
spaced-repetition.json to
`~/.claude/fluent-data/.backups/pre-import-<timestamp>/` before writing.

| If you see instead                       | Branch to                                                                                          |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `ValueError: expected exactly 1 active…` | Your edit left 0 or 2 actives — restore the backup, redo step 2.                                   |
| `новых N` with N > 0                     | New woordenlijst/grammar content landed since 2026-07-10 — fine; note N, it adds to the due count. |
| `--check` still prints thema_4           | The edit did not take (wrong cwd / wrong file). Diff against backup.                               |

Finally, commit `link/curriculum.json` as a SINGLE-file commit through
`nederlands-change-control` — the working tree carries mixed Prettier churn; a
blanket commit loses information and everything committed goes public.

## Phase 2 — backlog triage (DECISION GATE, ranked menu)

Choose how to handle the ~347 due cards. Options ranked; each carries its theory
obligation. Recommended combination: **(a) + (d), adding (b) only if two weeks
of (a) show the non-active backlog is drowning t13.**

### (a) Daily `/fluent-review` cadence at cap 30 — RANK 1, zero risk

The naive burn-down `347 / 30 ≈ 12 days` is wrong. The real formula:

```
days ≈ D / (c·f_out − inflow)
  D      = recomputed due today (347)
  c      = reviews actually done per day (cap 30; HISTORY says ~10.7)
  f_out  = fraction rescheduled beyond tomorrow. Failures (quality<3)
           return ~next day; even correct-but-Hard first reviews get a
           1-day interval. At lifetime accuracy 0.698, f_out ≈ 0.6–0.8.
  inflow = cards newly coming due (12 tomorrow + 15 this week now)
```

At a genuine 30/day: roughly 15–20 review days. At the historical ~11 per
session: 45+ days. The cap is not the bottleneck — session cadence and size are.
This option needs no data edit and cannot corrupt anything.

### (b) Defer stale non-active dues — RANK 2, data edit, obligations

Push `due_date` forward on due cards from prefixes nobody currently studies
(`link_t4_` 36 due, `link_t12_` 157 due, legacy `vocab_` 3 due), so
`/fluent-review` serves thema_13 instead of noise. This skill ships the tool:

```bash
# ALWAYS dry-run first (default), and test on a copy before the real DB:
python3 .claude/skills/fluent-backlog-campaign/scripts/defer_dues.py \
    --prefix link_t4_ --prefix link_t12_ --days 14
# then, after owner sign-off:
python3 ... defer_dues.py --prefix link_t4_ --prefix link_t12_ --days 14 --apply
```

Verified on a DB copy 2026-07-10: deferring t4+t12 moved 193 cards, today-bucket
347 → 154. The script backs up to `.backups/pre-defer-<ts>/`, refuses red cards,
never touches not-yet-due items, and rebuilds the queue identically to the
importer.

Obligations (non-negotiable):

- Backup exists before `--apply` (the script makes one; verify the dir).
- Two-owner rule: this edits Fluent's scheduling territory by hand — owner
  sign-off required, routed through `nederlands-change-control`.
- Document it as an experiment per `nederlands-research-methodology`: predict
  the number first ("today-bucket drops to ~154, t13 review share rises
  to >80%"), then measure.
- A deferral is a postponement, not a deletion: +14d means t12 floods back in
  two weeks. If t12 is truly abandoned material, prefer +90d and revisit.

### (c) Raise the cap `review_items_per_day` — RANK 3, usually wrong

Theory obligation (see `nt2-srs-reference`): in FSRS, retention degrades because
postponed reviews lower retrievability below target — the damage comes from
reviews NOT DONE, not from the cap number. Raising the cap only helps if the
learner genuinely does more quality reviews per day; the measured history (~10.7
reviews/session, 21 sessions ever) says the binding constraint is human time,
not the 30 limit. Raising it also enlarges each session's payload. Only
justified if sessions reliably exhaust 30 and the learner asks for more. Config
location: `spaced-repetition.json → daily_limits.review_items_per_day` (see
`nederlands-config-and-flags`; it is a data-file edit — backup + change-control
apply).

### (d) Freeze new imports until the gate — RANK 1 companion, free

Do not run `--thema N` focus imports or `--advance` while the today-bucket is
triple the cap. Every import seeds cards due TOMORROW
(`new_sr_item: due_date = today+1`), i.e. straight into the backlog. Exception:
the idempotent re-import of the active unit in Phase 1 (adds 0). Unfreeze when
recomputed due < ~50.

## Phase 3 — execution loop (weekly, measured)

Weekly checkpoint, same two commands as Phase 0. Steer by the `gate_report.py`
line for the active unit: `cards / m>=3 / pct / red`.

### What growth to EXPECT (derived, not hoped)

Mastery mechanics (verified in the runtime `update-db.py`, 2026-07-10):

- `repetitions` +1 per review with quality≥3, RESET to 0 on quality<3.
- Jump path: `repetitions>=5 AND consecutive_correct>=3` → mastery≥3.
- Increment path: `repetitions>=2 AND consecutive_correct>=1 AND quality>=4` →
  mastery +1 (so 0→3 across reviews 2,3,4).

FSRS-6 spacing (simulated with the runtime hook + DEFAULT_W, 2026-07-10;
quality→rating: q3→Hard, q4→Good, q5→Easy):

| Rating every time | Intervals after reviews 1..4 | 4th review at | 5th at  |
| ----------------- | ---------------------------- | ------------- | ------- |
| Hard (q=3)        | 1d, 3d, 7d, 12d              | day 11        | day 23  |
| Good (q=4)        | 2d, 11d, 46d, 163d           | day 59        | day 222 |
| Easy (q=5)        | 8d, 66d, 397d, …             | day 471       | —       |

Consequences:

- A card answered Good every time reaches mastery 3 at its 4th review — **~59
  days after its first review**. A hard-but-correct card gets there via the jump
  path at day ~23. Easy answers paradoxically DELAY mastery-3 (huge intervals
  postpone the 4th review) — that is the scheduler working as designed; do not
  "fix" it.
- Any lapse (quality<3) resets repetitions and consecutive_correct: the ladder
  restarts. At ~0.70 accuracy expect many restarts.
- Therefore: **earliest conceivable t13 gate pass ≈ repoint date + ~1 week of
  first-review spread (139 firsts at ≤30/day) + 23–59 days of ladder ≈
  mid-September 2026**; realistic with lapses: October–November 2026. This is a
  model-derived estimate — the weekly gate line is the truth.

### Weekly expectations and branches

| Week after repoint | Expect in t13 row                                        | If not →                                                                                                                                                                     |
| ------------------ | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1–2                | m≥3 still ~0; mastery L1/L2 counts in the histogram grow | Sessions not happening or not persisting: check `[sessions]` in fluent_health; if sessions run but items don't move, `nederlands-debugging-playbook` (update-db exit codes). |
| 3–5                | first m≥3 cards appear (hard-path day ~23)               | Accuracy likely <0.7 with resets — check session accuracy in session-log; consider smaller sessions, not cap raises.                                                         |
| 6–10               | pct climbs toward 80%; red stays 0                       | red > 0 inside t13: those cards outrank everything (priority "high"); review them first — they hard-block the gate.                                                          |

Do NOT tighten the loop below weekly — mastery moves on multi-day FSRS
intervals; daily gate-watching invites data-fiddling.

## Phase 4 — promotion (DECISION GATE)

Trigger: `gate_report.py` prints `READY -> --advance` for the active unit, i.e.
`--check` prints:

```
thema_13 — 139 карточек | mastery≥3: ≥112/139 (≥80.x%) | красных: 0
✅ готов дальше — запусти --advance
```

Protocol — in order, no skipping:

1. Paste the literal `--check` output into the owner conversation. Output, not a
   paraphrase — success is the gate line.
2. Owner confirms promotion AND that the next unit (thema_14) is what study
   moves to. `--advance` immediately imports thema_14 — which is grammatica-only
   on disk (no taak dirs, no woordenlijst → vocab 0, grammar clozes only, all
   due tomorrow). If real study jumps elsewhere, repoint (Phase 1 pattern)
   instead of advancing.
3. `python3 scripts/fluent_import.py --course link --advance` Expected:
   `→ active: thema_14 | added N` (N = t14 grammar clozes).
4. Re-run Phase 0 diagnostics; commit `link/curriculum.json` (the advance
   rewrote it) via `nederlands-change-control`.

## Rollback

Every mutating step above left a snapshot:

| What broke                            | Restore                                                                                                                                 |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| spaced-repetition.json (import/defer) | `cp ~/.claude/fluent-data/.backups/<pre-import-\|pre-defer-><ts>/spaced-repetition.json ~/.claude/fluent-data/`                         |
| curriculum.json (repoint)             | `cp ~/.claude/curriculum.json.pre-repoint-<date> link/curriculum.json` (or `git checkout -- link/curriculum.json` if not yet committed) |

Full restore runbook: `nederlands-run-and-operate`.

## Provenance and maintenance

All numbers date-stamped 2026-07-10 and VOLATILE. Re-verify with:

- Baseline numbers (items, dues, histogram, cap, sessions) and the per-unit gate
  table / active unit — the two Phase 0 commands:

  ```bash
  python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/fluent_health.py
  python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/gate_report.py --course link
  ```

- Gate formula, one-active invariant, advance-writes-manifest, new-item
  due=tomorrow: read `scripts/fluent_import.py` (MASTERY_THRESHOLD,
  `active_unit`, `advance`, `new_sr_item`).
- Mastery ladder + quality/rating map:
  `grep -n -A6 mastery_level ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/update-db.py`
- Cap serving path:
  `grep -n review_items_per_day ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/read-db.py`
- Interval table: re-simulate by importing `fsrs` from the cache hooks dir and
  calling `fsrs.schedule(state, rating, date, None)` in a loop (weights None =
  DEFAULT_W; if `metadata.weights` is no longer null, re-simulate with the live
  weights).
- Owner approvals (repoint in principle, 2026-07-09) are conversation facts:
  RE-CONFIRM with the owner at each decision gate; never treat this file as
  consent.
- defer*dues.py behavior: test against a copy first — `cp
  ~/.claude/fluent-data/spaced-repetition.json /tmp/x/ && python3
  .claude/skills/fluent-backlog-campaign/scripts/defer_dues.py --prefix link_t4*
  --days 14 --data-dir /tmp/x`

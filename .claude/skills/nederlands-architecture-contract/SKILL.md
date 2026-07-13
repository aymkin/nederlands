---
name: nederlands-architecture-contract
description: >-
  Use when deciding whether a design change to this repo or the Fluent ecosystem
  is safe — e.g. tempted to make fluent_import.py call update-db.py, to
  hand-edit DEFAULT_W in fsrs.py, to write item.difficulty, to add pip deps to
  runtime hooks, to bump the plugin version past 0.3.0, to renumber grammar
  modules, or when hitting "expected exactly 1 active unit", fsrs_difficulty vs
  difficulty confusion, or asking why the importer "bypasses" the DB updater.
  Also the index of known-weak points.
---

# Architecture contract — nederlands + Fluent

The load-bearing design decisions of this repo and its Fluent spaced-repetition
ecosystem: what each decision is, WHY it exists, the invariant that must hold,
and how to re-verify it. Violating any invariant here is a change-control event,
not a refactor.

**When NOT to use this skill:** for the step-by-step gating procedure of a
change use `nederlands-change-control`; for the incident history behind each
rule use `nederlands-failure-archaeology`; for FSRS-6 math and the mastery state
machine use `nt2-srs-reference`; for live config values and defaults use
`nederlands-config-and-flags`.

Jargon, once: _Fluent_ = a Claude Code tutor plugin with 6 JSON databases in
`~/.claude/fluent-data/`. _SR_ = spaced repetition. _FSRS-6_ = the scheduling
algorithm (successor to SM-2). _thema/taak_ = unit/task of the Link NT2 course.
All facts below verified 2026-07-09.

## 1. Two-owner invariant (sequence vs scheduling)

- `link/curriculum.json` owns COURSE SEQUENCE: 17 units (`thema_4`…`thema_20`,
  as of 2026-07-09 `thema_4` active, 16 locked), each
  `{id, grammar_file, grammar_modules, status}`. Exactly ONE unit may be
  `active` — `scripts/fluent_import.py` raises
  `ValueError("expected exactly 1 active unit, got N")` otherwise
  (`active_unit()`, lines 43–47).
- Fluent owns SCHEDULING: intervals, due dates, stability. The importer seeds
  new items and rebuilds the queue; it NEVER modifies an existing item
  (`add_items()` skips ids already in the store, line 211).
- The importer writes ONLY `~/.claude/fluent-data/spaced-repetition.json`
  (`write_sr()`), and it bypasses the plugin's `update-db.py` ON PURPOSE:
  update-db.py treats every call as a learning session and would falsely
  increment session count and streak. Do not "fix" this by routing the import
  through update-db.py.

Why: one writer per concern. Curriculum edits can't corrupt review state; review
sessions can't move the course pointer.

## 2. Stdlib-only runtime hooks

Runtime hooks in the plugin cache (`fsrs.py` 168 ln, `update-db.py` 628 ln,
`read-db.py`, …) and `scripts/fluent_import.py` (333 ln) import ONLY the Python
standard library. Why: hooks run in whatever `python3` Claude Code finds — there
is no venv guarantee at hook runtime. Heavy deps (torch, fsrs-optimizer) are
isolated in the offline optimizer venv `~/.claude/fluent-data/.venv-optimizer/`,
invoked only by the weekly LaunchAgent. Adding a pip import to any runtime hook
breaks every session on a machine without that package.

Corollary: `fsrs.py` is a hand-port of py-fsrs pinned at 6.3.1. `DEFAULT_W` (21
floats) was extracted programmatically from the pinned package — never hand-edit
it; the file header gives the extraction command.

## 3. Fork-based plugin distribution — four locations

Fluent is forked `m98/fluent` → `aymkin/fluent`; the **fork is the source of
truth** for all FSRS code. Upstream `m98/fluent` has no FSRS scheduler. On
2026-07-11 the marketplace was **repointed from upstream to the fork**
(`known_marketplaces.json` key `m98` → `source.repo` = `aymkin/fluent`), so the
daily 09:03 `git pull` now tracks the fork and materializes FSRS instead of
clobbering it.

| Location                                    | Role                     | Authoritative for           |
| ------------------------------------------- | ------------------------ | --------------------------- |
| `~/Projects/fluent`                         | dev clone of the fork    | new code, commits           |
| `~/.claude/plugins/marketplaces/m98/`       | marketplace clone (fork) | what the daily pull updates |
| `~/.claude/plugins/cache/m98/fluent/0.3.0/` | **the runtime**          | what actually executes      |
| `~/.claude/fluent-data/`                    | data dir (6 JSONs)       | learner state               |

**The topology has a deliberate quirk — verify it, never assume** (repointed and
verified 2026-07-11):

- The marketplace clone's `origin` is now the **fork `aymkin/fluent`** (HEAD
  `4205bf1`), not upstream; its `.claude/hooks/` now carries `fsrs.py`,
  `migrate_to_fsrs.py`, and `optimize_weights.py`. Before the 2026-07-11 repoint
  it tracked upstream `m98/fluent` (HEAD `86fb80f`) with no FSRS hooks, so a
  cache rebuild from it would silently revert the scheduler to SM-2 — that
  danger is now **resolved at the source**. Config backup:
  `~/.claude/known_marketplaces.json.pre-fork-20260711-222851`.
- The marketplace KEY stays named `m98` **on purpose** — the name is baked into
  the cache path `cache/m98/fluent/0.3.0`, the plugin id `fluent@m98`, and the
  optimizer plist's hardcoded path; renaming would move all three.
- The dev clone (`~/Projects/fluent`, origin = `aymkin/fluent`, upstream =
  `m98/fluent`, HEAD `4205bf1`) is unchanged; it and the **cache** both contain
  the FSRS hooks.
- Claude Code executes hooks from the CACHE. Editing a clone changes nothing
  until synced to the cache.
- **Remaining open point (no longer dangerous):** `read-db.py` was synced
  fork→cache on 2026-07-11 (review payload 40,953→27,581 B; per-item
  `review_history` no longer shipped to the prompt). The only remaining
  cache↔fork drift is `migrate_to_fsrs.py` — a one-time migration script, dead
  in normal ops. The fork→cache sync is still a manual, undocumented copy, but
  both sides carry FSRS, so a rebuild materializes FSRS rather than wiping it.
  After any hook edit, run the `diff -rq` below and reconcile.
- **New tradeoff:** upstream `m98` updates are no longer auto-tracked. Merge
  upstream fixes into the fork by hand —
  `git -C ~/Projects/fluent fetch upstream && git merge upstream/main` — then
  push.

Verify live before trusting any of the above:

```bash
git -C ~/.claude/plugins/marketplaces/m98 remote -v      # origin = aymkin/fluent (repointed 2026-07-11)
git -C ~/Projects/fluent log -1 --format=%h              # fork dev clone
git -C ~/.claude/plugins/marketplaces/m98 log -1 --format=%h
ls ~/.claude/plugins/marketplaces/m98/.claude/hooks/fsrs.py   # clone now HAS FSRS
diff -rq ~/Projects/fluent/.claude/hooks \
  ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks
# expected: only migrate_to_fsrs.py differs (dead one-time script); read-db.py + fsrs.py match (synced 2026-07-11)
```

A version bump 0.3.0→x changes the cache path AND silently breaks the optimizer
LaunchAgent, whose plist hardcodes
`.../cache/m98/fluent/0.3.0/.claude/hooks/optimize_weights.py`.

## 4. item_id idempotency schemes (and their asymmetry)

Import is idempotent because ids are deterministic — re-running never
duplicates. But the two schemes fail differently under content edits:

- **Vocab — slug-stable:** `link_t8_voc_taak1_de-buurt`
  (`{course}_t{N}_voc_{taakK}_{slug(word)}`, fluent_import.py:100). Editing a
  word's translation and re-importing does NOT update the card (existing ids are
  skipped); editing the word itself creates a NEW card and orphans the old one.
- **Grammar — POSITIONAL:** `link_t12_gram_3.8_10`
  (`{course}_t{N}_gram_{module}_{idx}`, line 157) where `idx` is the ordinal of
  the bold example within the module. Inserting/deleting/reordering bold
  examples in a grammatica file AFTER import shifts every later idx: review
  history silently attaches to the wrong sentences. **Edit grammar files BEFORE
  importing a thema; treat imported grammar sections as append-only.**
- Module numbers (`## 3.8 …`) are the Link book's own numbering, consumed by
  `curriculum.json.grammar_modules` — never renumber.
- Vocab source glob: `*woordenlijst*thema{N}*_anki.txt` under the thema dir
  (line 93). A woordenlijst file missing `thema{N}` in its name is silently not
  imported. Grammar file resolves thema-folder-first, then `link/gramatica/`
  fallback — that dir no longer exists (dead-path compat).

## 5. FSRS-6 field layout — the `difficulty` collision

Per SR item (verified against live data 2026-07-09):

| Field             | Meaning                                             |
| ----------------- | --------------------------------------------------- |
| `difficulty`      | CEFR level STRING (e.g. `"A2"`) — legacy, human     |
| `fsrs_difficulty` | FSRS numeric difficulty 1.0–10.0 (or `null` if new) |
| `stability`       | FSRS stability in days (or `null` if new)           |
| `last_rating`     | last FSRS rating 1–4 (absent until first review)    |

`fsrs.py:schedule()` takes a state dict whose key is `difficulty` (numeric);
`update-db.py` (lines 389–398) maps `item["fsrs_difficulty"]` into that dict and
writes `r["difficulty"]` back to `item["fsrs_difficulty"]`. Writing FSRS
difficulty into `item["difficulty"]` was a real pre-ship bug (repo commit
`350de1a`, fork `44fb945`). Any new code touching items MUST preserve this
mapping.

Scheduler authority: `spaced-repetition.json` `metadata.scheduler: "fsrs-6"` is
authoritative. A legacy `metadata.algorithm` key exists; it was stale (`"SM-2"`)
until fork commit `4205bf1` stamped it — as of 2026-07-09 both read FSRS-6, but
trust `scheduler`. `metadata.weights: null` means hooks use `DEFAULT_W`.
`calculate_sm2` is retained in update-db.py as rollback only.

Two `review_history` keys trap: the top-level
`spaced-repetition.json.review_history` is an EMPTY legacy list; real reviews
live per-item in `items[*].review_history` (sum = 225 on 2026-07-09).
Diagnostics must count per-item.

## 6. Guarded weight optimizer (400/50)

Weekly LaunchAgent `com.aymkin.fluent-fsrs-optimize.plist` (Sunday 09:05, venv
python against the CACHE path). `optimize_weights.py` guards: `MIN_TOTAL = 400`
total reviews AND `MIN_NEW = 50` since last optimize, else no-op. Why: FSRS-6
has 21 free parameters; fitting them on a few hundred reviews overfits and can
produce worse scheduling than `DEFAULT_W`. It has run once ever:
`[optimize] insufficient data (185/400, +185 new) — no-op` (log
`~/.claude/logs/fluent-fsrs-optimize.log`). It derives ratings from per-item
`quality` (0–5 → 1–4), never from `score` (historically unreliable 0).
fsrs-optimizer's API broke once on upgrade (fork `133308c`) — expect breakage on
pip upgrades in the venv.

## 7. Daily review cap — code trims, prompts enforce

`read-db.py --review` sorts today's queue by priority (critical<high<medium<low)
and slices to `spaced-repetition.json.daily_limits.review_items_per_day` (code
default 20; LIVE value 30 as of 2026-07-09). That trims the PAYLOAD — but
nothing in python rejects extra reviews: `update-db.py` accepts any
`review_results[]`. The cap is enforced only by the plugin skills' prompts.
**Known weakness:** any flow that bypasses the fluent-review skill bypasses the
cap. Note `daily_limits` lives inside spaced-repetition.json itself, not
learner-profile.json.

## 8. Backup-everything-before-write contract

Every writer snapshots to `~/.claude/fluent-data/.backups/` BEFORE writing, then
writes atomically (tmp file + replace):

| Writer               | Backup dir                        | Scope        |
| -------------------- | --------------------------------- | ------------ |
| `update-db.py`       | `pre-update-<session_id>/`        | all 6 DBs    |
| `fluent_import.py`   | `pre-import-<YYYY-MM-DD-HHMMSS>/` | SR file only |
| `migrate_to_fsrs.py` | `pre-migrate-fsrs-<ts>/`          | (one-time)   |
| daily snapshot       | `YYYYMMDD/`                       | all 6 DBs    |

Restore = plain copy back, all-or-nothing per snapshot dir (runbook:
`nederlands-run-and-operate`). New writers MUST follow this contract — the
timestamped import dir exists because a date-only name once collided same-day
(hardened in repo commit `a88b1ff`).

## 9. Queue rebuild semantics

`fluent_import.py:rebuild_queue()` rebuilds `review_queue` from scratch into 4
buckets — `today` (due ≤ today, i.e. includes overdue), `tomorrow`, `this_week`
(≤ today+7), `later` — comparing ISO `YYYY-MM-DD` STRINGS lexicographically
(safe only because the format is fixed; never introduce another date format into
`due_date`). It does not cap or priority-sort — that is `read-db.py --review`'s
job at read time. It also stamps `metadata.last_updated` and
`total_items_tracked`. As of 2026-07-09: 408 items; queue 335/12/15/46 (a
backlog — see `fluent-backlog-campaign`).

## 10. Public-by-default deploy

`.github/workflows/pages.yml` (the only CI) deploys the ENTIRE repo (`path: .`)
to GitHub Pages on every push to main. Sole exclusion:
`rm -f other/nieuw_in_rotterdam/*.epub *.pdf`. Everything else tracked — PDFs,
mp3s, transcripts, graded tests — publishes within minutes. Treat `git commit`
on main as "publish to the internet". Policy is unexamined (open); surface
inventory: `nederlands-external-positioning`.

## 11. read.html — the single external runtime dependency

`read.html` at repo root is the only public reading UI: a client-side markdown
reader (`?f=<repo-relative path>`) that loads `marked@13.0.2` from the jsdelivr
CDN — the ONE external runtime dependency in the whole system. It rejects `..`,
absolute, and `http(s):` paths (line 191). CDN outage or package retraction
kills story reading; everything else is offline.

## Known-weak points (open, verified 2026-07-09)

1. The SM-2-reversion danger is **resolved** (2026-07-11 marketplace repoint to
   the fork — §3): the marketplace clone now carries the FSRS hooks. Remaining:
   after the 2026-07-11 `read-db.py` sync the only cache↔fork drift is
   `migrate_to_fsrs.py` (a dead one-time script; `read-db.py` + `fsrs.py` now
   match), and the fork→cache sync is still manual/undocumented — no longer
   dangerous (both sides carry FSRS), but reconcile with the §3 `diff -rq` after
   any hook edit.
2. Optimizer plist hardcodes cache version `0.3.0` — breaks on version bump.
3. Daily review cap is prompt-enforced only (§7).
4. `build_vocab_index.py` has no `link_plus` support (choices are
   `link|de_opmaat|both`); `link_plus/woordenlijst_index.txt` is a stale
   pre-rename snapshot.
5. CLAUDE.md drift: calls the abandoned maart*2026 plan "active"; claims `link/`
   task dirs are `{N}*{task*name}`— disk reality is plain`taak_N`(verified`ls
   link/thema_8`); understates `.prettierignore`(it also ignores`\*\*/verhaal*_.md`, `_\_reader.html`).
6. `scripts/README.md` says "21 passed" for the importer tests; running
   `python3 scripts/test_fluent_import.py` gives **25 passed** (verified
   2026-07-09). The README is stale — do not delete tests to match it.
7. `package.json` name is `de_opmaat` with a stale description — don't trust its
   repository URLs.
8. Plugin skill `fluent-sm2-calculator` still documents SM-2 while the runtime
   scheduler is FSRS-6 (live since 2026-07-04) — it is partially stale; trust
   `fsrs.py` and `metadata.scheduler`.

## Provenance and maintenance

Verified 2026-07-09 against disk and live data. Re-verify before relying on:

- Importer writes only SR / skips existing ids: read `scripts/fluent_import.py`
  (`write_sr`, `add_items`, `rebuild_queue`).
- Clone/cache/marketplace heads: §3 commands.
- Pages deploy scope: read `.github/workflows/pages.yml` (`path: .`).
- Test count: `python3 scripts/test_fluent_import.py` (tempdir-isolated, safe).
- The rest:

```bash
# one-active-unit + statuses
python3 -c "import json; u=json.load(open('link/curriculum.json'))['units']; \
print([(x['id'], x['status']) for x in u if x['status'] != 'locked'])"

# scheduler + weights + daily_limits + queue sizes
python3 - <<'EOF'
import json, pathlib
d = json.loads((pathlib.Path.home()
    / ".claude/fluent-data/spaced-repetition.json").read_text())
print(d["metadata"].get("scheduler"), d["metadata"].get("weights"),
      d.get("daily_limits"),
      {k: len(v) for k, v in d["review_queue"].items()})
EOF

CACHE=~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks
grep -n "MIN_TOTAL\|MIN_NEW" "$CACHE/optimize_weights.py"   # optimizer guards
grep -n "fsrs_difficulty" "$CACHE/update-db.py"             # field mapping
grep -n "0.3.0\|Weekday" \
  ~/Library/LaunchAgents/com.aymkin.fluent-fsrs-optimize.plist  # hardcode
grep -n jsdelivr read.html                                  # the CDN dep
```

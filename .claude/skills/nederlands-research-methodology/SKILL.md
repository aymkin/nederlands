---
name: nederlands-research-methodology
description: >-
  Use when turning a hunch into an accepted result in this repo or the Fluent
  fork — proposing an experiment, a new algorithm (scheduler, optimizer,
  alignment), a study-plan or process change; before declaring a fix "works";
  when writing or retiring a design spec/plan under docs/superpowers/; when a
  claimed result has no predicted number; when a doc claim (test counts, levels,
  line pointers) disagrees with disk; or when tempted to build a new templated
  system before evidence anyone follows it.
---

# Research methodology: hunch → accepted result

How ideas earn their way into this project. Every rule below is backed by a real
incident in this repo's history — commands to re-verify each one are in the
Provenance section.

**When NOT to use this skill:** for the concrete measurement/analysis techniques
themselves (probes, counting, bisection), use
`nederlands-proof-and-analysis-toolkit`. For whether an already-proven change is
_allowed_ to land (gating, non-negotiables), use `nederlands-change-control`.
For the catalog of past failures, use `nederlands-failure-archaeology`.

## 1. The evidence bar

A result is accepted here only when BOTH hold:

1. **One mechanism explains ALL observations — including the negatives.** A
   theory that explains the failing case but not why the passing case passes is
   not done. Example: the story-reader drift fix (commit `e6f41db`) was accepted
   because the mechanism (edge-tts VTT cues split on `!`/`?`/`:` → more cues
   than sentences → `match_timings()` exhausts cues and pins the highlight at
   audio-end) explained both why the highlight froze late in the story AND why
   short stories never showed the bug.
2. **It survives adversarial review before shipping.** Assign a review pass
   whose job is to break the design, not admire it. The `fsrs_difficulty`
   collision was caught exactly this way: the FSRS implementation commit (fork
   `f059eff`, 2026-07-04) wrote FSRS numeric difficulty into the item key
   `difficulty` — which already held the CEFR level STRING ("A2"). A pre-ship
   review caught it the same day; fix `44fb945` (fork) landed BEFORE the
   migration script (`4d35f9f`) ever touched live data, and the docs were
   corrected in nederlands `350de1a` ("collision found in review"). Cost of the
   review: minutes. Cost if shipped: silent corruption of every card's CEFR
   level.

Use the superpowers plugin skills for this when available:
`superpowers:requesting-code-review` for the adversarial pass,
`superpowers:verification-before-completion` before any "it works" claim.

## 2. Predict the numbers BEFORE running

Write down the number the hypothesis predicts, then run. If you only look at the
output and rationalize it afterwards, you have measured nothing. Three worked
examples from this repo (all verifiable, see Provenance):

1. **Optimizer guard.** The plan (2026-07-03) wrote the exact expected log line
   before the code ever ran:
   `[optimize] insufficient data (165/400, +165 new) — no-op`. The first live
   run logged `insufficient data (185/400, +185 new) — no-op` — identical shape;
   the count grew 165→185 only because reviews accrued between plan-writing and
   the run.
2. **Payload trim.** Baseline measured first (~444KB / 13k lines pushed into the
   model's context to review 30 cards), then each cut measured against it:
   `--review` payload 82393 → 43000 bytes, −90.3% vs the original dump (fork
   commits `281c2a4`, `13fd374`).
3. **Alignment fix.** The mechanism (word-level Whisper timestamps + fuzzy
   matching) predicts EVERY sentence aligns, not merely more of them. Run
   confirmed: `285/285 sentences aligned (was drifting past ~270)` (`e6f41db`).

Notes on the discipline:

- A prediction that says "it should be better" is not a prediction. "285/285"
  is. "no-op with this exact message" is.
- When predicted and actual differ, the difference must itself be explained by
  the mechanism (165→185 above: reviews accumulated for 5 days — the guard logic
  was exactly as predicted).
- Record the baseline BEFORE changing anything. The payload trim is only
  provable as −90.3% because the 444KB baseline was measured and written into
  the commit body first.

## 3. The idea lifecycle in this repo

1. **Brainstorm** — decisions locked interactively, captured in the spec (the
   `superpowers:brainstorming` skill drives this).
2. **Design spec** — `docs/superpowers/specs/YYYY-MM-DD-slug-design.md`. Must
   carry a **Status** line and a locked-decisions section.
3. **Implementation plan** — `docs/superpowers/plans/YYYY-MM-DD-slug.md` (same
   slug, no `-design` suffix). Checkbox tasks, TDD micro-steps: write failing
   test → run to see it fail → implement → run green → commit.
4. **Live verification** — predict-then-run against real data (Section 2).
5. **Record** — update memory / docs of record; tick plan checkboxes.
6. **OR retire** — documented pause/retirement (see below).

The two real spec/plan pairs to copy the format from (verified on disk
2026-07-10):

- `docs/superpowers/specs/2026-06-26-fluent-curriculum-bridge-design.md`
  (Russian; header `Статус: утверждён, готов к плану реализации`) +
  `docs/superpowers/plans/2026-06-26-fluent-curriculum-bridge.md` (41 checkbox
  tasks).
- `docs/superpowers/specs/2026-07-03-fluent-fsrs-scheduler-design.md` (header
  `**Status:** approved (design), pending implementation plan`; section
  `## Decisions (locked during brainstorming)`) +
  `docs/superpowers/plans/2026-07-03-fluent-fsrs-scheduler.md` (52 checkbox
  tasks; steps literally named "Write the failing invariant test" / "Run the
  test to verify it fails").

### Documented retirement

Dead ends are results too — but only if written down so nobody re-runs them. The
template is the Parkiet pause commit (`1a6d78a`, 2026-04-17). Its message
states, in order:

1. **What was tested** — Parkiet multi-voice TTS, `[S1]-[S4]` speaker tags,
   first 10 sentences of a verhaal, three rendering modes (normal,
   ellipsis-paced, slowed), single- vs multi-voice on 10 excerpts.
2. **State committed as checkpoint** — the runner script + 50 MP3 samples, so
   resuming needs zero re-setup.
3. **Why paused and what would resume it** — "future work may integrate Parkiet
   into story_reader.py if multi-voice quality warrants the extra dependency
   (currently on edge-tts)."

Write retirements in exactly this shape: tested / checkpoint / resume condition.
Then record the retirement in `nederlands-failure-archaeology`'s domain (the
incident chronicle) so future sessions check there first.

## 4. Experiment hygiene

- **Date-stamp everything.** Spec/plan filenames start `YYYY-MM-DD-`; commit
  bodies say "After day 1 experiment: …" (`4774cb5`). Live-state numbers (queue
  sizes, review counts) drift daily — a number without a date is noise.
- **Backup before any data mutation.** Both mutation paths do this automatically
  and you must preserve that: `fluent_import.py` copies `spaced-repetition.json`
  to `.backups/pre-import-<timestamp>/` before every write
  (scripts/fluent_import.py:240-242); `update-db.py` runs `backup_all()` for all
  6 DBs before writing. Any new experiment that touches `~/.claude/fluent-data/`
  must snapshot first, same pattern.
- **One variable at a time.** The Parkiet experiment compared three rendering
  modes and single- vs multi-voice as separate renders, not one blended run. The
  payload trim landed as two commits, each with its own before/after
  measurement.
- **Record negative results next to positive ones.** Commit `4774cb5`
  (2026-02-25) records "NPOkennis <10% comprehension, Peppa Pig 90%+" in the
  same sentence — the <10% is what made the plan revision defensible. A log that
  only keeps wins cannot calibrate the next estimate.

## 5. Where good ideas historically came from

| Source                          | Instance                              |
| ------------------------------- | ------------------------------------- |
| Adversarial review pre-ship     | `fsrs_difficulty` collision (fork     |
|                                 | `44fb945`, nederlands `350de1a`)      |
| Day-1 reality check demolishing | Listening-level estimate wrong on day |
| an assumption                   | 1 → Comfort/Challenge/Stretch tiers   |
|                                 | (`4774cb5`)                           |
| Measuring instead of assuming   | 444KB→43KB `--review` payload, −90.3% |
|                                 | (fork `281c2a4`, `13fd374`)           |
| Upstream algorithm research     | SM-2 → FSRS-6: spec cites FSRS as     |
|                                 | Anki's default since 23.10; port      |
|                                 | pinned against py-fsrs 6.3.1 with a   |
|                                 | cross-check test as correctness gate  |

Common thread: the idea came from contact with reality (a review, a day of real
use, a byte count, upstream literature) — never from adding process.

## 6. Anti-patterns (each one happened here)

1. **Heavyweight process built before evidence of adherence.** Two templated
   study-plan systems died within days:
   - `daily/maart_2026/` — full month of pre-filled daily lesson files, created
     2026-02-25; git shows real day-execution commits only for 26–27 Feb, then
     nothing but a formatting touch on 2026-04-10.
   - The April "Mikel method / Language Islands" experiment (`e379c80`,
     2026-04-14) — one follow-up commit, then abandoned (owner-confirmed
     2026-07-09). The owner's standing rule (2026-07-09): never create
     heavyweight templated study-plan systems; new processes must be light and
     course-anchored. What survived instead: the Link-at-Danner course loop +
     Fluent. Before building any recurring-process artifact, demand evidence the
     lightweight version was actually followed for 2+ weeks.
2. **Trusting docs over disk.** `scripts/README.md` says the importer test suite
   yields "21 passed"; running it yields **25 passed** (verified 2026-07-10:
   `python3 scripts/test_fluent_import.py`). The README is stale — do NOT "fix"
   tests down to match docs. Same class of drift: CLAUDE.md still calls the
   maart_2026 plan "active". Disk and executed commands are ground truth; docs
   are hypotheses about ground truth.
3. **Post-hoc rationalization.** If the number wasn't predicted (or the baseline
   wasn't captured) before the run, rerun the experiment properly rather than
   narrating the output you happened to get.

## Provenance and maintenance

Verified 2026-07-10 unless noted. Re-verify before relying on a claim:

- Collision caught in review: `git show --stat 350de1a` and
  `git -C ~/Projects/fluent show -s f059eff 44fb945 4d35f9f` (dates show the
  order: implement → collision fix → migration).
- Optimizer prediction vs run:
  `grep -n "insufficient data" docs/superpowers/plans/2026-07-03-*.md` (predicts
  165/400) vs `cat ~/.claude/logs/fluent-fsrs-optimize.log` (actual
  `185/400, +185 new`). The log grows — check the latest line.
- Payload trim numbers:
  `git -C ~/Projects/fluent show -s --format='%b' 281c2a4 13fd374`.
- Alignment 285/285: `git show --no-patch --format='%b' e6f41db`.
- Spec/plan pairs and format: `ls docs/superpowers/{specs,plans}/`;
  `head -8 docs/superpowers/specs/2026-07-03-fluent-fsrs-scheduler-design.md`;
  checkbox counts `grep -c '^- \[' docs/superpowers/plans/*.md`.
- Parkiet retirement template: `git show --no-patch --format='%b' 1a6d78a`.
- Negative result recorded: `git show --no-patch --format='%b' 4774cb5`.
- Importer backup-before-write: `grep -n "pre-import" scripts/fluent_import.py`.
- Dead study plans:
  `git log --date=short --format='%ad %s' -- daily/maart_2026/` (commits cluster
  on 2026-02-25..27 only); `git show --no-patch e379c80`.
- README vs reality: `python3 scripts/test_fluent_import.py | tail -1` vs
  `sed -n '535,545p' scripts/README.md`.
- py-fsrs pin: `head -8 ~/Projects/fluent/.claude/hooks/fsrs.py`.

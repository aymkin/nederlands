---
name: nederlands-research-frontier
description:
  Use when asked what research-grade or novel work this project enables, whether
  personal FSRS weights can beat DEFAULT_W on one learner's small review log,
  how to evaluate fitted weights on a held-out slice before adopting them
  (fsrs_holdout_eval.py, log-loss), whether the 400-review optimizer guard is
  justified, how to close the loop error_patterns → targeted content → toets
  results, or how to generate stories constrained to learned vocabulary with
  measured coverage.
---

# Research frontier: the three chosen open problems

Three open problems where this repo's assets could push past the current state
of the art. Chosen by the project owner (2026-07-09); the rejected fourth
candidate was a multi-voice TTS pipeline.

**Status discipline: everything in this file is OPEN or CANDIDATE. Nothing below
is claimed as achieved.** A "result" exists only when the falsifiable milestone
is met and documented per `nederlands-research-methodology` (pre-register
predictions, then measure). Any change to repo scripts, plugin hooks, commands,
or `~/.claude/fluent-data/` that these problems suggest goes through
`nederlands-change-control` first — this skill proposes, it does not authorize.

**When NOT to use this skill:** for running the existing systems use
`nederlands-run-and-operate`; for FSRS-6 math and mastery rules use
`nt2-srs-reference`; for the evidence bar and idea lifecycle use
`nederlands-research-methodology`; for measurement probes use
`nederlands-diagnostics-and-tooling`; for draining the review backlog (a
prerequisite for problem 1's data) use `fluent-backlog-campaign`.

---

## Problem 1 — Personal FSRS weight optimization on small data

### Why current SOTA fails

`fsrs-optimizer` (installed: 6.5.0 in `~/.claude/fluent-data/.venv-optimizer/`)
is built for Anki-scale review logs — thousands to millions of reviews. On a few
hundred reviews the fit can be worse than the population-default weights, which
is exactly why this project's weekly optimizer is guarded: `optimize_weights.py`
hard-codes `MIN_TOTAL = 400` and `MIN_NEW = 50` and no-ops below them (its only
run ever printed `insufficient data (185/400)`). The open question SOTA does not
answer: _at what point, and with what safeguards, do personally fitted weights
actually beat DEFAULT_W for one learner?_

Critically, the current adoption path has **no held-out check at all**: once the
guard passes, `optimize_weights.py` trains and writes `metadata.weights`
unconditionally (backup, then overwrite). The guard is a data-quantity proxy,
not a quality check.

### This project's asset

- A complete, clean, single-learner review log. As of 2026-07-10: 408 SR items,
  225 per-item reviews (sum over `items[*].review_history`; the top-level
  `review_history` key is an empty legacy list — never count that one). Quality
  distribution {5: 112, 4: 52, 3: 29, 2: 13, 1: 16, 0: 3}.
- Each review record is exactly `{date, quality, score}`. `score` is
  historically unreliable (often 0) — the optimizer derives rating from
  `quality` only (`_rating()`: q<3→1, q=3→2, q=4→3, else 4). Session context
  (accuracy, skills practiced, command used) is joinable by date from
  `session-log.json` (21 sessions as of 2026-07-10) — it is NOT inside the
  review records themselves.
- A live, guarded optimizer that self-activates (LaunchAgent
  `com.aymkin.fluent-fsrs-optimize`, Sun 09:05) — a real deployment target for
  any improvement, not a toy.
- The exact production scheduler as an importable module: `fsrs.py` in the
  plugin cache (stdlib FSRS-6 port pinned against py-fsrs 6.3.1, 21-float
  DEFAULT_W — never hand-edit).

### First three steps (in this repo)

1. **Held-out evaluation harness — CANDIDATE shipped.**
   `scripts/fsrs_holdout_eval.py` (in this skill dir) replays every item's
   history chronologically through the cache's own `fsrs.py`, predicts recall
   via `retrievability(elapsed, stability)`, and scores log-loss/RMSE on reviews
   after a chronological `--split-date`, against a base-rate baseline. Read-only
   on fluent-data.

   ```bash
   python3 .claude/skills/nederlands-research-frontier/scripts/\
   fsrs_holdout_eval.py --split-date 2026-07-01
   # candidate weights:
   #   ... --split-date 2026-07-01 --weights-file fitted.json
   ```

   First run (2026-07-10, DEFAULT_W, split 2026-07-01): 125 scorable predictions
   of 225 reviews (first reviews and same-day repeats are unscoreable); held-out
   n=42, log_loss 0.3378, rmse 0.3224 vs constant-baseline log_loss 0.4124. So
   DEFAULT_W already beats the base rate — the bar a personal fit must clear. If
   this harness proves useful, propose promoting it to `scripts/` proper via
   `nederlands-change-control`.

2. **Pre-adoption comparison at optimizer activation.** When the 400/50 guard
   finally passes (backlog draining will accelerate this — see
   `fluent-backlog-campaign`), do NOT let fitted weights stand unexamined. Fit
   on reviews before a split date, evaluate both DEFAULT_W and the fitted vector
   on the held-out slice with the harness, and only keep `metadata.weights` if
   fitted wins. Two routes, both via change control:
   - _Manual (no code change):_ after the Sunday run, extract the new
     `metadata.weights`, evaluate, and if it loses restore the
     `pre-optimize-<date>` backup (restore runbook:
     `nederlands-run-and-operate`).
   - _Structural (preferred, larger change):_ add the held-out gate inside
     `optimize_weights.py` in the fork — this touches the plugin clone→cache
     sync, a documented weak point (`nederlands-architecture-contract`).

3. **Document adopt/reject as a dated experiment.** Pre-register the prediction
   ("fitted will/will not beat DEFAULT_W held-out log-loss") before the guard
   passes, per `nederlands-research-methodology`. A rejection is a
   publishable-grade result too: it validates the guard's floor empirically for
   the small-data regime.

### You have a result when…

Fitted weights beat DEFAULT_W on held-out log-loss over **≥100 held-out scorable
predictions** (chronological split, harness above). If they do not, the guard
was right — record that with the numbers. As of 2026-07-10 this milestone is not
yet testable: 225 total reviews (guard needs 400) and only 42 held-out
predictions at a 2026-07-01 split. Do not weaken the milestone to fit the data.

---

## Problem 2 — Closed-loop AI tutoring measured by real exam results

### Why current SOTA fails

SRS apps (Anki, SuperMemo, FSRS-based tools) schedule _what you gave them_ —
they never generate remediation content from your error profile. AI tutors
generate content but rarely persist structured error histories, and almost never
validate against real course exams. The loop "error observed → error scheduled
for review → targeted content generated → recurrence measured → real toets
score" is not closed anywhere mainstream.

### This project's asset

Every stage of that loop already exists here, disconnected:

- **Structured error store:** `mistakes-db.json` holds 46 `error_patterns` (dict
  keyed by pattern id) with `frequency`, `severity`, `last_occurred`,
  `examples`, `mastery_level`. Verified 2026-07-10. `update-db.py` increments
  `frequency` by 1 per reported occurrence (line ~299) — frequency deltas per
  session ARE the recurrence signal.
- **Errors are schedulable:** 43 of the 46 patterns are auto-seeded as SR items
  (`type: "error_pattern"`, item id == pattern id, 43/43 id overlap verified
  2026-07-10) — errors already flow into review sessions.
- **Sessions produce new structured errors:** the `/fluent-*` session flow
  reports `errors[]` (each needs `pattern_id`) through `update-db.py`.
- **Content generators in-repo:** `/verhaal` (accepts a target word list in
  brackets and `--level`/`--thema` flags) and `/anki-cards` (mandates recycling
  2–4 words from previous themas per example) — both are prompt commands in
  `.claude/commands/`, editable hooks for pattern-targeted generation.
- **Ground-truth exams:** real toets artifacts exist —
  `presentatie_toets_voorbereiding.md` (tracked, A2 spreken prep) plus a graded
  result PDF (untracked as of 2026-07-10:
  `presentatie_toets_20260702-1747.pdf`), and
  `de_opmaat/thema_*/beoordeling_toets_*.pdf` graded scans.

Top patterns as of 2026-07-10 (by `frequency`): `spelling_vowel_doubling` (6,
moderate, last 2026-07-06), `grammar_word_order_verb_final` (6, **critical**,
last 2026-06-27), `english_interference` (5), `grammar_zijn_perfect_beweging`
(4). All 46 patterns sit at `mastery_level` 0.

### First three steps (in this repo)

1. **Map pattern → generation hook.** For each top-5 pattern write one
   remediation recipe: which command, which flags, which constraint. Example
   (candidate, not yet run): `grammar_word_order_verb_final` →
   `/verhaal --thema 13` with an explicit instruction to maximize
   omdat/als/dat-subclauses, plus a `/anki-cards` drill set where every example
   ends in a verb cluster. Store recipes as a table in a proposal doc; adding
   them to the command files themselves is a change-control item.
2. **Define the recurrence metric before intervening.** Metric: occurrences of
   the target `pattern_id` per session (frequency delta in `mistakes-db.json`)
   over the next N sessions, compared to the trailing N-session rate. Also
   record toets outcomes as the slow outer-loop metric — the presentatie toets
   (2026-07-02) is the first baseline artifact. Pre-register the expected drop
   (`nederlands-research-methodology`).
3. **Run ONE remediation cycle** for a single pre-registered pattern (pick
   `grammar_word_order_verb_final`: highest severity among the most frequent).
   Generate the targeted content, let the learner work it, then read the
   frequency delta over the following sessions. Change nothing else about the
   routine during the window — one variable at a time.

### You have a result when…

A pre-registered error pattern's recurrence rate (occurrences per session) drops
measurably across N≥5 post-intervention sessions relative to its trailing
baseline, while at least one non-targeted pattern of similar frequency does not
drop comparably (crude control). Confound to state up front: reviews of the
seeded error-pattern SR item also train the pattern — attribute honestly or
pause that item's reviews during the window.

---

## Problem 3 — Vocab-constrained generation with measured comprehensibility

### Why current SOTA fails

LLM content generation "at level A2" is judged by eye. Even this repo's own
`/verhaal` command declares that known vocabulary should form the "80% backbone"
of a story and gives per-level new-word budgets (level 1: 8–10 new words, ≤12
words/sentence … level 5: 25–30) — but nothing ever _measures_ whether a
generated story meets its own budget. The project's history shows eyeballing
fails: commit 4774cb5 records that the estimated listening level was wrong on
day one (NPOkennis <10% understood, Peppa Pig 90%), forcing
Comfort/Challenge/Stretch tiers.

### This project's asset

- A machine-readable known-vocabulary set: `link/woordenlijst_index.txt`
  (auto-generated by `python3 scripts/build_vocab_index.py --course link`;
  header says 1031 words as of its last build).
- A shipped measurement primitive: `vocab_coverage.py` in
  `nederlands-diagnostics-and-tooling/scripts/` — tokenizes a text, reports %
  covered by the index, % function words, % unknown, top unknown tokens;
  `--max-thema N` restricts "known" to what the learner has actually reached.
  Documented limitation: no lemmatization, so coverage is a **lower bound**
  (inflected forms of known words count unknown).
- An existing story corpus to baseline: `daily/verhalen/verhaal_*.md` (4 stories
  as of 2026-07-10).

Measured baseline (2026-07-10): `verhaal_2026-04-14_twee_dagen_van_alexander.md`
against the full link index scores 40.2% index-covered + 22.1% function words =
**62.4% "should read"**, 37.6% unknown — far off the command's declared 80%
backbone, though inflation by missing lemmatization and the story's
de_opmaat-era vocabulary both bias this low. That gap between declared and
measured is the research opening.

### First three steps (in this repo)

1. **Baseline the corpus.** Run `vocab_coverage.py` over all four existing
   verhalen against `--course link` (and `--course de_opmaat` for the April
   stories, which were written for that course), with and without `--max-thema`.
   Record the numbers in a dated table — this is the "before" picture.
2. **Make the budget explicit and verified in `/verhaal`.** Propose (via
   `nederlands-change-control`) an addition to `.claude/commands/verhaal.md`:
   every generated story must declare its target tier and new-word budget, and
   the generator must run `vocab_coverage.py` on its own output before
   delivering, printing the coverage block into the story file. Iterate
   generation until the pre-declared target is met.
3. **Calibrate tiers against the learner.** After each verified story, collect a
   one-line comprehension self-report (Comfort / Challenge / Stretch — reuse the
   4774cb5 tier language). Plot measured coverage vs reported tier across ≥10
   stories; adjust the coverage thresholds until prediction matches report.
   Candidate improvement discovered by the baseline run: a cheap
   lemmatization/inflection expansion in the coverage script (e.g. matching
   `zegt/zei` to `zeggen`) would remove the largest known bias — propose it as a
   diagnostics-skill change.

### You have a result when…

A generated story hits a **pre-declared** coverage target (e.g. ≥95% "should
read" tokens = index-covered + function words, at a stated `--max-thema`)
verified by `vocab_coverage.py` — not by eye — AND the learner's comprehension
self-report matches the tier the coverage number predicted, repeatedly
(pre-register the expected mapping first). One story matching once is anecdote;
declare the sample size up front.

---

## Shared ground rules for all three problems

| Rule                                        | Where it's enforced                                     |
| ------------------------------------------- | ------------------------------------------------------- |
| Pre-register predictions before measuring   | `nederlands-research-methodology`                       |
| Any file/DB/plugin mutation gated           | `nederlands-change-control`                             |
| Never write `~/.claude/fluent-data/` ad hoc | two-owner invariant, `nederlands-architecture-contract` |
| Count reviews per-item, never top-level key | `nederlands-diagnostics-and-tooling`                    |
| Label unproven things open/candidate        | this file's own discipline                              |

## Provenance and maintenance

All numbers verified 2026-07-10 on this machine. Re-verify before use (run from
the repo root):

```bash
# review count (per-item; top-level review_history is empty legacy)
python3 -c "import json;d=json.load(open('$HOME/.claude/fluent-data/spaced-repetition.json'));print(sum(len(v.get('review_history',[])) for v in d['items'].values()))"

# optimizer guards, missing held-out check, quality->rating mapping
grep -n "MIN_TOTAL\|MIN_NEW\|def _rating" \
  ~/.claude/plugins/cache/m98/fluent/*/.claude/hooks/optimize_weights.py

# error-pattern count + top frequencies
python3 -c "import json;d=json.load(open('$HOME/.claude/fluent-data/mistakes-db.json'));e=d['error_patterns'];print(len(e),sorted(e,key=lambda k:-e[k]['frequency'])[:5])"

# seeded error-pattern SR items (was 43/46 on 2026-07-10)
python3 -c "import json;d=json.load(open('$HOME/.claude/fluent-data/spaced-repetition.json'));print(sum(1 for v in d['items'].values() if v.get('type')=='error_pattern'))"

# harness still runs against the live plugin cache
python3 .claude/skills/nederlands-research-frontier/scripts/fsrs_holdout_eval.py \
  --split-date 2026-07-01

# vocab index size ("1031 words" header as of last build)
head -3 link/woordenlijst_index.txt

# /verhaal declared budgets and "80% backbone" claim
sed -n '25,55p' .claude/commands/verhaal.md

# coverage baseline (62.4% "should read" on 2026-07-10)
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/vocab_coverage.py \
  daily/verhalen/verhaal_2026-04-14_twee_dagen_van_alexander.md --course link

# toets ground-truth artifacts
git ls-files | grep presentatie
ls de_opmaat/thema_*/beoordeling_toets_*.pdf
```

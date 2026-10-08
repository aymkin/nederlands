---
name: nederlands-diagnostics-and-tooling
description:
  Use when you need numbers instead of impressions from this repo's learning
  system - Fluent review backlog size, queue buckets, mastery histogram, red
  cards, distance to the 80% --advance gate, "review_history looks empty",
  optimizer readiness (400/50 guard), whether a *_anki.txt will import cleanly
  (literal tabs, column count, #html:true with [sound:], tag taxonomy,
  Rusland/Россия scan), or what % of a Dutch text is covered by learned
  vocabulary. Ships four runnable read-only probes.
---

# Diagnostics and tooling: measure, don't eyeball

This repo's failure mode is confident guessing: "the backlog looks big", "thema
12 feels almost done", "this story should be readable". Every one of those has a
number. This skill ships four stdlib-only, read-only scripts in `scripts/`
(relative to this SKILL.md) plus interpretation guides.

**When NOT to use this skill:** if something is already known to be broken and
you need symptom→fix steps, use `nederlands-debugging-playbook`; to actually run
imports/sessions/restores, use `nederlands-run-and-operate`; for what counts as
pass/fail evidence and test suites, use `nederlands-validation-and-qa`; for the
meaning of FSRS/mastery numbers, use `nt2-srs-reference`.

All commands below assume cwd = repo root
(`/Users/Alex.Naymkin/Projects/nederlands`). Every script is read-only: nothing
under `~/.claude/fluent-data/` or the repo is ever written.

| Script              | Question it answers                        | Exit codes                |
| ------------------- | ------------------------------------------ | ------------------------- |
| `fluent_health.py`  | What state is the SR database in?          | always 0 (dashboard)      |
| `gate_report.py`    | How far is each unit from `--advance`?     | 0 ok, 1 import failure    |
| `anki_lint.py`      | Will this `*_anki.txt` import cleanly?     | 0 clean, 1 findings, 2 IO |
| `vocab_coverage.py` | What % of this text does the learner know? | 0 ok, 1 no index/tokens   |

## 1. fluent_health.py — one-shot SR dashboard

```bash
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/fluent_health.py
# optional: --data-dir /path/to/fluent-data (default ~/.claude/fluent-data)
```

Real output (live data, 2026-07-10, abridged):

```text
=== Fluent health — 2026-07-10 ===
[scheduler metadata]
  scheduler: fsrs-6
  algorithm: FSRS-6
  target_retention: 0.9
  weights: None
  last_optimized: None
  -> weights null: FSRS hook uses DEFAULT_W. This is the normal, permanent
     state — the weight optimizer was removed from the plugin [...]

[items] 408 items
[queue buckets]
  today: 335   tomorrow: 12   this_week: 15   later: 46
  recomputed due<=today from items: 347
  !! queue.today (335) != recomputed due (347) — queue is STALE [...]

[prefix census]  (voc = vocabulary, gram = grammar cloze)
  error-pattern/other        39  (39 -)
  link_t12_                 157  (57 gram + 100 voc)
  link_t13_                 139  (40 gram + 99 voc)
  link_t4_                   51  (51 gram)
  vocab_* (legacy)           22  (22 voc)

[mastery histogram]  level 0: 361  1: 19  2: 21  3: 7
[red cards] consecutive_incorrect>=2: 3  -> grammar_bijzin_en_conjunct,
  grammar_possessive_hij_zijn, spelling_long_vowel_open_syllable

[review_history] top-level key: 0 entries (LEGACY, expected empty) |
  per-item sum: 225 (REAL)

[sessions] 21 total
  last: session-021 on 2026-07-09 (1 days ago), accuracy 0.767

[reviews] 225 per-item reviews recorded
```

Between `[queue buckets]` and `[prefix census]` the script prints the session
cap and a burn-down in `/fluent-review` rounds. Fluent 0.6.0 (2026-10-06)
replaced the daily cap with `SESSION_CAP`, which the script reads from the
plugin since 2026-10-08. Live run that day:

```text
[session cap] SESSION_CAP = 10 (fluent 0.7.1) — one /fluent-review round; nothing caps the day
  daily_limits.review_items_per_day = 45 is still in the data, unread since Fluent 0.6.0
[burn-down] 90 due / 10 per round = 9 /fluent-review rounds;
  plus 2 more coming due within 7 days -> ~10 rounds (optimistic: ignores lapses re-entering the queue)
```

### Interpretation

| Signal                         | Green                 | Red / act on it                                                                                                                                                                |
| ------------------------------ | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scheduler`                    | `fsrs-6`              | anything else → scheduler regressed; see `nederlands-failure-archaeology`                                                                                                      |
| `weights`                      | `None`, permanently   | a 21-float list means something revived weight fitting — nothing in the plugin writes this any more (archaeology 12)                                                           |
| queue.today vs recomputed due  | equal                 | mismatch = queue stale. NORMAL: it is rebuilt only by `fluent_import.py` and `update-db.py`, not nightly. Trust the recomputed number; a session or import refreshes the queue |
| burn-down rounds               | ≤ 9                   | ≥ 30 = structural backlog → `fluent-backlog-campaign` (the same backlog sizes as the old ≤ 3 / ≥ 10 days at 30 a day)                                                          |
| top-level review_history       | 0                     | non-zero = something wrote the legacy key; stop and investigate before trusting any review counts                                                                              |
| per-item review_history sum    | growing over sessions | frozen while sessions increase = `update-db.py` payloads lack `review_results` — see `nederlands-debugging-playbook`                                                           |
| red cards                      | 0                     | any → these block `--advance`; drill them first in the next session                                                                                                            |
| `total_items_tracked` vs items | equal                 | mismatch = stale metadata; a re-import rebuilds it                                                                                                                             |
| days since last session        | 0–2                   | ≥ 7 = streak dead, backlog compounding                                                                                                                                         |

**The review_history trap (memorize):** `spaced-repetition.json` has TWO
`review_history` keys. The top-level list is a legacy stub, permanently empty.
Real reviews live per-item in `items[*].review_history`; the optimizer counts
them there (`optimize_weights.py:27`). Any diagnostic that reads the top-level
key reports 0 and is wrong.

## 2. gate_report.py — mastery-gate math for every unit

Imports `check()` from `scripts/fluent_import.py` (verified importable), so its
numbers CANNOT drift from what `--check`/`--advance` enforce: ready = total>0
AND mastered/total ≥ 0.80 (`mastery_level ≥ 3`) AND zero red cards
(`consecutive_incorrect ≥ 2`).

```bash
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/gate_report.py --course link
```

Real output (2026-07-10, zero-card units elided):

```text
=== Mastery-gate report — course 'link' ===
unit       status   cards  m>=3     pct  red  gate
--------------------------------------------------
thema_4    active      51     0   0.0%    0  not ready (need 41 mastered)
thema_12   locked     157     0   0.0%    0  not ready (need 126 mastered)
thema_13   locked     139     0   0.0%    0  not ready (need 112 mastered)
...
61 items outside this course's prefixes (legacy vocab_*, error patterns)
active unit per curriculum.json: ['thema_4'] (exactly one is the invariant)
```

### Interpretation

| Observation                                                 | Meaning / next step                                                                                                                                |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `READY -> --advance`                                        | run `python3 scripts/fluent_import.py --course link --check` to confirm, then `--advance` per `nederlands-run-and-operate`                         |
| `not ready (need N mastered)`                               | N − current is the card gap; at ~5 reviews/card to reach level 3 this is months, not days — the deadlock `fluent-backlog-campaign` exists to break |
| cards>0 on a `locked` unit                                  | a focus import (`--thema N`) ran without moving the pointer — expected for thema 12/13                                                             |
| `active` unit ≠ where the learner really is                 | curriculum pointer drift (as of 2026-07-10: active=thema_4, real study=thema_13). Repointing is a gated decision — `nederlands-change-control`     |
| two units `active` / crash "expected exactly 1 active unit" | curriculum.json corrupted; fix statuses by hand before anything else                                                                               |
| pct > 0 but red > 0                                         | gate blocked by red cards alone; drilling 2–3 items is cheaper than more coverage                                                                  |

## 3. anki_lint.py — validate an \*\_anki.txt before import/commit

```bash
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/anki_lint.py \
  link/thema_13/taak_1/woordenlijst_thema13_taak1_anki.txt
# --strict: heuristic flags also fail the exit code
```

Clean file → `0 errors, 0 warnings, 0 heuristic flags`, exit 0 (verified on the
live thema 13 file and the grammatica drill file). Against a seeded-bad file it
produces:

```text
ERROR  line 6: no literal TAB — row will import as a single field
ERROR  line 7: VOLDEMORT violation ('Rusland') — Rusland/Россия must
       never appear in content
ERROR  line 8: 6 columns, expected 5 (from #columns)
ERROR  [sound:...] present but '#html:true' missing — audio will render
       as literal text (8cd356c)
HEUR   line 9: 'verzekering' looks like a noun (suffix) but has no
       de/het/een article  [heuristic — verify by hand]
4 errors, 0 warnings, 1 heuristic flags   (exit 1)
```

### Interpretation

| Finding                         | Severity | Why / fix                                                                                                                                                                                  |
| ------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| no literal TAB                  | ERROR    | editor/formatter converted tabs to spaces → silent one-field import. Restore tabs; `*_anki.txt` is prettier-ignored for exactly this reason                                                |
| wrong column count              | ERROR    | a stray TAB inside a field or a missing field; Anki shifts every later column                                                                                                              |
| `[sound:]` without `#html:true` | ERROR    | audio renders as literal text (incident 8cd356c)                                                                                                                                           |
| VOLDEMORT violation             | ERROR    | hard content rule (commit 5be6931); never commit, never publish                                                                                                                            |
| flat / unknown-namespace tag    | WARN     | taxonomy is hierarchical (`link::thema13::taak1::A2`); known namespaces: link, sententiae, constructies, de_opmaat. `link::` on link_plus files is legacy-correct — do not "fix"           |
| noun without article            | HEUR     | suffix-based heuristic (…heid, …ing, …atie, …): false negatives are common, occasional false positives (e.g. gerunds). Eyeball each flag; house rule is `de aankoop`, never bare `aankoop` |

Lint every new/edited deck BEFORE `nederlands-change-control`'s commit gate;
pushes to main publish to GitHub Pages within minutes.

## 4. vocab_coverage.py — measured comprehensibility of a text

The primitive behind "content generation constrained to learned vocabulary" (see
`nederlands-research-frontier`). Regenerate the index first if vocab files
changed: `python3 scripts/build_vocab_index.py --course link`.

```bash
python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/vocab_coverage.py \
  daily/verhalen/verhaal_2026-04-14_twee_dagen_van_alexander.md \
  --course link --max-thema 13
```

Real output (2026-07-10):

```text
index: link/woordenlijst_index.txt (themas <= 13, 41 sections,
  988 known tokens)
tokens: 2234 total, 572 unique
covered by index:        899 (40.2%)
function words (extra):  494 (22.1%)
combined 'should read': 1393 (62.4%)
unknown:                 841 (37.6%, 361 unique)
top 20 unknown tokens: goed x22, zeg x18, zegt x16, iliko x14, ...
```

### Interpretation

| Combined coverage | Reading                                                     |
| ----------------- | ----------------------------------------------------------- |
| ≥ 90%             | comfortable independent reading (i+1 territory)             |
| 75–90%            | usable as a lesson text with pre-taught unknowns            |
| < 75%             | too hard as-is; rewrite or pre-teach the top unknown tokens |

The 62.4% above correctly flags that story as hard for a thema-13 Link learner —
but read the unknown list before believing the number:

- **No lemmatization.** `zegt/zeg` count as unknown even if `zeggen`-class words
  are known. Coverage is a LOWER bound; mentally forgive obvious inflections in
  the top-unknown list.
- **Proper names** (iliko, julia, devi) count as unknown — subtract them.
- `--max-thema N` = only vocab up to thema N counts as known; omit it to use the
  whole index. `--course de_opmaat` reads high (its index contains whole example
  sentences).
- **No link_plus support** — `build_vocab_index.py` does not index `link_plus/`;
  its `woordenlijst_index.txt` is a stale pre-rename snapshot. Do not measure
  Yulia's texts against it.

Use it as a generation gate: draft a verhaal → measure → replace/pre-teach top
unknowns → re-measure. Target ≥ 90% combined for independent reading.

## Quick manual probes (no script needed)

```bash
# real review count (per-item, the only correct way)
python3 -c "import json,pathlib;d=json.loads((pathlib.Path.home()/'.claude/fluent-data/spaced-repetition.json').read_text());print(sum(len(i.get('review_history',[])) for i in d['items'].values()))"

# is the mastery gate mathematically movable this week?
python3 scripts/fluent_import.py --course link --check --thema 13

# what would the next session actually serve? prints: cap, served, due
FLUENT_ROOT="$(ls -d ~/.claude/plugins/cache/*/fluent/*/ | sort -V | tail -1)"
python3 "${FLUENT_ROOT}.claude/hooks/read-db.py" --review | python3 -c "import json,sys;d=json.load(sys.stdin);c=d['computed'];print(c['session_cap'],len(d['databases']['spaced_repetition']['review_queue']['today']),c['due_reviews_count'])"
```

Trap inside that `--review` payload (verified 2026-10-08, Fluent 0.7.1): the
round lives in `databases.spaced_repetition.review_queue.today` — 10 ids, cut to
`computed.session_cap` — while `computed.due_reviews_count` stays UNCAPPED (=90)
even in `--review` mode. `computed` has exactly five keys (`today`,
`due_reviews_count`, `next_session_id`, `streak_active`, `session_cap`);
`review_queue_trimmed_to` and `due_review_items` are gone. Top-level output keys
are `databases` and `computed`, and DB names use underscores
(`spaced_repetition`) while filenames use hyphens.

## Provenance and maintenance

Live numbers above are a 2026-07-10 snapshot (408 items, 335/347 due, 225
reviews, 21 sessions, 7 items at mastery≥3, 3 red cards); the cap section and
the `--review` trap are from 2026-10-08 (90 due, round of 10). They age daily —
rerun `fluent_health.py`, never quote this file's numbers.

Re-verify drift-prone claims:

- Gate constants unchanged:
  `grep -n "MASTERY_THRESHOLD\|>= 3\|>= 2" scripts/fluent_import.py`
- `gate_report.py` still imports cleanly (fluent_import API drift):
  `python3 .claude/skills/nederlands-diagnostics-and-tooling/scripts/gate_report.py --course link`
- Two-review_history-keys trap still holds (optimizer counts per-item):
  `git -C ~/Projects/fluent show 09618f3^:.claude/hooks/optimize_weights.py | grep -n "review_history"`
- Queue rebuilt only on import/update (staleness message stays true):
  `grep -n "review_queue" ~/.claude/plugins/cache/aymkin/fluent/0.4.0/.claude/hooks/update-db.py`
- Session cap still 10, `review_items_per_day` still unread (expect
  `SESSION_CAP = 10`, then `0`):
  `H="$(ls -d ~/.claude/plugins/cache/*/fluent/*/ | sort -V | tail -1).claude/hooks"; grep -n "SESSION_CAP =" "$H/session_cap.py"; grep -c review_items_per_day "$H/read-db.py"`
- Plugin cache path version (`0.3.0` hardcoded above) —
  `ls -d ~/.claude/plugins/cache/*/fluent/*/ | sort -V | tail -1`
- Anki header formats still match conventions:
  `head -5 link/thema_13/taak_1/woordenlijst_thema13_taak1_anki.txt`
- Index builder still writes `woordenlijst_index.txt` and still lacks link_plus:
  `python3 scripts/build_vocab_index.py --help; head -3 scripts/build_vocab_index.py`

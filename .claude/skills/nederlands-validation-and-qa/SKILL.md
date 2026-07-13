---
name: nederlands-validation-and-qa
description: >-
  Use when validating work in the nederlands repo or the Fluent fork — running
  or adding tests (test_fluent_import.py, fluent tests/, py-fsrs crosscheck),
  checking acceptance thresholds (mastery gate 80%, optimizer 400/50, 285/285
  alignment), QA-ing Anki TSV cards / verhalen / grammatica content before
  commit, deciding whether a doc claim is trustworthy, or when "pnpm run
  format:check" fails, "N passed" counts disagree with docs, or someone asks "is
  this verified?".
---

# Validation & QA — what counts as evidence here

Runbook for proving that code, content, and claims in
`/Users/Alex.Naymkin/Projects/nederlands` (and the Fluent fork at
`~/Projects/fluent`) are actually correct. Covers the two test suites, the
numeric acceptance thresholds, content QA gates, doc-drift traps, and the golden
(canonical) inventory.

**When NOT to use this skill:** to _measure_ live system state (queue sizes,
review counts, DB probes) use `nederlands-diagnostics-and-tooling`; to _make_ a
change that QA flagged (including fixing stale docs) go through
`nederlands-change-control`; for house style details of documents use
`nederlands-docs-and-writing`; when a test fails and you need root cause, use
`nederlands-debugging-playbook`.

## The evidence standard

A claim is **verified** in this repo only when all three hold:

1. The exact command that produced the evidence is written down.
2. Its output is pasted (not paraphrased, not "it passed").
3. It is date-stamped ("as of 2026-07-09: …") because live state drifts daily.

Anything else is labeled `UNVERIFIED`. Docs here are known to drift (see
"Doc-drift QA" below), so a doc citation alone is never evidence — re-run the
command. Predict the number you expect _before_ running the check; a surprising
match is how stale assumptions get caught.

## Test suite 1 — repo: scripts/test_fluent_import.py

Self-running, **no pytest anywhere** (`python3 -c "import pytest"` →
ModuleNotFoundError; that is by design, don't add it).

```bash
python3 scripts/test_fluent_import.py
# expected (2026-07-10): "25 passed", one "OK  test_name" line per test
```

Note: `scripts/README.md:539` says "21 passed" — STALE (verified 2026-07-10).
Never delete tests to match the doc; fix the doc via change control.

### How it works / how to add a test

The file defines bare `def test_*()` functions using plain `assert`, and a
collector at the bottom:

```python
def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")
```

To add a test:

1. Write `def test_<behavior>():` anywhere above `_run_all()`. Name it for the
   behavior, not the function under test.
2. Use only `assert` (with a message for non-obvious checks) — no unittest, no
   pytest fixtures.
3. Build fixtures with `tempfile.TemporaryDirectory()` and write real files
   (curriculum.json, `woordenlijst_thema{N}_*_anki.txt` with literal tabs) —
   existing tests are the pattern; never point a test at the live
   `~/.claude/fluent-data/`.
4. The module imports `import fluent_import as fi` (same dir — python puts the
   script's dir on sys.path, so it runs from any cwd).
5. Tests run in **alphabetical order** via `sorted(globals())` — each test must
   be independent; no shared state between tests.
6. Re-run; the count must increment (25 → 26). Failure = first failing assert
   raises and the run stops (no partial report).

## Test suite 2 — Fluent fork: ~/Projects/fluent/tests/

**Six** files (verified 2026-07-10 by `ls ~/Projects/fluent/tests/`), all stdlib
`unittest`, each run individually from the fork root:

```bash
cd ~/Projects/fluent
python3 tests/test_fsrs.py            # FSRS-6 stdlib port unit tests → OK
python3 tests/test_read_db.py         # → OK
python3 tests/test_update_db.py       # → OK
python3 tests/test_migrate_to_fsrs.py # → OK
python3 tests/test_optimize_weights.py # → OK (see note)
python3 tests/test_fsrs_crosscheck.py  # → OK (skipped=1) under system python3
```

Notes:

- Tests locate hooks via `Path(__file__).parent.parent/.claude/hooks` — they
  test the **clone**, not the runtime cache. After passing, hook changes still
  need the clone→cache sync (see `nederlands-run-and-operate`).
- `test_optimize_weights.py` prints an
  `[optimize] insufficient data (165/400, +165 new) — no-op` line after `OK` —
  that is fixture output from the test itself, not the live DB. Expected.
- To run under unittest verbosity: append `-v`.

### The py-fsrs numerical crosscheck gate

`tests/test_fsrs_crosscheck.py` is the correctness gate for any change to the
stdlib FSRS port (`.claude/hooks/fsrs.py`). It compares scheduling sequences
numerically against pip-installed **py-fsrs, pinned 6.3.1**, with py-fsrs's
learning/relearning steps emptied and fuzzing disabled (the stdlib port only
models day-granularity long-term scheduling — the docstring explains why).

- Under system python3 (no py-fsrs): `@unittest.skipUnless(HAVE_FSRS, ...)`
  fires → output `OK (skipped=1)`. **A skip is NOT a pass** for FSRS-math
  changes.
- The real gate runs in the fork's dev venv (has fsrs 6.3.1, no pytest):

```bash
cd ~/Projects/fluent
.devvenv/bin/python tests/test_fsrs_crosscheck.py
# expected: "Ran 1 test" ... "OK" (no skip)
```

Rule: any edit to `fsrs.py` ships only with this gate green **in the devvenv**.
The crosscheck loads the hook under a private module name to avoid the `fsrs`
sys.modules collision with the pip package — don't "simplify" that import dance.

## Acceptance thresholds (the numbers that gate decisions)

| Gate                                            | Threshold                                                                                                                 | Where defined                                                                                | Verified   |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------- |
| Curriculum mastery gate (`--check`/`--advance`) | mastery≥3 count / total ≥ **0.80** AND **zero** red cards (`consecutive_incorrect ≥ 2`), total > 0                        | `scripts/fluent_import.py:248` (`MASTERY_THRESHOLD = 0.80`), :258-261                        | 2026-07-10 |
| Item mastery reaching 3                         | `repetitions >= 5` AND `consecutive_correct >= 3`                                                                         | update-db.py ~:411 (runtime cache `~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/`) | 2026-07-10 |
| FSRS optimizer runs at all                      | total reviews ≥ **400** AND ≥ **50** new since last optimize; else `[optimize] insufficient data (N/400, +M new) — no-op` | fork `.claude/hooks/optimize_weights.py:14-15` (`MIN_TOTAL`, `MIN_NEW`)                      | 2026-07-10 |
| Story-reader alignment bar                      | **285/285** sentences aligned (Whisper forced alignment; VTT greedy matching drifted past ~270)                           | commit `e6f41db` body                                                                        | 2026-07-10 |
| Whisper model standard                          | turbo model: **0 overlaps** (base had occasional overlaps)                                                                | commit `1c88339` body                                                                        | 2026-07-10 |
| FSRS port correctness                           | exact numeric parity vs py-fsrs 6.3.1                                                                                     | crosscheck gate above                                                                        | 2026-07-10 |

Live context (volatile, as of a 2026-07-10 probe): 408 SR items, 225 lifetime
per-item reviews, 7 items at mastery≥3 — every gate above is far from firing.
Re-probe, never quote these numbers as current:

```bash
python3 -c "
import json
d=json.load(open('$HOME/.claude/fluent-data/spaced-repetition.json'))
it=d['items']
print(len(it), sum(len(v.get('review_history',[])) for v in it.values()),
      sum(1 for v in it.values() if v.get('mastery_level',0)>=3))"
```

## Content QA gates (run before every content commit)

### Anki TSV checklist

- [ ] **Literal TAB separators** — converting tabs to spaces silently corrupts
      import. Check: `head -5 file | sed -n l` (shows `\t`).
- [ ] Header matches one of the 5 golden formats (table below) exactly.
- [ ] `#html:true` present whenever any field contains `[sound:…]` (incident:
      commit 8cd356c).
- [ ] Tags follow the taxonomy for that format: `link::thema{N}::taak{K}::A2`
      (5-col Word), `sententiae::{theme}::{level}::audio` (4-col), `…::zinnen`
      (3-col), `opmaat::thema{N}::pagina{P}::A2` (de_opmaat 5-col). link_plus
      files keep the legacy `link::` prefix — existing decks depend on it, never
      migrate.
- [ ] Every Dutch noun carries its article (`het stokbrood`, `de buurt`).
- [ ] **Voldemort grep** clean — the words Rusland/Россия must never appear in
      content (rule since commit 5be6931; characters come from
      Polen/Oekraïne/Turkije):

```bash
grep -rniE "rusland|россия" --include="*.md" --include="*.txt" \
  link/ link_plus/ de_opmaat/ other/ daily/
# expected: no output
```

- [ ] **Level calibration per learner**: Alex content at A2→B1; Yulia
      (`link_plus/`) content at **A1+** even though the Link+ book is B1→B2
      (CLAUDE.md "Language Context" — this one is accurate).
- [ ] `*_anki.txt` is in `.prettierignore` — never run Prettier over it.

### Vocab recycling rule

Before generating any cards or texts, build and read the vocab index — new
content must recycle learned vocabulary, and the index is the ground truth of
what is learned:

```bash
python3 scripts/build_vocab_index.py --course link   # or de_opmaat|both
# writes link/woordenlijst_index.txt — read THIS, not 20+ source files
```

No `link_plus` support exists; `link_plus/woordenlijst_index.txt` is a stale
pre-rename snapshot (open weak point). The `/anki-cards` command mandates this
step — don't duplicate its style rules here, invoke it.

### Verhaal (story) QA

- [ ] **All verbs bolded** (every conjugated form — the `/verhaal` command's own
      checklist requires "no missed conjugations").
- [ ] **One sentence per line**, no hard wraps — TTS/reader scripts parse
      line-per-sentence. Protection: `**/verhaal_*.md` is in `.prettierignore`
      and `daily/verhalen/**/*.md` has a `proseWrap:     "never"` override in
      `.prettierrc`. A verhaal saved under any other name/path gets rewrapped by
      Prettier and breaks (incident 51c5ba6).
- [ ] NL/RU/EN extra-words table present.
- [ ] Exception: `other/nieuw_in_rotterdam/` extensions bold **vocabulary**, not
      verbs — two conventions, never mix them.

### Grammar-file ordering trap

Grammar cloze item*ids are **positional** (`link_t12_gram_3.8_10`). QA any
grammatica edit for this: editing/reordering `**bold**` examples \_after* a
Fluent import orphans the imported cards. Edit grammar BEFORE importing; after
import, treat bold examples as frozen.

## Doc-drift QA — known-stale claims (verified 2026-07-10)

Check this list before trusting a doc; fix docs only via
`nederlands-change-control`, never as a drive-by.

| Doc says                                                                                  | Disk reality                                                                                        |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `scripts/README.md` (### Тесты): "21 passed"                                              | 25 passed (run the suite)                                                                           |
| CLAUDE.md: "The active study plan uses the Evgeniy 6-step method" (maart_2026)            | Plan abandoned after 2 of ~25 days; real loop = Link@Danner + Fluent                                |
| CLAUDE.md dir tree: `link/ … thema_N/{N}_{task_name}/`                                    | `link/` uses plain `taak_1..4` dirs; the `{N}_{name}` pattern exists only in `link_plus/thema_1`    |
| CLAUDE.md Anki table: "Vocabulary with audio: Dutch \| Russian \| Notes \| Audio \| Tags" | No de_opmaat file has that header (header census below); de_opmaat vocab uses the 5-col Word format |
| `package.json` name/URLs (`de_opmaat`)                                                    | Repo is `aymkin/nederlands`                                                                         |

Header census command (re-verify the audio-vocab claim):

```bash
for f in $(find de_opmaat -name "*_anki.txt"); do
  head -4 "$f" | tr '\n' '|'; echo "  <= $f"; done | sort | uniq -c
```

## Format checking — scope to tracked files

`pnpm run format:check` runs Prettier over `**/*.md` including **untracked
scratch** (`.superpowers/`, `link/thema_13/les.md` — Alex's raw class notes that
must NEVER be autocorrected). As of 2026-07-10 it exits 1 on 18 such files, so
its exit code says nothing about the commit-worthy tree. Use:

```bash
git ls-files '*.md' -z | xargs -0 pnpm exec prettier --check
# 2026-07-10: "All matched files use Prettier code style!" over 259 files
```

Same trick with `--write` to format only tracked files. Never run
`pnpm run format` blindly while untracked notes exist in content dirs.

## Golden inventory (canonical shapes — deviations are bugs)

| Golden artifact                   | Canonical shape                                                                                                                                                                                                                                                                  | Exemplar                                                                         |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `curriculum.json`                 | keys `course`, `units[]`; unit = `{id, grammar_file, grammar_modules, status}`; status ∈ done/active/locked; **exactly one active** (ValueError otherwise, tested)                                                                                                               | `link/curriculum.json` (17 units)                                                |
| Anki 5-col Word                   | `#separator:tab` / `#html:true` / `#columns:Word	Example	Translation	TranslationExample	Tags` / `#tags column:5`                                                                                                                                                                     | `link/thema_8/taak_1/woordenlijst_thema8_taak1_anki.txt`                         |
| Anki 4-col sententiae             | `#separator:tab` / `#html:true` / `#tags column:4`; `[sound:x.mp3]` in col 3                                                                                                                                                                                                     | `de_opmaat/thema_7/2/sententiae_gezondheid_anki.txt`                             |
| Anki 3-col zinnen/luisteren/lezen | `#separator:tab` / `#html:true` / `#tags column:3`                                                                                                                                                                                                                               | `link_plus/thema_2/taak_1_wie_doet_de_boodschappen/zinnen_thema2_taak1_anki.txt` |
| Anki 2-col legacy                 | `#separator:tab` / `#html:false`, no tags                                                                                                                                                                                                                                        | `de_opmaat/thema_6/woordenlijst_pagina_16_anki.txt`                              |
| Anki grammar drill                | `#separator:tab` / `#html:true` / `#columns:Front	Back	Tags` / `#tags column:3`, inline HTML                                                                                                                                                                                       | `link/thema_12/grammatica_thema12_anki.txt`                                      |
| Grammatica module                 | H1 `# Thema {N}: {Title} — Grammatica`; H2 = the Link book's own module numbers (e.g. `## 2.16`, `## 3.6` — non-sequential, consumed by curriculum.json, never renumber); per module `### Regel` → table → `### Voorbeelden uit oefeningen` (bold = cloze source); body in Dutch | `link/thema_12/grammatica_thema12_op_de_basisschool.md`                          |
| Importer behavior                 | seeds new items only, rebuilds queue, writes ONLY spaced-repetition.json, backs up first, idempotent item_ids                                                                                                                                                                    | locked by the 25-test suite                                                      |

Stub trap: some link woordenlijst files are deliberate single-column stubs
(`#columns:Word` only, e.g. `link/thema_6/taak_1/…_anki.txt` — "woordenlijst
stub … voedt woordenlijst_index.txt"). They feed the vocab index, are not
importable decks, and must not be used as format exemplars.

Typo'd filenames (`opdrach_3.md`, `woordenlijst_page_14_anki.txt`) are
load-bearing — public GitHub Pages links point at them; renaming is a breaking
change.

## Provenance and maintenance

All claims verified 2026-07-09 and re-verified 2026-07-10 against disk/live
state. Re-verify before relying on:

- Test count: `python3 scripts/test_fluent_import.py | tail -1` (25 passed)
- Fork test files: `ls ~/Projects/fluent/tests/` (6 test\_\*.py)
- Crosscheck gate:
  `cd ~/Projects/fluent && .devvenv/bin/python tests/test_fsrs_crosscheck.py`
  (OK, not skipped)
- py-fsrs pin: `~/Projects/fluent/.devvenv/bin/pip show fsrs` (6.3.1)
- Mastery gate: `grep -n MASTERY_THRESHOLD scripts/fluent_import.py` (0.80)
- Optimizer guard:
  `grep -n "MIN_TOTAL\|MIN_NEW" ~/Projects/fluent/.claude/hooks/optimize_weights.py`
  (400 / 50)
- Item mastery rule:
  `grep -n "repetitions.*>= 5" ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/update-db.py`
- 285/285 and 0-overlaps: `git show e6f41db | grep 285`;
  `git show 1c88339 | grep -i overlap`
- Doc staleness: `grep -n "21 passed" scripts/README.md`; header census command
  above
- Tracked-format check still green:
  `git ls-files '*.md' -z | xargs -0 pnpm exec prettier --check`
- Live SR counts: the python probe in "Acceptance thresholds" (volatile daily)

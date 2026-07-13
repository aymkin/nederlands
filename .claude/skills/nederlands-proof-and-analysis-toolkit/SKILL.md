---
name: nederlands-proof-and-analysis-toolkit
description: >-
  Use when a claim needs proof instead of trust: porting or replacing an
  algorithm (FSRS-6 vs py-fsrs parity), deciding whether ~225 reviews can train
  21 FSRS weights, a read-db.py payload or context dump feels bloated, checking
  an importer/script is safe to re-run, validating TTS audio-highlight
  alignment, a plan resting on an untested difficulty estimate, or proving
  fluent-data backups actually restore. Also when docs, test counts, or hook
  copies disagree with each other.
---

# Proof & analysis toolkit — "prove it, don't just install it"

Seven first-principles methods, each with a worked example FROM THIS REPO'S
history. The pattern behind all of them: before relying on a component, design a
cheap experiment whose outcome is a NUMBER you predicted in advance, run it, and
only then build on top.

**When NOT to use this skill:** to run the existing test suites or check
acceptance thresholds, use `nederlands-validation-and-qa`; for the full
hunch-to-accepted-result process and evidence bar, use
`nederlands-research-methodology`; for ready-made measurement probes and their
interpretation, use `nederlands-diagnostics-and-tooling`; for the operational
restore runbook, use `nederlands-run-and-operate`.

Paths used below: nederlands repo = `~/Projects/nederlands`; Fluent fork dev
clone = `~/Projects/fluent`; Fluent runtime cache =
`~/.claude/plugins/cache/m98/fluent/0.3.0/`; live data =
`~/.claude/fluent-data/`.

---

## Recipe 1 — Numerical cross-check against a reference implementation

**When to use:** you port, fork, or reimplement an algorithm (scheduler, scoring
formula, parser) and correctness is not obvious from reading code.

**Steps:**

1. Pin the reference implementation to an exact version. Record the pin in the
   ported file's docstring.
2. Extract magic constants FROM the reference programmatically — never copy them
   from a blog post or by hand.
3. Neutralize deliberate scope differences so you compare like with like
   (disable features you intentionally did not port).
4. Drive both implementations through the same input sequences; assert outputs
   match within an explicit, justified tolerance.
5. Guard against accidental self-comparison (loading your port where the
   reference should be, or vice versa).

**Worked example — the stdlib FSRS-6 port** (fork
`~/Projects/fluent/.claude/hooks/fsrs.py`, gated by
`tests/test_fsrs_crosscheck.py`, commits 4d1d7fc + f5740b3):

- **Pin:** `fsrs==6.3.1` (py-fsrs) installed only in the dev venv
  (`~/Projects/fluent/.devvenv`). Verify:
  `~/Projects/fluent/.devvenv/bin/pip show fsrs`.
- **Constant extraction:** `DEFAULT_W` (21 floats) was printed from the pinned
  package, not typed in — the command lives in fsrs.py's docstring:

  ```bash
  ~/Projects/fluent/.devvenv/bin/python -c \
      "from fsrs import Scheduler; print(list(Scheduler().parameters))"
  ```

  Never hand-edit `DEFAULT_W` (see `nederlands-architecture-contract`).

- **Scope neutralization:** the port models day-granularity long-term reviews
  only. The test therefore builds py-fsrs's `Scheduler` with
  `learning_steps=()`, `relearning_steps=()`, `enable_fuzzing=False` so both
  sides run the same long-term formulas and advance the clock by the same
  integer day count.
- **Tolerance design:** stability must match within
  `max(card.stability * 0.02, 1e-6)` — 2% RELATIVE, because stability grows
  unbounded and an absolute delta would be meaningless at S=200; the 1e-6 floor
  keeps the assertion meaningful near zero. Difficulty is bounded [1, 10], so an
  ABSOLUTE delta of 0.01 works, plus explicit range assertions.
- **Self-comparison guard:** the port is loaded via
  `importlib.util.spec_from_file_location("_fsrs_hook", ...)` under a private
  name because BOTH modules are called `fsrs` — a plain
  `sys.path.insert(); import fsrs` would cache whichever loads first under
  `sys.modules["fsrs"]` and silently compare the reference with itself.
- **Inputs:** four rating sequences including a lapse mid-stream (`[3,1,3]`) and
  a lapse after Easy streak (`[4,4,1,3]`), stepping the clock to each card's own
  due date.

**Run it:**

```bash
~/Projects/fluent/.devvenv/bin/python \
    ~/Projects/fluent/tests/test_fsrs_crosscheck.py
```

**What convinces:** every step of every sequence matches the pinned reference
within the pre-declared tolerance, and the test SKIPS (does not falsely pass)
when py-fsrs is absent (`skipUnless(HAVE_FSRS, ...)`). "I read both
implementations and they look the same" convinces nobody — the
fsrs_difficulty/CEFR collision (fork 44fb945) and the unclamped-D0
mean-reversion subtlety (fsrs.py `_next_difficulty` comment) were exactly the
kind of details reading misses.

---

## Recipe 2 — Guard-before-train: statistical power reasoning

**When to use:** anything that fits parameters to data (weight optimizer,
threshold tuning, "personalization"). Ask FIRST: is there enough data for the
number of free parameters?

**The heuristic:** count free parameters P and independent observations N. A
common regression rule of thumb wants N/P ≥ 10–20. Below that, the fit memorizes
noise (overfitting) and the "personalized" model is worse than the population
default.

**Worked example — the FSRS weight optimizer** (fork
`.claude/hooks/optimize_weights.py`, commit 5ba0487):

- FSRS-6 has **21 free weights**. As of 2026-07-10 the live DB holds **225
  reviews** (sum of per-item `review_history`; the top-level `review_history`
  key is an empty legacy list — count per-item):

  ```bash
  python3 -c "
  import json,os
  sr=json.load(open(os.path.expanduser(
      '~/.claude/fluent-data/spaced-repetition.json')))
  print(sum(len(v.get('review_history',[])) for v in sr['items'].values()))"
  ```

  225 / 21 ≈ 10.7 observations per parameter — bottom of the acceptable band,
  and reviews of the same card are not independent. Training now would overfit.

- **The encoded guard:** `MIN_TOTAL = 400` (≈19 reviews/parameter) and
  `MIN_NEW = 50` since the last optimize (optimize_weights.py lines 14–15).
  Below either, the weekly run is a deliberate no-op. Its only run so far
  logged: `[optimize] insufficient data (185/400, +185 new) — no-op`
  (`~/.claude/logs/fluent-fsrs-optimize.log`).
- **The MIN_NEW increment** prevents weekly retraining on 98%-identical data:
  weights would jitter from optimizer randomness, not new evidence.
- **Belt-and-braces around the fit:** training failure keeps current weights
  (exit 1, scheduling untouched); a result with `len(weights) != 21`
  (`EXPECTED_WEIGHTS`) aborts; all 6 DBs are snapshotted to
  `.backups/pre-optimize-<date>/` before the write.
- **Data hygiene:** rating is derived from each entry's `quality` (0–5), NEVER
  from `score` — historical `score` is unreliably 0 (optimize_weights.py
  `_rating`, line 20 comment).

**What convinces:** the guard is code, not discipline — you can point at
`should_optimize()` and at the no-op log line. When you add any new fitted
component, write down N, P, and N/P in the commit message before writing the
training code.

---

## Recipe 3 — Measure payload before optimizing

**When to use:** something "feels" slow, bloated, or context-hungry. Measure
bytes first, find what dominates, cut the dominant term, measure again. Never
optimize on vibes.

**Worked example — read-db.py `--review` payload** (fork commits 281c2a4,
13fd374, 18d55c0; CHANGELOG: "Payload for a 369-item queue capped at 30: 444KB →
43KB (-90.3%)"):

| Step     | Change                                                                                | Measured effect                                  |
| -------- | ------------------------------------------------------------------------------------- | ------------------------------------------------ |
| baseline | full 6-DB dump, `indent=2`                                                            | ~444 KB into model context to use 30 records     |
| 281c2a4  | compact JSON separators                                                               | −35% on every /fluent-\* call, content-identical |
| 281c2a4  | `--review`: sort by priority, cap at `review_items_per_day`, trim items to capped set | −81.5% vs baseline                               |
| 13fd374  | empty mastery_db/progress_db/session_log; narrow mistakes_db to referenced patterns   | 82,393 → 43,000 B (−47.8% more; −90.3% total)    |
| 18d55c0  | drop `due_review_items`, trim learner_profile + per-item review_history               | 35.0 KB → 22.9 KB                                |

Each commit message states the byte counts BEFORE and AFTER — that is the house
style for perf work. The safety argument for dropping data was also explicit:
step 7 of /fluent-review persists via update-db.py, which rereads all 6 files
fresh from disk, so nothing needs to round-trip through the payload.

**Measure it yourself (read-only):**

```bash
C=~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/read-db.py
python3 $C | wc -c            # full dump
python3 $C --review | wc -c   # review payload
```

Live measurement 2026-07-10: full = 298,697 B; `--review` = 35,282 B. Note the
35 KB (not 22.9 KB): the runtime CACHE did not yet contain 18d55c0 — the
measurement itself exposed a fork→cache sync gap (cache behind dev clone HEAD
`4205bf1`). That `read-db.py` gap was closed on 2026-07-11 by syncing fork→cache
(`--review` payload then dropped to 27,581 B); the marketplace, which trailed on
upstream `86fb80f` that day, was repointed to the fork on 2026-07-11 (see
`nederlands-architecture-contract` §3). That is the point of measuring: it
catches drift no doc mentions.

**What convinces:** a before/after byte count on the same dataset, plus a stated
reason why the dropped data is safe to drop. "-90%" without the absolute
numbers, or absolute numbers without the safety argument, is half a proof.

---

## Recipe 4 — Idempotency proof pattern

**When to use:** any script that writes to a shared store and might be run twice
(imports, migrations, seeders). "Should be fine to re-run" must be a test, not a
hope.

**Worked example — `scripts/fluent_import.py`** (nederlands repo, tested by
`scripts/test_fluent_import.py`; run `python3 scripts/test_fluent_import.py` →
`25 passed` as of 2026-07-10; `scripts/README.md` says "21 passed" — stale, do
not "fix" tests to match):

- **Design that makes idempotency possible:** the item*id is a pure function of
  stable content, not of run state. Vocab:
  `{course}\_t{N}\_voc_taak{K}*{slug(word)}`→`link_t8_voc_taak1_de-buurt`(fluent_import.py line ~100). The same word always maps to the same id, so`add_items`
  can skip ids already in the store (line ~211) and re-running adds 0.
- **The proof, as tests:**
  - `test_add_items_idempotent`: same items added twice → first call returns 1,
    second returns 0, existing item state untouched.
  - `test_do_import_end_to_end_and_idempotent`: full import against a fixture
    repo, then a second full import → `s2["added"] == 0`.
- **The counterexample inside the same script:** grammar ids are
  `{prefix}gram_{module}_{idx}` where `idx` is POSITIONAL within the module's
  `Voorbeelden uit oefeningen` bullets (line ~157). Re-running unchanged is
  idempotent — but inserting/reordering a bold example in the grammar file after
  import shifts every later idx: old cards orphan (keep their review history
  under ids nothing regenerates) and the shifted examples import as "new".
  Idempotency is only as strong as the id's stability under the edits people
  actually make. Rule: edit grammar files BEFORE importing (see
  `nederlands-change-control`).

**What convinces:** a test that runs the writer twice against the same store and
asserts the second run is a no-op (`added == 0`, byte-identical store, or both)
— plus an honest note on which input mutations break the id scheme.

---

## Recipe 5 — Forced-alignment validation: count, don't eyeball

**When to use:** validating audio/text synchronization (story readers, Anki
audio splits) or any output where "looks right" hides tail failures.

**Worked example — story_reader audio/highlight drift** (nederlands commits
e6f41db, 1c88339):

- **Symptom:** edge-tts VTT cues split on `!`/`?`/`:` are not 1:1 with markdown
  sentences; the greedy matcher exhausted cues early and pinned the highlight at
  audio-end. Eyeballing the first minutes showed nothing — drift appeared "past
  ~270" of 285 sentences.
- **The fix carried its own metric:** Whisper word-level timestamps + fuzzy
  sentence matching, and the script PRINTS the coverage —
  `Aligned {matched} / {len(sentences)} sentences` (story_reader.py line ~277).
  The fix commit's acceptance evidence: **285/285 sentences aligned** (was
  drifting past ~270).
- **Second measured comparison (1c88339):** Whisper `turbo` model vs `base` → 0
  timing overlaps vs base's occasional overlap, on a 124-sentence story. Note:
  the shipped default model is still `base`, hardcoded in `audio_to_anki.py`
  `transcribe_with_whisper` (~line 51, shared by story_reader) — the turbo
  result was an experiment, not the default. Switching means editing that line.

**Generalize:** define the total (sentences), define the success predicate
(matched above the fuzzy threshold, no overlapping intervals), make the tool
print `matched/total`, and require total/total — or an explained gap — before
shipping. `--no-align` (VTT greedy) remains as the known-buggy fallback; never
use it for acceptance.

**What convinces:** `285/285` printed by the tool on the real artifact. Not "I
listened to it and it seemed synced".

---

## Recipe 6 — Day-1 reality check / calibration experiment

**When to use:** before building anything on an ASSUMED quantity (a learner's
level, a comprehension rate, a throughput estimate). Spend one day measuring the
assumption; re-plan from the measurement.

**Worked example — the March study plan** (nederlands commit 4774cb5,
2026-02-25):

- The plan assumed news-for-kids listening material (NOS Jeugdjournaal,
  NPOkennis, Het Klokhuis) was the right difficulty. Day 1 measured actual
  comprehension: **NPOkennis <10%, Peppa Pig 90%+**. The estimate was off by an
  entire CEFR band for natural speech.
- Instead of pushing through, the plan was re-cut around the measurement: a
  Comfort → Challenge → Stretch difficulty ladder, comfort-tier resources in the
  early weeks, 7 daily files + roadmap updated — one day in, before sunk cost
  accumulated.
- Postscript honesty: the plan itself later died (2 of ~25 days executed — see
  `nederlands-failure-archaeology`), which is a second lesson: calibrate the
  ASSUMPTION on day 1, and also treat process adherence itself as an assumption
  to check within days (owner rule: no heavyweight templated study-plan
  systems).

**Generalize:** (1) write down the assumption as a number BEFORE testing
("comprehension ≈ 60%"); (2) run the cheapest test that yields the real number;
(3) if off by more than ~2x, re-plan, don't patch; (4) commit the measurement in
the message so the next person inherits the calibration, not the folklore.

**What convinces:** a predicted number, a measured number, and a visible plan
change traceable to the delta — all in one commit.

---

## Recipe 7 — Backup-restore drill: prove recoverability

**When to use:** before trusting any backup scheme — i.e., before the first
risky mutation of `~/.claude/fluent-data/`. A backup nobody has restored is a
hypothesis.

**Ground truth (verified 2026-07-10):** `~/.claude/fluent-data/.backups/` holds
71 snapshot dirs: `YYYYMMDD/` (39), `pre-update-session-NNN/` (21),
`pre-import-<ts>/` (8), `pre-migrate-fsrs-<ts>/` (2), `precompact*` (1). Each is
a FLAT copy of all 6 JSONs (learner-profile, progress-db, mistakes-db,
mastery-db, session-log, spaced-repetition). Restore = plain copy back;
all-or-nothing per snapshot.

**The drill — runs entirely on a SCRATCH COPY; NEVER mutate the live dir. An
actual live restore is owner-gated and belongs to
`nederlands-run-and-operate`:**

```bash
# 1. Snapshot the live dir to scratch (read-only on live)
S=$(mktemp -d); cp -R ~/.claude/fluent-data "$S/fd"

# 2. Pick a backup snapshot inside the scratch copy
ls "$S/fd/.backups/" | tail -5           # choose one, e.g. a pre-update
B="$S/fd/.backups/<chosen-snapshot>"

# 3. Simulate the failure you are insuring against — corrupt the copy
python3 - "$S" <<'EOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]) / "fd" / "spaced-repetition.json"
p.write_text(p.read_text()[:100])        # truncated = unparseable
EOF

# 4. Restore: copy the whole snapshot back (all-or-nothing)
cp "$B"/*.json "$S/fd/"

# 5. Prove it: every file parses, contents match the snapshot exactly
for f in "$S"/fd/*.json; do python3 -c "import json;json.load(open('$f'))" \
  && echo "OK  $(basename $f)"; done
diff -r --exclude='.backups' <(cd "$B" && ls) <(cd "$S/fd" && ls *.json | cat)
python3 -c "
import json,sys,glob,os
b,d = sys.argv[1], sys.argv[2]
for f in glob.glob(b+'/*.json'):
    assert json.load(open(f)) == json.load(open(d+'/'+os.path.basename(f))), f
print('restore byte-equivalent: all 6 DBs')" "$B" "$S/fd"

# 6. Clean up scratch
rm -rf "$S"
```

**What convinces:** step 5's output — all 6 files parse AND equal the snapshot
content after a real (simulated) corruption. Also record what the drill does NOT
cover: cross-file consistency between a restored snapshot and reviews done AFTER
it was taken (restoring an old snapshot silently discards later sessions — that
is the all-or-nothing trade-off, and why the LIVE restore decision is the
owner's).

---

## Provenance and maintenance

All facts verified 2026-07-10 against the repo, the fork, and live data.
Volatile numbers (review counts, payload bytes, backup dir census, HEADs) WILL
drift — re-verify before quoting:

| Claim                                    | Re-verify with                                                                                                                                                                                            |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| crosscheck test shape, tolerances        | `cat ~/Projects/fluent/tests/test_fsrs_crosscheck.py`                                                                                                                                                     |
| py-fsrs pin 6.3.1 in dev venv            | `~/Projects/fluent/.devvenv/bin/pip show fsrs`                                                                                                                                                            |
| DEFAULT_W = 21 floats, extraction cmd    | head of `~/Projects/fluent/.claude/hooks/fsrs.py`                                                                                                                                                         |
| optimizer guards 400 / 50 / 21           | `grep -n "MIN_TOTAL\|MIN_NEW\|EXPECTED" ~/Projects/fluent/.claude/hooks/optimize_weights.py`                                                                                                              |
| live per-item review count (225)         | python snippet in Recipe 2                                                                                                                                                                                |
| optimizer no-op log line                 | `tail ~/.claude/logs/fluent-fsrs-optimize.log`                                                                                                                                                            |
| payload commits + byte counts            | `git -C ~/Projects/fluent show 281c2a4 13fd374 18d55c0 --stat`                                                                                                                                            |
| live payload bytes (298,697 / 35,282)    | `wc -c` commands in Recipe 3                                                                                                                                                                              |
| clone vs marketplace vs cache drift      | `git -C ~/Projects/fluent log -1; git -C ~/.claude/plugins/marketplaces/m98 log -1; diff -q ~/Projects/fluent/.claude/hooks/read-db.py ~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/read-db.py` |
| importer tests pass (25)                 | `python3 ~/Projects/nederlands/scripts/test_fluent_import.py`                                                                                                                                             |
| item_id construction lines               | `grep -n "item_id" ~/Projects/nederlands/scripts/fluent_import.py`                                                                                                                                        |
| 285/285 alignment + drift story          | `git -C ~/Projects/nederlands show e6f41db --stat`                                                                                                                                                        |
| turbo 0-overlaps, 124 sentences          | `git -C ~/Projects/nederlands log -1 1c88339`                                                                                                                                                             |
| whisper model `base` hardcoded           | `grep -n '"base"' ~/Projects/nederlands/scripts/audio_to_anki.py`                                                                                                                                         |
| day-1 tiers (NPOkennis <10%, Peppa 90%+) | `git -C ~/Projects/nederlands log -1 4774cb5`                                                                                                                                                             |
| backup census (71 dirs; 6 JSONs each)    | `ls ~/.claude/fluent-data/.backups/ \| wc -l; ls ~/.claude/fluent-data/.backups/ \| sed 's/[0-9].*//' \| sort \| uniq -c`                                                                                 |

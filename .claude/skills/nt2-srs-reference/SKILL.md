---
name: nt2-srs-reference
description:
  Use when a task assumes domain knowledge this repo takes for granted - NT2,
  inburgering, CEFR levels, Link vs Link+ vs De Opmaat tracks, learner levels,
  Dutch grammar terms (voltooid deelwoord, lidwoord, inversie, tangconstructie),
  FSRS-6 math (stability, fsrs_difficulty, retrievability, DEFAULT_W,
  target_retention), SM-2 legacy (easiness_factor), quality/score/rating
  mappings, mastery_level thresholds, the 80% --advance gate, or the 400-review
  optimizer guard.
---

# nt2-srs-reference — the domain pack

Theory as it applies HERE, not a textbook. Three parts: (A) NT2/CEFR and this
repo's courses and learners, (B) spaced repetition as actually implemented (SM-2
legacy → FSRS-6 live), (C) the learning-method consensus the content conventions
encode.

**When NOT to use this skill:** for how to RUN the importer/sessions/scripts use
`nederlands-run-and-operate`; for config values and where they live use
`nederlands-config-and-flags`; for symptom→fix triage use
`nederlands-debugging-playbook`; for why a design decision exists use
`nederlands-architecture-contract`; to actually drain the review backlog use
`fluent-backlog-campaign`.

---

## Part A — NT2, CEFR, courses, learners

### Terms

| Term        | Meaning                                                                                                                                                                                                             |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NT2         | Nederlands als Tweede Taal — Dutch as a second language, the field this whole repo serves                                                                                                                           |
| inburgering | The Dutch civic-integration obligation for many migrants; passing NT2 exams at a set level is its core. Alex (RTB / temporary-protection status) is potentially inburgeringsplichtig; his employer pays for courses |
| CEFR        | Common European Framework: A1 (beginner) → A2 (elementary) → B1 (independent) → B2 (upper-intermediate). NT2 Staatsexamen I = B1, II = B2                                                                           |

### The three courses in this repo

| Dir          | Course                                                           | Level          | Learner                         |
| ------------ | ---------------------------------------------------------------- | -------------- | ------------------------------- |
| `de_opmaat/` | De Opmaat (Boom textbook), thema_1–9                             | 0→A2           | Alex                            |
| `link/`      | Link, _praktisch geschoolden_ track (nt2.nl), thema_4–20 on disk | to A2/B1       | Alex, live at the Danner school |
| `link_plus/` | Link+, _theoretisch geschoolden_ track (nt2.nl)                  | B1→B2 textbook | Yulia                           |

"Praktisch/theoretisch geschoolden" = the two nt2.nl audience tracks
(practically vs academically educated); Link+ moves faster and targets B2.
Verified 2026-07-09: `ls link/` shows thema_4..20; `ls de_opmaat/` shows
thema_1..9.

### The two learners — REAL levels vs textbook levels

| Learner | Textbook            | Real level                  | Rule for content                                             |
| ------- | ------------------- | --------------------------- | ------------------------------------------------------------ |
| Alex    | De Opmaat A2 + Link | A2, approaching B1          | Write at A2→B1                                               |
| Yulia   | Link+ (B1→B2)       | **A1+** (between A1 and A2) | Write verhalen/exercises at A1+, NOT at the textbook's level |

The Yulia gap is deliberate and documented in CLAUDE.md's Language Context;
never scale her content up to match Link+.

Related content rule (the "Voldemort rule", commit 5be6931): the words
Rusland/Россия must never appear in generated content; story characters come
from Polen/Oekraïne/Turkije. Base explanation language is Russian.

### Dutch grammar terminology (house convention)

The repo convention is to name grammar concepts with the DUTCH terms (with a
short Russian gloss on first use), not Russian/English terms. One-line glosses:

| Dutch term            | Gloss (RU / EN)                                                                    |
| --------------------- | ---------------------------------------------------------------------------------- |
| voltooid deelwoord    | причастие прош. времени / past participle (gemaakt, gegaan)                        |
| lidwoord              | артикль / article (de, het, een)                                                   |
| woordvolgorde         | порядок слов / word order                                                          |
| inversie              | инверсия / verb-subject swap after a fronted element                               |
| tangconstructie       | рамочная конструкция / "clamp": finite verb at position 2, verb rest at clause end |
| de-woord / het-woord  | существительное de-/het-рода / common- vs neuter-gender noun                       |
| onderwerp / werkwoord | подлежащее / глагол — subject / verb                                               |

Live examples: `link/thema_13/grammatica_thema13_gas_water_elektriciteit.md`
uses voltooid deelwoord (line ~7) and "inversie bij bijwoordelijke bepaling"
(§3.8); `link/thema_12/...` uses de-woord/het-woord tables.

### House grammar-table patterns

Two canonical table shapes recur; reuse them, don't invent new ones.

**1. Conjunction word-order table** (CLAUDE.md "Grammar Reference"):

| Conjunction | Word Order         | Example                            |
| ----------- | ------------------ | ---------------------------------- |
| **want**    | normal (S + V)     | Ik blijf thuis, want ik ben ziek.  |
| **omdat**   | verb to end        | Ik blijf thuis, omdat ik ziek ben. |
| **als**     | verb to end        | Als het regent, blijf ik thuis.    |
| (inversie)  | V + S after adverb | Morgen ga ik naar Amsterdam.       |

**2. Positie 1-2-3 table** (verbatim shape from `link/thema_13/grammatica_...md`
§3.8):

| Positie 1    | Positie 2 | Positie 3 | Rest   |
| ------------ | --------- | --------- | ------ |
| Ik           | blijf     | vanavond  | thuis. |
| **Vanavond** | **blijf** | **ik**    | thuis. |

Rule it encodes: the finite verb (persoonsvorm) is ALWAYS at position 2 in a
main clause; fronting a time/place expression forces inversie.

In `link/` grammatica files the H2 numbers (2.17, 3.8, …) are the Link book's
OWN module numbers — non-sequential on purpose, consumed by
`link/curriculum.json`, and the grammar-card item_ids are POSITIONAL. Never
renumber; edit grammar files BEFORE importing (see `nederlands-change-control`).

### Why nouns must carry articles

Dutch has two lexical genders — de-woorden (common) and het-woorden (neuter) —
and the assignment is largely unpredictable, so it must be memorized WITH the
noun. Gender drives adjective inflection (een mooi**e** tuin but een mooi meisje
— the het-woord + een case drops -e; see the thema_12 table), pronoun choice,
and relative pronouns. Hence the hard repo rule (CLAUDE.md): every Dutch noun in
vocab lists and Anki cards includes its lidwoord — `het stokbrood`,
`de stroopwafel`.

---

## Part B — spaced repetition as implemented here

### SM-2 in one paragraph (what Fluent used before 2026-07-04)

SM-2 (SuperMemo-2, 1987): each card carries `easiness_factor` (EF, start 2.5,
floor 1.3), `interval_days`, `repetitions`. Quality ≥3 = success: interval goes
1 → 6 → ceil(interval × EF); quality <3 resets repetitions and interval to 1. EF
updates by `EF + (0.1 − (5−q)(0.08 + (5−q)·0.02))`. This exact code survives as
`calculate_sm2()` in update-db.py (defined ~line 149) — retained as a rollback
path but **never called** as of 2026-07-09 (verify:
`grep -n calculate_sm2 <cache>/.claude/hooks/*.py` shows only the definition).
The plugin skill `fluent-sm2-calculator` still describes SM-2 — treat it as
stale for scheduling math (its quality scale, below, is still right).

### FSRS-6: the S/D/R model

FSRS models each card with three quantities:

- **S — stability**: days for recall probability to fall to 90%. Grows on
  success, collapses on lapse.
- **D — difficulty** (1..10): how hard the card is; damps stability growth.
  Stored here as `fsrs_difficulty` (see collision below).
- **R — retrievability**: predicted recall probability, a function of elapsed
  time t and S.

Implementation: `<cache>/.claude/hooks/fsrs.py` (169 lines, stdlib-only), ported
from py-fsrs pinned at 6.3.1. `DEFAULT_W` = 21 floats `w[0..20]` (w[0..3] =
0.212, 1.2931, 2.3065, 8.2956 are the initial stabilities per first rating;
w[20] = 0.1542 sets the forgetting-curve decay). NEVER hand-edit DEFAULT_W — it
was extracted programmatically from the pinned package.

Formula shapes (all verified against fsrs.py 2026-07-09):

```
decay   = -w[20]
factor  = 0.9^(1/decay) - 1
R(t, S) = (1 + factor * t / S) ^ decay          # retrievability
interval(S) = (S / factor) * (0.9^(1/decay) - 1)   # days to R = 0.9
```

`target_retention` is 0.9 (module constant TARGET_RETENTION and live metadata).
Algebraic consequence worth knowing: at target 0.9 the two factors cancel, so
**interval(S) = S** — the next interval is just stability rounded to whole days,
min 1.

New card (S or D is None): first rating g initializes `S0 = max(w[g-1], 0.001)`
and `D0 = clamp(w[4] − e^(w[5](g−1)) + 1, 1, 10)`.

On review of a known card with elapsed days t: compute r = R(t, S), then

- **Difficulty**: Δ = −w[6](g−3); damped = d + Δ(10−d)/9; mean-revert toward
  unclamped D0(Easy) with weight w[7]; clamp [1,10].
- **Success (g ≥ 2)**: S grows by factor
  `1 + e^w8 · (11−d) · S^−w9 · (e^((1−r)·w10) − 1) · hard · easy` where hard =
  w[15] if g=2, easy = w[16] if g=4.
- **Lapse (g = 1)**: S becomes
  `min(w11·d^−w12·((S+1)^w13 − 1)·e^((1−r)·w14),  S / e^(w17·w18))` — the second
  term caps how much stability survives a lapse. Interval then re-derives from
  the new S; a lapse typically collapses to ~1 day (fsrs.py self-check asserts
  exactly 1 for its example).

### Rating scale and THIS repo's mappings

FSRS rating is 1..4: **1 Again, 2 Hard, 3 Good, 4 Easy**. But session payloads
carry `quality` (0-5, SM-2-era scale; semantics per the fluent-sm2-calculator
skill: `quality = floor(score/2)`, score 0-10). Two independent mappings exist —
they agree, but live in different files:

| Place                  | Mapping (verified 2026-07-09)                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| update-db.py ~386      | `score = review.get("score", quality*2)`; rating = 1 if score≤4, 2 if ≤6, 3 if ≤8, else 4                   |
| optimize_weights.py:19 | rating from `quality` ONLY: q<3→1, q=3→2, q=4→3, else 4. Ignores `score` — historical score is unreliably 0 |

In quality terms (default score path): q≤2 → Again, 3 → Hard, 4 → Good, 5 →
Easy.

FSRS state per item: reads `stability`, `fsrs_difficulty`, `last_reviewed`;
writes back `stability`, `fsrs_difficulty`, `interval_days`, `due_date`,
`last_rating`. Live metadata (probed 2026-07-09): `scheduler: "fsrs-6"`,
`target_retention: 0.9`, `weights: null` → hooks fall back to DEFAULT_W. An
`algorithm` key also exists (read "FSRS-6" on 2026-07-09; earlier observed as
stale "SM-2") — **no code reads either key** for branching; update-db.py calls
`fsrs.schedule()` unconditionally.

### Why the short-term path is unused

py-fsrs has a same-day/"short-term" scheduling path (w[17..19], sub-day learning
steps). This port deliberately omits it: items store `last_reviewed` as a DATE,
not a timestamp, so there is no sub-day state — one review per card per day, day
granularity throughout (fsrs.py module docstring). The cross-check against
py-fsrs runs with empty learning/relearning steps for the same reason.

### Migration seeding (2026-07-04, migrate_to_fsrs.py)

SM-2 fields were converted once, for previously-reviewed cards only
(`repetitions > 0`; never-reviewed cards stay `stability: null` so the first
FSRS review initializes them):

```
stability       = max(interval_days, 0.5)
fsrs_difficulty = clamp(10 − (EF − 1.3) / 1.4 * 9, 1, 10)
```

So EF 2.5 (default) → difficulty ≈ 2.29; EF 1.3 (floor) → 10 (max).

### CRITICAL field collision: `difficulty` vs `fsrs_difficulty`

On SR items, the key `difficulty` holds the **CEFR level STRING** ("A2"). FSRS
numeric difficulty lives in `fsrs_difficulty`. Overwriting `difficulty` with the
float was a real bug caught in review (nederlands 350de1a, fork 44fb945). Any
code touching FSRS difficulty must use `fsrs_difficulty`.

### mastery_level 0-5 state machine (update-db.py ~399-421)

Runs on every `review_results[]` entry, after FSRS scheduling. Counters:

| Counter                 | Update rule                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| `repetitions`           | +1 if quality ≥ 3, else RESET to 0 (SM-2-era counter, still drives mastery) |
| `consecutive_correct`   | +1 if quality ≥ 3, else 0                                                   |
| `consecutive_incorrect` | +1 if quality < 3, else 0                                                   |

Mastery transitions (checked in this order; mastery NEVER decreases):

1. If `repetitions ≥ 5` AND `consecutive_correct ≥ 3` →
   `mastery_level = min(5, max(current, 3))` (the jump-to-3 branch).
2. Elif `repetitions ≥ 2` AND `consecutive_correct ≥ 1` AND `quality ≥ 4` →
   `mastery_level = min(5, current + 1)` (increment branch — 4 consecutive
   quality-≥4 reviews reach level 3 this way).

Priority heuristic: `consecutive_incorrect ≥ 2` → "high" (a **red card**);
`mastery_level ≥ 3` → "low"; else keep (default "medium").

### How mastery feeds the 80% --advance gate

`scripts/fluent_import.py --check` (MASTERY_THRESHOLD = 0.80, ~line 248): a unit
is ready iff

```
total > 0  AND  (count of mastery_level ≥ 3) / total ≥ 0.80
           AND  zero red cards (consecutive_incorrect ≥ 2)
```

Arithmetic reality check (as of 2026-07-09): 408 items, 225 lifetime reviews,
only 7 items at mastery ≥ 3, review queue today = 335 with a live daily cap of
30 (`daily_limits.review_items_per_day`; code default is 20). Each card needs
≥4-5 successful reviews to reach level 3, so at current cadence the gate is
months away — that deadlock is exactly what `fluent-backlog-campaign` addresses.
Re-probe, don't trust these numbers:

```
python3 -c "
import json, os
sr=json.load(open(os.path.expanduser(
    '~/.claude/fluent-data/spaced-repetition.json')))
it=sr['items']; print(len(it),
 sum(len(i.get('review_history',[])) for i in it.values()),
 sum(1 for i in it.values() if i.get('mastery_level',0)>=3),
 {k:len(v) for k,v in sr['review_queue'].items()}, sr['daily_limits'])"
```

(Per-item `review_history` is the real review log; the TOP-LEVEL
`review_history` list in the same file is an empty legacy artifact — always
count per-item.)

### Why the optimizer waits for 400 reviews

`optimize_weights.py` (weekly LaunchAgent, Sun 09:05) fits all 21 FSRS weights
to the personal review log via fsrs-optimizer 6.5.0. Guards (lines 14-15,
32-33): no-op unless total reviews ≥ `MIN_TOTAL = 400` AND ≥ `MIN_NEW = 50`
since the last optimize. Rationale: 21 free parameters against ~225 review
events (2026-07-09) is a textbook overfitting setup — personalized weights
fitted on that little data would be worse than the population DEFAULT_W. It has
run once ever, logging
`[optimize] insufficient data (185/400, +185 new) — no-op`. Until it fires,
`metadata.weights` stays `null` and DEFAULT_W applies.

---

## Part C — the learning-method consensus

`other/language_learning_methods/` analyzes several method authors (Alisher
immersion, MaksimEng active output, Evgeniy 6-step, Denis Borisov, neuroscience
notes). Where they AGREE is what this repo's conventions encode:

| Principle                       | Encoded where                                                      | Evidence in repo                                                                                                                          |
| ------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| SRS is mandatory                | Everything flows into Anki + Fluent SR                             | `methods_comparison_and_strategy.md` §"Anki как основа": both methods call spaced repetition the key tool                                 |
| Phrases > isolated words        | 5-col Anki format requires an Example sentence; card-quality rules | same file: "Словосочетания > отдельные слова"                                                                                             |
| Audio is mandatory              | TTS scripts, `[sound:]` in cards, `#html:true` rule                | `evgeniy_6step_method_analysis.md`: "Всё взаимодействие с языком первые 6 месяцев — через звук"; Anki cards must carry audio              |
| Regularity > intensity          | Daily small sessions, streak tracking in Fluent                    | `evgeniy_...md` ~601 "регулярность > интенсивность"; `neuroscience_of_language_learning.md` ~295: 20 min Anki daily beats 2 h on weekends |
| Input phase before output phase | Content tiers, listening resources                                 | `methods_comparison...md`: accumulation (0-300 h, input) → activation (output)                                                            |

### Comprehension tiers (Comfort / Challenge / Stretch)

Defined in `daily/roadmap_maart_2026.md` (~lines 135-137), born from a real
incident (commit 4774cb5): the day-1 listening-level estimate was wrong
(NPOkennis <10% understood, Peppa Pig 90%), so resources were re-tiered by
MEASURED comprehension:

| Tier      | Comprehension | Example resources                                 |
| --------- | ------------- | ------------------------------------------------- |
| Comfort   | 80-95%        | Peppa Pig, Heb je zin?, De Opmaat audio           |
| Challenge | 60-80%        | Easy Dutch Super Easy                             |
| Stretch   | 30-60%        | NOS Jeugdjournaal, Net in Nederland, Het Klokhuis |

Use the tiers when picking or generating listening/reading material: mostly
Comfort/Challenge; Stretch in small doses. NOTE: the maart_2026 plan that hosts
this table is itself abandoned (2 of ~25 days executed) and CLAUDE.md calling it
"active" is stale — the TIERS survive as the useful concept, the plan does not.
Owner rule: never build heavyweight templated study-plan systems again; new
processes must be light and course-anchored (see `nederlands-change-control`).

---

## Provenance and maintenance

All facts re-verified 2026-07-09 against disk. Cache path below means the Fluent
runtime: `~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/` (a version
bump changes it — re-resolve with
`ls -d ~/.claude/plugins/cache/m98/fluent/*/ | sort -V | tail -1`).

| Claim                                           | Re-verify with                                                                                                                                 |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| FSRS formulas, DEFAULT_W, TARGET_RETENTION 0.9  | `sed -n '24,75p' <cache>/fsrs.py`                                                                                                              |
| score→rating thresholds in update-db            | `grep -n 'rating = 1 if' <cache>/update-db.py`                                                                                                 |
| mastery thresholds (5/3 jump, 2/1/q4 increment) | `sed -n '399,421p' <cache>/update-db.py`                                                                                                       |
| seeding formulas (max(interval,0.5), EF map)    | `sed -n '25,37p' <cache>/migrate_to_fsrs.py`                                                                                                   |
| optimizer guards 400/50 + quality-only rating   | `sed -n '14,33p' <cache>/optimize_weights.py`                                                                                                  |
| gate 0.80 + red-card rule                       | `grep -n 'MASTERY_THRESHOLD\|red' scripts/fluent_import.py`                                                                                    |
| live SR counts / queue / limits / metadata      | python probe in Part B above                                                                                                                   |
| calculate_sm2 still dead code                   | `grep -rn calculate_sm2 <cache>/*.py` (definition only = dead)                                                                                 |
| link/ thema range, curriculum active unit       | `ls link/`; `python3 -c "import json;c=json.load(open('link/curriculum.json'));print([u['id'] for u in c['units'] if u['status']=='active'])"` |
| Positie table / inversie wording                | `sed -n '111,126p' link/thema_13/grammatica_thema13_gas_water_elektriciteit.md`                                                                |
| tier percentages                                | `sed -n '130,140p' daily/roadmap_maart_2026.md`                                                                                                |
| method-consensus quotes                         | `grep -rn 'регулярность > интенсивность\|Словосочетания' other/language_learning_methods/`                                                     |

Volatile items (WILL drift): item/review/mastery counts, queue sizes,
`weights: null`, the `algorithm` metadata string, curriculum active unit
(repoint to thema_13 approved in principle 2026-07-09 — check before asserting),
cache version path.

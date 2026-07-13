---
name: nederlands-failure-archaeology
description: >-
  Use when tempted to re-investigate a past problem in the nederlands repo or
  Fluent fork: audio/highlight drift in story_reader, VTT cue mismatch, Whisper
  alignment, Prettier breaking sentence parsing, link/ vs link_plus/ history
  confusion, Rusland/Voldemort scrub, fluent_import backup collision, gramatica/
  missing, fsrs_difficulty vs difficulty collision, Parkiet TTS, dead study
  plans (maart_2026, Mikel), fsrs-optimizer API break, renovate branch, SM-2 to
  FSRS-6 migration. Check before reopening.
---

# Failure archaeology — every settled battle in this repo

This is the incident chronicle for the `nederlands` repo and its Fluent fork:
every major investigation, dead end, rejected fix, pause, and stall, recorded as
symptom → root cause → evidence → status. Read the relevant entry BEFORE
re-investigating a familiar symptom or "improving" something that looks odd —
most odd-looking things here are scar tissue from a real incident.

All commit hashes below were re-verified with `git show` on 2026-07-09. Hashes
prefixed `fork:` live in the Fluent fork working clone
(`git -C ~/Projects/fluent show <hash>`); bare hashes live in this repo.

**Status legend:** `fixed` (done, verified) · `enforced-ongoing` (rule that must
be actively upheld in new work) · `paused` (deliberately stopped, artifacts
remain) · `stale-doc` (docs contradict reality) · `open` (unresolved, labeled as
such).

## Settled battles — do not reopen

| Battle                                           | Verdict                                      | Entry |
| ------------------------------------------------ | -------------------------------------------- | ----- |
| VTT greedy matching for sentence highlighting    | Rejected; Whisper forced alignment won       | 1     |
| Pause-based audio splitting in audio_to_anki     | Rejected; forced alignment won               | 1     |
| Whisper `base` model for reader alignment        | Rejected; `turbo` gives 0 overlaps           | 1     |
| Letting Prettier wrap verhaal/story markdown     | Rejected; breaks TTS alignment               | 1     |
| Storing FSRS difficulty in item key `difficulty` | Rejected; collides with CEFR string          | 6     |
| Date-only backup dir names in fluent_import      | Rejected; same-day collision                 | 4     |
| Central `link/gramatica/` dir                    | Deleted; thema-folder-first is canon         | 5     |
| Heavyweight templated study-plan systems         | Two died in ≤2 days; owner rule: never again | 8     |
| Multi-voice TTS via Parkiet                      | Paused, NOT chosen for research frontier     | 7     |
| Reading pre-2026-04-17 `link/` history as Alex's | Wrong; it was Yulia's                        | 2     |
| Mentioning Rusland/Россия in any content         | Forbidden (Voldemort rule)                   | 3     |

## 1. The Whisper/VTT alignment saga (Feb–Apr 2026) — fixed

Three rounds of the same underlying lesson: naive segmentation loses sync with
real audio; forced alignment against a known transcript wins.

**Round 1 — pause-based splitting (2026-02-24).** Symptom: audio_to_anki.py
split dialogues on silence, producing 71 ragged segments for Thema 7/2 where the
transcript had 30 sentences. Root cause: pause detection has no knowledge of
sentence boundaries. Fix: `3ef3232` added a forced-alignment mode (Whisper
transcription + `SequenceMatcher` fuzzy match against `--transcript`); `8ec4dbe`
re-cut Thema 7/2 with it: 30 precise segments instead of 71 pause splits.

**Round 2 — VTT cue mismatch in story_reader (2026-04-15).** Symptom: sentence
highlight drifted, then pinned at the LAST sentence while audio kept playing
(drift started ~sentence 270 of 285). Root cause: edge-tts emits VTT cues split
on `!` / `?` / `:` punctuation — not 1:1 with markdown sentences. When cues
outnumbered sentences, `match_timings()` exhausted `cue_idx` early and assigned
`cues[-1].end` to every remaining sentence. Fix: `e6f41db` switched story_reader
to word-level Whisper timestamps + fuzzy sentence matching (reusing
`transcribe_with_whisper`, `find_best_match`, `normalize_text` from
audio_to_anki.py). Result: 285/285 sentences aligned. VTT greedy matching
survives only as the known-buggy `--no-align` fallback — do not "promote" it
back.

**Round 3 — Prettier broke sentence parsing (2026-04-16).** Symptom:
story*reader mis-parsed sentences after `pnpm run format` rewrapped a story file
(one-sentence-per-line is load-bearing for TTS alignment). Fix: `51c5ba6` —
`parse_sentences()` now merges continuation lines into paragraphs before
splitting on sentence boundaries, AND `.prettierignore` gained
`\*\*/verhaal*_.md`+`_\_reader.html`. Both halves matter: removing the ignore
entries reintroduces silent corruption of alignment inputs.

**Round 3b — model choice.** `1c88339` (2026-04-16): regenerating with Whisper
`turbo` gave 0 timestamp overlaps vs occasional overlaps with `base`; 124
sentences aligned, voice switched to nl-NL-FennaNeural. Note: audio_to_anki.py
still hardcodes model `base` (~line 51) — that is a different tool with
different needs, not an oversight to sync.

## 2. link/ → link_plus/ rename (2026-04-17) — enforced-ongoing

Symptom (for history readers): `git log -- link/` before 2026-04-17 shows
Yulia's Link+ B1→B2 materials, which contradicts today's layout where `link/` is
Alex's Link praktisch course. Root cause: `78f07e9` renamed Yulia's `link/` to
`link_plus/` (the underscore avoids URL-encoding on GitHub Pages and ambiguity
with Anki `::` tag syntax). Alex's `link/` dir came LATER, reusing the old name.
Rule when reading history: any path `link/...` in commits before `78f07e9` means
Yulia/Link+; after it, Alex/Link praktisch. Side effect that must never be
"fixed": `link_plus/` Anki files still carry the `link::` tag prefix — existing
decks depend on it (pre-rename legacy). Status: enforced-ongoing (a semantics
rule, not a bug).

## 3. Voldemort scrub (2026-04-21) — enforced-ongoing

Symptom: content mentioned characters' country of origin as Rusland. Decision:
the words Rusland/Россия must NEVER appear in any content, in any language.
Characters come from Polen / Oekraïne / Turkije. Evidence: `5be6931` rewrote 8
files across de_opmaat and link_plus (Alexander now "komt uit Polen"; Yulia's
vocab example uses Oekraïne; the Marleen-parallel speaking exercise in
de_opmaat/thema_8 rewritten around Polen). No TTS regeneration was needed at the
time. Status: enforced-ongoing — grep before every commit:
`grep -rn 'Rusland\|Росси' --include='*.md' --include='*.txt' .` (exclude
`.git`). Every push publishes to public GitHub Pages, so a slip is immediately
public.

## 4. fluent_import backup hardening (2026-06-26) — fixed

Symptom: two importer runs on the same day could silently overwrite each other's
pre-write backup; a predictable temp filename risked clobbering. Root cause:
backup dir was named by date only; tmp file name was not unique per process.
Fix: `a88b1ff` — timestamped backup dirs
(`.backups/pre-import-<YYYY-MM-DD-HHMMSS>/`), pid-unique `.{pid}.tmp` + atomic
replace, plus bucket-boundary and first-write tests in
`scripts/test_fluent_import.py`. Status: fixed. Do not simplify the backup
naming back to date-only.

## 5. Grammar resolution + gramatica/ deletion (2026-06-26/27) — fixed

Symptom: fluent_import.py looked for grammar files only in a central
`link/gramatica/` dir; grammar actually lives in per-thema folders. Fix in two
steps: `43ee589` made the importer resolve `grammar_file` thema-folder-first
with `gramatica/` as fallback (+32 test lines); the next day `1ee376d` moved the
grammar files into per-thema folders (14 renames) and removed `link/gramatica/`
entirely, adding thema 13–20 grammars. Today: `link/gramatica/` does not exist
on disk; the fallback at `scripts/fluent_import.py:174` is dead-path
compatibility only. Do not recreate the directory, and do not delete the
fallback "because the dir is gone" — it is cheap and documented. Related trap
(unchanged since import design): grammar item_ids like `link_t12_gram_3.8_10`
embed a POSITIONAL example index — editing bold examples in a grammar file after
import orphans already-scheduled cards. Edit grammar BEFORE importing a thema.

## 6. fsrs_difficulty field collision (2026-07-04) — fixed pre-ship

Symptom class: FSRS-6 needs a numeric per-item difficulty; SR items already had
a key `difficulty` holding the CEFR level STRING ("A2"). Root cause: the first
FSRS implementation wrote numeric difficulty into `difficulty`, silently
destroying the CEFR label. Caught: in code review BEFORE the migration shipped —
never hit production data. Fix: fork commit `fork:44fb945` renamed the FSRS
field to `fsrs_difficulty` (per-item FSRS state = `stability`,
`fsrs_difficulty`, `last_reviewed`); `350de1a` updated this repo's spec/plan
docs to match. Status: fixed + enforced-ongoing rule: `difficulty` = CEFR
string, always; FSRS numeric difficulty = `fsrs_difficulty`, always. Any new
code touching SR items must preserve this split.

## 7. Parkiet multi-voice TTS (2026-04-17) — paused

What: experiment testing the Parkiet TTS model's multi-voice `[S1]`–`[S4]`
speaker tags on 10 sentences from verhaal_galopperen_door_nederland, three
rendering modes (normal / ellipsis-paced / slowed), single- vs multi-voice.
Evidence: `1a6d78a` — `scripts/parkiet_test.py` (170 lines) committed as a
checkpoint, explicitly "Experiment is paused". Artifacts still live (verified
2026-07-09): 52 MP3s tracked under `parkiet_test_audio/` (commit message says 50
— the tracked count is 52) plus `parkiet_test_output.mp3` at repo root — all
published to GitHub Pages on every deploy. `scripts/.venv` (torch 2.11.0,
transformers 5.5.4) exists ONLY for this script. Status: paused. The owner
explicitly did NOT choose multi-voice TTS as a research-frontier direction
(decision 2026-07-09). Do not resume without an owner decision; do not delete
the artifacts without change control (deletion breaks published URLs — see
nederlands-change-control).

## 8. Study-plan abandonments — the survivorship lesson

Two heavyweight templated study-plan systems died within days each. The owner
distilled this into a binding rule (2026-07-09): **never create heavyweight
templated study-plan systems** — new processes must be light and
course-anchored.

**maart_2026 6-step plan.** Created `ae3d4df` 2026-02-25: 23 pre-filled daily
`les.md` files across 5 week folders, weekly resource rotation, progressive
6-step protocol. Same day, `4774cb5` — the day-1 reality check: Alex's estimated
listening level was wrong (NPOkennis <10% comprehension, Peppa Pig 90%+), so
W0–W2 resources were swapped and a Comfort → Challenge → Stretch difficulty
ladder introduced. Execution evidence: lesson-processing commits exist only for
25–26 Feb (`76e41eb`, `6ef999b`, `1f5a22c`) — **2 of ~25 days** — then nothing
but a formatting commit (`04f6ca4`, 2026-04-10). Zero of the 23 les.md files
contain a ticked checkbox. CLAUDE.md still describes this plan as "the active
study plan" — stale-doc; disk and history reality is: abandoned after 2 days
(verified 2026-07-09).

**April Mikel / Language Islands experiment.** Created `e379c80` 2026-04-14
(`daily/april_2026/`). Daily entries exist for exactly 2026-04-13 and 2026-04-14
— **2 days** — last touch `823fb1a` 2026-04-15 (formatting). Abandoned.

**What survived instead:** light, course-anchored loops — the Link course at
Danner + Fluent review sessions. The 4774cb5 tier idea (calibrate against
measured comprehension, not estimated level) remains a good technique even
though its host plan died. Status: enforced-ongoing (the rule) + stale-doc
(CLAUDE.md's "active" claim).

## 9. fsrs-optimizer 6.5.0 API break (2026-07-06) — fixed, expect recurrence

Symptom: the weekly weight-optimizer wrapper broke against the installed
`fsrs-optimizer` 6.5.0 package (its `train()` API had changed; it also reads
`./revlog.csv` from the current working directory). Fix: `fork:133308c` adapted
`optimize_weights.py` to the 6.5.0 API (train() is run with cwd chdir'd to a
tempdir holding revlog.csv). Status: fixed for 6.5.0, but this dependency has
broken its API once already — treat any pip upgrade of `fsrs-optimizer` in
`~/.claude/fluent-data/.venv-optimizer/` as a breaking change until the wrapper
is re-tested. The optimizer has run exactly once as of 2026-07-09: log line
`[optimize] insufficient data (185/400, +185 new) — no-op` in
`~/.claude/logs/fluent-fsrs-optimize.log`.

## 10. Renovate onboarding stalled (since 2026-03-01) — open

`origin/renovate/configure` (tip `b2999ef`, "Add renovate.json", 2026-03-01) has
never been merged; `renovate.json` does not exist on main (verified 2026-07-09).
Dependency-update automation is therefore half onboarded: the branch exists,
nothing enforces it. Either merge it or delete the branch — a 4-month-stale bot
branch is noise. Status: open.

## 11. SM-2 → FSRS-6 migration (2026-07-04) — fixed/done

Not an incident, but the settled outcome several entries orbit.

- FSRS-6 went live 2026-07-04 (backup
  `~/.claude/fluent-data/.backups/pre-migrate-fsrs-2026-07-04T013401/`). The
  migration was made idempotent (`fork:4fd622a`) and re-ran harmlessly on
  2026-07-09 (second `pre-migrate-fsrs-2026-07-09T221056/` backup).
- What "seeded" means: `migrate_to_fsrs.py` derives `stability` from the
  existing SM-2 interval (`max(interval, 0.5)`) for cards that HAVE review
  history; never-reviewed cards get `stability: null` until first review. As of
  2026-07-09: **95 of 408 items seeded** — exactly the 95 items with non-empty
  per-item `review_history` (225 reviews total). The importer also stamps
  `stability`/`fsrs_difficulty` as `null` on newly imported items (`7494138`).
- `metadata.scheduler: "fsrs-6"` is authoritative. The legacy
  `metadata.algorithm` key used to lag at "SM-2"; `fork:4205bf1` (2026-07-09)
  now stamps it to "FSRS-6" too — as of 2026-07-09 both agree.
- `calculate_sm2` is retained in update-db.py as a deliberate rollback path —
  dead code by design, do not prune.
- Known stale-doc: the Fluent plugin's own `fluent-sm2-calculator` skill still
  describes SM-2 while the runtime is FSRS-6.

For FSRS-6 math and the mastery state machine, see nt2-srs-reference. For the
live backlog/mastery-gate deadlock this migration exposed (335 due cards,
mastery≥3 count = 0), see fluent-backlog-campaign — that is an active campaign,
not archaeology.

## When NOT to use this skill

For a LIVE symptom you have not yet diagnosed, use nederlands-debugging-playbook
(symptom → triage); this skill is for checking whether a battle was already
fought and how it ended. For the rules these incidents produced (as gates on new
changes), use nederlands-change-control.

## Provenance and maintenance

All claims verified 2026-07-09 against this repo, the fork clone, and
`~/.claude/fluent-data/` (read-only). Re-verify drift-prone claims:

| Claim                                       | Command                                                                                                                                                                                                                                                              |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Incident commits exist/say what's claimed   | `git show --stat <hash>` for 3ef3232 8ec4dbe e6f41db 51c5ba6 1c88339 78f07e9 5be6931 a88b1ff 43ee589 1ee376d 350de1a 4774cb5 1a6d78a 7494138                                                                                                                         |
| Fork commits                                | `git -C ~/Projects/fluent show --no-patch 44fb945 133308c 4fd622a 4205bf1`                                                                                                                                                                                           |
| gramatica/ still absent; fallback line      | `ls link/gramatica; grep -n gramatica scripts/fluent_import.py`                                                                                                                                                                                                      |
| Parkiet MP3s still tracked                  | `git ls-files 'parkiet_test_audio/*.mp3' \| wc -l` (52)                                                                                                                                                                                                              |
| Renovate branch still unmerged              | `git fetch && git branch -r \| grep renovate; ls renovate.json`                                                                                                                                                                                                      |
| Seeded/reviewed counts (95/408, 225)        | `python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.claude/fluent-data/spaced-repetition.json')));i=d['items'];print(len(i),sum(1 for v in i.values() if v.get('stability') is not None),sum(len(v.get('review_history',[])) for v in i.values()))"` |
| scheduler/algorithm metadata agree          | same file: `metadata.scheduler`, `metadata.algorithm`                                                                                                                                                                                                                |
| Optimizer still no-op                       | `tail -3 ~/.claude/logs/fluent-fsrs-optimize.log`                                                                                                                                                                                                                    |
| maart_2026 still abandoned (no new commits) | `git log --oneline -3 -- daily/maart_2026`                                                                                                                                                                                                                           |
| Prettier ignore entries still present       | `grep -n 'verhaal_\|reader' .prettierignore`                                                                                                                                                                                                                         |
| Voldemort compliance                        | `grep -rn 'Rusland\|Росси' --include='*.md' --include='*.txt' de_opmaat link link_plus other daily`                                                                                                                                                                  |

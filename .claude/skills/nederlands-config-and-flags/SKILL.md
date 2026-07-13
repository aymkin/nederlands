---
name: nederlands-config-and-flags
description:
  Use when you need to know any configuration value, CLI flag, default, guard,
  or live setting in this repo — curriculum.json fields, fluent_import.py flags,
  MASTERY_THRESHOLD, spaced-repetition.json metadata, review_items_per_day,
  optimizer guards (400/50), DEFAULT_W, script flags (audio_to_anki,
  text_to_speech, story_reader, build_vocab_index), prettier config, pages.yml
  exclusions, LaunchAgent schedules, or Anki profile selection — or when adding
  a new config axis.
---

# nederlands-config-and-flags

Catalog of every configuration axis in the nederlands repo and its Fluent
spaced-repetition ecosystem: options, defaults, live values where they differ,
and the guards that protect them. Every table row carries a one-line re-verify
command — flags drift, so run it before trusting a value.

All commands assume cwd `/Users/Alex.Naymkin/Projects/nederlands` unless the
path is absolute. `<CACHE>` below means the Fluent plugin runtime dir; resolve
it first (the version segment changes on plugin bumps):

```bash
CACHE=$(ls -d ~/.claude/plugins/cache/m98/fluent/*/ | sort -V | tail -1)
```

**When NOT to use this skill:** for _running_ the tools (importer modes, session
flow, restore) use `nederlands-run-and-operate`; for _changing_ any guarded
value first read `nederlands-change-control`; for the _meaning_ of FSRS fields
and mastery math see `nt2-srs-reference`.

## 1. link/curriculum.json (course sequence manifest)

Location: `link/curriculum.json`. Only `link/` has one — `de_opmaat/` and
`link_plus/` have no manifest, so `--course link` is the only working value
today despite CLAUDE.md implying otherwise (verified 2026-07-09).

| Field                     | Options                                                     | Default                                       | Live (2026-07-09)                      | Guard                        |
| ------------------------- | ----------------------------------------------------------- | --------------------------------------------- | -------------------------------------- | ---------------------------- |
| `course`                  | course dir name                                             | —                                             | `"link"`                               | none                         |
| `units[].id`              | `thema_N`                                                   | —                                             | thema_4..thema_20                      | `--advance` walks list order |
| `units[].grammar_file`    | filename in thema dir                                       | —                                             | `grammatica_thema{NN}_{slug}.md`       | resolved thema-folder-first  |
| `units[].grammar_modules` | `"all"` or list of module-number strings (`["2.17","3.7"]`) | `"all"` (code fallback, fluent_import.py:176) | all `"all"`                            | non-listed modules skipped   |
| `units[].status`          | `active` / `locked` / `done`                                | —                                             | thema_4 active, 5–20 locked, none done | **exactly one `active`**     |

- **One-active invariant:** `active_unit()` (fluent_import.py:44-46) raises
  `ValueError: expected exactly 1 active unit, got N` if 0 or 2+. `--advance` is
  the only code path that writes `done` (line 296) and moves `active`.
- Live pointer (thema_4) lags real study (thema 13 at the Danner course).
  Repointing is approved in principle but decision-gated — see
  `fluent-backlog-campaign`; do not repoint ad hoc.

Re-verify:

```bash
python3 -c "import json;u=json.load(open('link/curriculum.json'))['units'];\
print('active:',[x['id'] for x in u if x['status']=='active'])"
```

## 2. fluent_import.py CLI + constants

`scripts/fluent_import.py` — stdlib-only bridge repo → Fluent SR DB.

| Flag        | Type          | Default     | Effect                                    | Guard                                                   |
| ----------- | ------------- | ----------- | ----------------------------------------- | ------------------------------------------------------- |
| `--course`  | str, required | —           | course dir containing curriculum.json     | dir must have manifest                                  |
| `--check`   | bool          | off         | mastery-gate report, read-only            | never writes                                            |
| `--advance` | bool          | off         | mark active done, activate next, import   | gate is advisory only — `--advance` does NOT enforce it |
| `--thema N` | int           | active unit | focus import/check WITHOUT moving pointer | pointer untouched                                       |
| `--taak K`  | int           | all taken   | restrict vocab import to one taak         | combine with `--thema`                                  |

| Constant            | Value  | Where                | Meaning                                                                                 |
| ------------------- | ------ | -------------------- | --------------------------------------------------------------------------------------- |
| `MASTERY_THRESHOLD` | `0.80` | fluent_import.py:248 | gate: total>0 AND mastery≥3 share ≥ 0.80 AND zero red cards (consecutive_incorrect ≥ 2) |

- Writes ONLY `~/.claude/fluent-data/spaced-repetition.json`; backup to
  `.backups/pre-import-<YYYY-MM-DD-HHMMSS>/` before every write
  (fluent_import.py:240), atomic tmp+replace.
- Tests: `python3 scripts/test_fluent_import.py` — 25 passed as of 2026-07-09
  (scripts/README.md's "21 passed" is stale).

Re-verify: `python3 scripts/fluent_import.py --help` and
`grep -n MASTERY_THRESHOLD scripts/fluent_import.py`

## 3. spaced-repetition.json metadata + daily limit

File: `~/.claude/fluent-data/spaced-repetition.json`. Live values below verified
2026-07-09; this is the most volatile axis in the repo.

| Key                                 | Default (code)                 | Live (2026-07-09)           | Guard / note                                                                                                                                                                     |
| ----------------------------------- | ------------------------------ | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `metadata.scheduler`                | —                              | `"fsrs-6"`                  | **authoritative** scheduler switch                                                                                                                                               |
| `metadata.algorithm`                | —                              | `"FSRS-6"`                  | informational only; was stale `"SM-2"` earlier — trust `scheduler`                                                                                                               |
| `metadata.target_retention`         | 0.9                            | `0.9`                       | consumed by fsrs.py interval calc                                                                                                                                                |
| `metadata.weights`                  | `null` → DEFAULT_W             | `null`                      | optimizer writes this when it fires                                                                                                                                              |
| `metadata.last_optimized`           | `null`                         | `null`                      | optimizer has never fired                                                                                                                                                        |
| `metadata.reviews_at_last_optimize` | 0                              | `0`                         | baseline for the +50 guard                                                                                                                                                       |
| `metadata.total_items_tracked`      | —                              | `408`                       | volatile                                                                                                                                                                         |
| `algorithm_notes` block             | —                              | SM-2 prose/formula          | **stale legacy text — ignore**                                                                                                                                                   |
| `daily_limits.review_items_per_day` | `20` (read-db.py:105 fallback) | `30`                        | **prompt-enforced only** — the cap is applied by read-db.py `--review` slicing + plugin SKILL.md prompts, no python hard stop; bypassing the fluent-review flow bypasses the cap |
| top-level `review_history`          | `[]`                           | `[]` (legacy, always empty) | real reviews live per-item in `items[*].review_history`                                                                                                                          |

Re-verify:

```bash
python3 -c "import json;d=json.load(open('$HOME/.claude/fluent-data/spaced-repetition.json'));\
print(d['metadata'],d['daily_limits'])"
```

Code default: `grep -n review_items_per_day "$CACHE/.claude/hooks/read-db.py"`

## 4. Optimizer guards + fsrs.py constants

Hooks live in `<CACHE>/.claude/hooks/` (runtime copies — the clone at
`~/Projects/fluent` may drift; sync state before editing anything there).

| Constant    | Value     | Where                  | Meaning                                                                                                                                      |
| ----------- | --------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `MIN_TOTAL` | `400`     | optimize_weights.py:14 | no-op unless ≥400 lifetime per-item reviews                                                                                                  |
| `MIN_NEW`   | `50`      | optimize_weights.py:15 | AND ≥50 new since `reviews_at_last_optimize`                                                                                                 |
| `DEFAULT_W` | 21 floats | fsrs.py:24             | FSRS-6 weight vector, pinned against py-fsrs 6.3.1 — **never hand-edit**; regenerate programmatically from the pinned package if ever needed |

- Guard check is optimize_weights.py:33; the only run ever logged
  `[optimize] insufficient data (185/400, +185 new) — no-op`.
- Optimizer trains from per-item `review_history` deriving rating from `quality`
  (0-5 → 1-4), never from `score`.

Re-verify:

```bash
grep -n "MIN_TOTAL\|MIN_NEW" "$CACHE/.claude/hooks/optimize_weights.py"
python3 -c "import ast,re;s=open('$CACHE/.claude/hooks/fsrs.py').read();\
print(len(ast.literal_eval(re.search(r'DEFAULT_W\s*=\s*(\[.*?\])',s,re.S).group(1))))"
```

Expect 21. A naive comma-split reports 22 (trailing comma) — use the ast probe
above.

## 5. Content-script flags

All four print Russian help text; `--help` is safe (no side effects). Re-verify
any row: `python3 scripts/<script>.py --help`.

### audio_to_anki.py

| Flag                 | Default                                                 | Note                                                       |
| -------------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| `audio` (positional) | required                                                | MP3 path; outputs land NEXT TO input → published via Pages |
| `--transcript`       | none                                                    | MD `Speaker: text`; enables forced alignment (recommended) |
| `--theme`            | `general`                                               | Anki tag theme                                             |
| `--level`            | `A2`                                                    | CEFR tag                                                   |
| `--copy-to-anki`     | off                                                     | copy audio to Anki media                                   |
| Whisper model        | `base` **hardcoded** (line 51, inside the CLI cmd list) | no flag to change; README line pointers are stale          |

### text_to_speech.py

| Flag                  | Default          | Note                                                                        |
| --------------------- | ---------------- | --------------------------------------------------------------------------- |
| `input` (positional)  | required         | auto-detects anki TSV / transcript / plain md                               |
| `--voice`             | `colette`        | choices `colette`/`fenna`/`maarten` → `nl-NL-{Colette,Fenna,Maarten}Neural` |
| `--theme` / `--level` | `general` / `A2` | tags                                                                        |
| `--copy-to-anki`      | off              | copy MP3s to Anki media                                                     |
| `--update-anki`       | off              | **rewrites the input file IN PLACE, no backup**                             |
| `--whole`             | off              | one MP3 for the whole story instead of per sentence                         |

### story_reader.py

| Flag                 | Default                                  | Note                                                                 |
| -------------------- | ---------------------------------------- | -------------------------------------------------------------------- |
| `input` (positional) | required                                 | MD, one sentence per line                                            |
| `--voice`            | `maarten`                                | note: differs from text_to_speech's colette                          |
| `--output`           | `<input_stem>_reader.html` next to input |                                                                      |
| `--no-align`         | off                                      | skips Whisper; falls back to known-buggy VTT greedy matching — avoid |

### build_vocab_index.py

| Flag       | Default | Note                                                                                                                               |
| ---------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `--course` | `both`  | choices `link`/`de_opmaat`/`both` — **NO link_plus** (open gap); `link_plus/woordenlijst_index.txt` is a stale pre-rename snapshot |

## 6. Formatting, deploy, gitignore

| Axis                          | Live value (2026-07-09)                                                                                         | Protects                                                                                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.prettierrc`                 | proseWrap `always`, printWidth 80, tabWidth 2, useTabs false                                                    | house prose style                                                                                                                                                 |
| `.prettierrc` override        | `daily/verhalen/**/*.md` → proseWrap `never`                                                                    | one-sentence-per-line verhaal format (TTS/alignment compat)                                                                                                       |
| `.prettierignore`             | `node_modules/`, `*.pdf`, `*.mp3`, `*.docx`, `*_anki.txt`, `**/verhaal_*.md`, `*_reader.html`                   | anki files: literal TABs (prettier would corrupt them silently); verhaal files: line breaks; reader HTML: giant base64 blobs                                      |
| package.json scripts          | `format` = `prettier --write "**/*.md"`, `format:check` = `--check`                                             | UNVERIFIED live exit: `format:check` was failing on untracked scratch files as of 2026-07-09 — verify with `pnpm run format:check`; don't trust exit code blindly |
| `.gitignore`                  | `.DS_Store`, `node_modules`, `__pycache__`, `.pnp.cjs`, `.yarn/`, `music/`                                      | note: NO ignore for generated `_reader.html` or output MP3s — they get tracked and published                                                                      |
| `.github/workflows/pages.yml` | push to `main` → deploy ENTIRE repo (`path: .`); sole exclusion `rm -f "other/nieuw_in_rotterdam"/*.epub *.pdf` | copyrighted book binaries only — everything else (PDFs, MP3s, notes) publishes publicly within minutes; see `nederlands-external-positioning`                     |

Re-verify: `cat .prettierrc .prettierignore .gitignore` and
`grep -n "rm -f\|path:" .github/workflows/pages.yml`

## 7. LaunchAgents (macOS scheduled jobs)

All in `~/Library/LaunchAgents/`, verified 2026-07-09 via PlistBuddy.

| Label                             | Schedule                 | Runs                                                                                                                        | Logs                                                                              |
| --------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `com.aymkin.claude-plugin-update` | daily 09:03              | `git pull` every repo under `~/.claude/plugins/marketplaces/*/` + `~/.claude/skills/*/`, rewrites skills.lock               | `/tmp/claude-plugin-update.log` (stdout+stderr)                                   |
| `com.aymkin.claude-dotfiles-sync` | daily 09:04              | dotfiles `sync.sh`, auto-commit + push                                                                                      | `~/.claude/logs/sync.log`, `sync-error.log`                                       |
| `com.aymkin.fluent-fsrs-optimize` | Sunday 09:05 (Weekday=0) | `.venv-optimizer/bin/python` against `optimize_weights.py` at the **hardcoded** cache path `.../cache/m98/fluent/0.3.0/...` | `~/.claude/logs/fluent-fsrs-optimize.log` (inline `>>` redirect), RunAtLoad false |

**Guard/trap:** a Fluent plugin version bump 0.3.0→x changes the cache path and
silently breaks the optimizer plist. After any bump, check the plist path
against `ls -d ~/.claude/plugins/cache/m98/fluent/*/`.

Re-verify:

```bash
for p in claude-plugin-update claude-dotfiles-sync fluent-fsrs-optimize; do
  /usr/libexec/PlistBuddy -c Print ~/Library/LaunchAgents/com.aymkin.$p.plist
done
```

## 8. Anki profile selection

| Axis             | Behavior                                                                                                                               | Guard                                                                            |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Profiles on disk | TWO: `alex` and `iuliia` under `~/Library/Application Support/Anki2/`                                                                  | none                                                                             |
| Selection        | `anki_utils.find_anki_media_folder()` returns `profiles[0]` from **unsorted** `iterdir()` with a printed warning (anki_utils.py:54-57) | currently lands on `alex` by luck; **no `--profile` override exists** (open gap) |

If a script copies media, read its output for the
`⚠️ Найдено N профилей, использую: <name>` line and confirm it picked the
intended profile.

Re-verify: `ls ~/Library/Application\ Support/Anki2/` and
`grep -n "profiles\[0\]" scripts/anki_utils.py`

## How to add a new config axis (checklist)

1. Classify the change with `nederlands-change-control` first — most axes above
   are guarded because a past incident made them so.
2. Prefer an existing home: manifest field → `link/curriculum.json`; scheduler
   behavior → `spaced-repetition.json` metadata (read by hooks); script behavior
   → argparse flag with an explicit `default=` and `choices=` where the value
   set is closed.
3. Make the code default match the documented default; if the live JSON value
   may diverge (like review_items_per_day 30 vs 20), read it with a
   `.get(key, DEFAULT)` fallback, never crash on absence.
4. Guard it: validate early with a descriptive exception (model:
   `active_unit()`'s ValueError), and keep write paths
   backup-then-atomic-replace (model: fluent_import.py `write_sr`).
5. Add a test to `scripts/test_fluent_import.py` if the axis touches the
   importer; run `python3 scripts/test_fluent_import.py` (expect 25+ passed).
6. Add a row to the relevant table in THIS skill with Default | Live | Guard |
   Re-verify command, date-stamped.
7. Never put secrets or machine-specific absolute paths into repo config — the
   whole repo deploys publicly on push to main (section 6).

## Provenance and maintenance

All values verified 2026-07-09 directly against disk. One drift probe per axis;
if any fails or disagrees, update the table before relying on it.

| Claim                               | Re-verify                                                                                                                               |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| one-active invariant + live pointer | `python3 -c "import json;print([u['id'] for u in json.load(open('link/curriculum.json'))['units'] if u['status']=='active'])"`          |
| importer flag set                   | `python3 scripts/fluent_import.py --help`                                                                                               |
| MASTERY_THRESHOLD 0.80              | `grep -n MASTERY_THRESHOLD scripts/fluent_import.py`                                                                                    |
| SR metadata + live daily limit      | `python3 -c "import json;d=json.load(open('$HOME/.claude/fluent-data/spaced-repetition.json'));print(d['metadata'],d['daily_limits'])"` |
| daily-limit code default 20         | `grep -n review_items_per_day "$CACHE/.claude/hooks/read-db.py"`                                                                        |
| optimizer guards 400/50             | `grep -n "MIN_TOTAL\|MIN_NEW" "$CACHE/.claude/hooks/optimize_weights.py"`                                                               |
| DEFAULT_W has 21 floats             | ast probe in section 4                                                                                                                  |
| script flags/defaults               | `python3 scripts/<script>.py --help` for each                                                                                           |
| whisper model hardcode              | `grep -n '"base"' scripts/audio_to_anki.py`                                                                                             |
| prettier + ignores                  | `cat .prettierrc .prettierignore`                                                                                                       |
| pages.yml exclusion                 | `grep -n "rm -f\|path:" .github/workflows/pages.yml`                                                                                    |
| LaunchAgent schedules/paths         | PlistBuddy loop in section 7                                                                                                            |
| Anki profiles + picker              | `ls ~/Library/Application\ Support/Anki2/; grep -n "profiles\[0\]" scripts/anki_utils.py`                                               |
| importer tests count                | `python3 scripts/test_fluent_import.py`                                                                                                 |

---
name: nederlands-debugging-playbook
description:
  "Use when something in this repo misbehaves: story-reader audio/highlight
  drift, Anki import mangled (tabs, [sound:] shows as text), fluent_import.py
  finds 0 vocab, grammar cards orphaned, review_history looks empty,
  update-db.py exit 1/2, ModuleNotFoundError whisper, wrong Anki profile,
  format:check fails, TTS drops paragraphs or overwrites files,
  CLAUDE_PLUGIN_ROOT empty, optimizer no-op, hook edits not taking effect."
---

# Nederlands repo — debugging playbook

Symptom → triage for this repo's known failure modes. Each trap carries its
origin story (commit or live probe) and a discriminating experiment so you
diagnose instead of guessing. All commands verified read-only on 2026-07-09.

**When NOT to use this skill:** for the full incident chronicle (what happened,
in order, with evidence) use `nederlands-failure-archaeology`; for normal
operation runbooks use `nederlands-run-and-operate`; for measurement probes and
interpretation use `nederlands-diagnostics-and-tooling`; before changing
anything to "fix" a trap, pass through `nederlands-change-control`.

Shell idiom used throughout (the Fluent runtime lives in a versioned cache dir;
resolve it, never hardcode):

```bash
CACHE=$(ls -d ~/.claude/plugins/cache/m98/fluent/*/ | sort -V | tail -1)
```

## Triage index

| #   | Symptom                                                    | Area       |
| --- | ---------------------------------------------------------- | ---------- |
| 1   | Story-reader highlight drifts / pins at last sentence      | Reader     |
| 2   | Story-reader misparses sentences after editing a story     | Reader     |
| 3   | Reader highlights overlap / double-fire                    | Reader     |
| 4   | Anki import: whole row lands in first field                | Anki       |
| 5   | Anki card shows literal `[sound:...]` text                 | Anki       |
| 6   | Anki file "looks wrong": no blank line after headers       | Anki       |
| 7   | `fluent_import.py` imports 0 vocab for a thema             | Importer   |
| 8   | Grammar cards duplicated/orphaned after re-import          | Importer   |
| 9   | "No reviews ever happened" (review_history empty)          | Fluent DB  |
| 10  | KeyError `spaced-repetition` reading read-db output        | Fluent DB  |
| 11  | `update-db.py` exits 1 or 2                                | Fluent DB  |
| 12  | `ModuleNotFoundError: No module named 'whisper'`           | Env        |
| 13  | Reader crashes FileNotFoundError despite WHISPER_AVAILABLE | Env        |
| 14  | Anki media lands in the wrong profile                      | Env        |
| 15  | `pnpm run format:check` exits 1 "randomly"                 | Tooling    |
| 16  | `--update-anki` destroyed columns in an anki file          | TTS        |
| 17  | TTS audio silently missing paragraphs                      | TTS        |
| 18  | `$CLAUDE_PLUGIN_ROOT` is empty in Bash                     | Fluent env |
| 19  | Weekly optimizer "did nothing"                             | Fluent     |
| 20  | Edited a Fluent hook; behavior unchanged                   | Fluent     |

## Reader / alignment

### 1. Highlight drifts out of sync, or pins at the last sentence

- **First check:** was the HTML generated with `--no-align`? Grep your shell
  history / regenerate: `python3 scripts/story_reader.py <story.md>` (default =
  Whisper forced alignment) vs `--no-align` (VTT greedy matching).
- **Root cause:** edge-tts VTT cues split on `!`/`?`/`:` mid-sentence; the
  greedy cue-to-sentence matcher desyncs and the highlight sticks at the end.
- **Fix:** regenerate WITHOUT `--no-align` (requires the `whisper` CLI, see trap
  12/13). `--no-align` is a known-buggy fallback, kept only for machines without
  Whisper.
- **Story:** commit e6f41db "Use Whisper forced alignment in story_reader to fix
  audio/highlight drift".

### 2. Reader misparses sentences after a story was edited/committed

- **First check:** did Prettier rewrap the story file? One sentence per line is
  the contract; look for continuation lines:
  `pnpm exec prettier --check <story.md>` and eyeball line lengths.
- **Root cause:** `proseWrap: always` (printWidth 80) split single-line
  sentences across lines; the reader parsed each physical line as a sentence.
- **Fix:** story*reader now merges continuation lines (51c5ba6), and
  `.prettierignore` excludes
  `\*\*/verhaal*\*.md`. If a NEW story path pattern is used, add it to `.prettierignore`
  before formatting — do not rely on the merge heuristic.
- **Story:** commit 51c5ba6 "Make story_reader resilient to Prettier-wrapped
  markdown".

### 3. Highlights overlap / two sentences lit at once

- **First check:** which Whisper model produced the timestamps? `base` is
  hardcoded in `scripts/audio_to_anki.py` line ~51 (verified 2026-07-09).
- **Root cause:** Whisper `base` occasionally emits overlapping word timestamps;
  `turbo` gave 0 overlaps on the same audio.
- **Discriminating experiment:** rerun alignment with turbo and diff timings:
  `whisper <mp3> --model turbo --word_timestamps True ...` vs base output.
- **Fix:** for readers, use turbo. Note the hardcoded `base` default is a
  deliberate speed/quality tradeoff for short course audio — changing the
  default is a change-control item.
- **Story:** commit 1c88339 ("Whisper turbo alignment — 0 overlaps vs base's
  occasional overlap, 124 sentences").

## Anki files

### 4. Anki import puts the whole row into the first field

- **First check:** are there real TABs in the file?
  `grep -c $'\t' <file_anki.txt>` — 0 or a low count on a data-full file means
  tabs were converted to spaces (editors, copy-paste, and LLM rewrites all do
  this). Visualize: `cat -t <file> | head` (tabs show as `^I`).
- **Root cause:** the `_anki.txt` format is literal TAB-separated
  (`#separator:tab`); space-"aligned" columns are silent corruption.
- **Fix:** restore from git (`git checkout -- <file>`) or re-insert tabs. Never
  let a formatter touch `*_anki.txt` — it is in `.prettierignore` for this
  reason.
- **Story:** recurring editing hazard; format contract documented in CLAUDE.md
  "Anki File Formats".

### 5. Card shows literal `[sound:x.mp3]` text instead of playing audio

- **First check:** `head -3 <file_anki.txt>` — is `#html:true` present?
- **Root cause:** `[sound:]` tags inside fields require `#html:true` on import;
  without it Anki treats the tag as plain text.
- **Fix:** add `#html:true` to the header block and re-import.
- **Story:** commit 8cd356c "Unify html:true across all Link Anki card files"
  (HyperTTS writes `[sound:]` directly into fields).

### 6. Some anki files have a blank line after the headers, some don't

- **Not a bug.** Verified 2026-07-09: thema_12/13 woordenlijst files have a
  blank line after `#tags column:5`; thema_4–6 files do not. Anki ignores blank
  lines; `fluent_import.py` skips rows with <3 columns, so both parse.
- **Trap:** scripts that assume data starts at a fixed line number break on one
  of the two variants. Parse by content (skip `#`-lines and blanks), never by
  offset. Do NOT "normalize" the files — pure churn, and diffs of published
  files break nothing but waste review attention.

## Curriculum importer (`scripts/fluent_import.py`)

### 7. Import reports 0 vocab / "лексика 0" for a thema that has vocab

- **First check:** the vocab glob is at `scripts/fluent_import.py:93` (verified
  2026-07-09): `sorted(unit_dir.rglob(f"*woordenlijst*thema{num}*_anki.txt"))`.
  Probe what it actually matches:

  ```bash
  python3 -c "from pathlib import Path;
  print(*Path('link/thema_13').rglob('*woordenlijst*thema13*_anki.txt'),
  sep='\n')"
  ```

- **Root cause:** filenames missing the `thema{N}` token (e.g.
  `woordenlijst_taak1_anki.txt`) are silently not imported. No warning is
  printed.
- **Fix:** name new files `woordenlijst_thema{N}_taak{K}_anki.txt`. Do NOT
  rename existing published files to match (GitHub Pages links are load-bearing,
  incl. typo'd names) — instead add a correctly-named file or fix at creation
  time.

### 8. Grammar cards duplicated or orphaned after re-import

- **First check:** compare grammar item_ids before/after:

  ```bash
  python3 -c "
  import json, pathlib
  p = pathlib.Path.home()/'.claude/fluent-data/spaced-repetition.json'
  d = json.loads(p.read_text())
  print(*sorted(k for k in d['items'] if '_gram_' in k)[:20], sep='\n')"
  ```

- **Root cause:** grammar item*ids are POSITIONAL —
  `{prefix}gram*{module*num}*{idx}` (`fluent*import.py:157`), where `idx`is the ordinal of the`**bold**`example under the module. Inserting, deleting, or reordering bold examples in`grammatica_thema{NN}*\*.md`after import shifts`idx`:
  re-import then seeds NEW ids while the old scheduled cards keep their
  (now-unmatched) content — orphans with live intervals.
- **Fix:** finish grammar edits BEFORE first import of that thema. If the file
  was already imported, appending new examples at the END of a module is safe
  (existing idx unchanged); anything else goes through
  `nederlands-change-control`.
- **Story:** design property of the bridge (specs in
  `docs/superpowers/specs/2026-06-26-fluent-curriculum-bridge-design.md`).

## Fluent databases

### 9. "No reviews have ever happened" — review_history is empty

- **First check — do NOT trust the top-level key.** Count both:

  ```bash
  python3 -c "
  import json, pathlib
  p = pathlib.Path.home()/'.claude/fluent-data/spaced-repetition.json'
  d = json.loads(p.read_text())
  print('top-level:', len(d.get('review_history', [])))
  print('per-item sum:', sum(len(v.get('review_history', []))
        for v in d['items'].values()))"
  ```

- **Root cause:** top-level `review_history` in `spaced-repetition.json` is an
  empty LEGACY list. Real reviews live per-item in `items[*].review_history`.
  Verified 2026-07-09: top-level 0, per-item sum 225.
- **Fix:** always aggregate per-item (that is what
  `optimize_weights.py:extract_logs` does). Any diagnostic reading the top-level
  list will falsely conclude zero activity.

### 10. KeyError / empty result reading read-db.py output

- **First check:** you probably used a hyphen key. Output keys use UNDERSCORES
  (`spaced_repetition`, `mistakes_db`, ...) while the files on disk use hyphens
  (`spaced-repetition.json`). Verified: `read-db.py:37`.
- **Fix:**
  `python3 "$CACHE/.claude/hooks/read-db.py" | python3 -c "import json,sys; print(list(json.load(sys.stdin)))"`
  and use the keys you see. `--review` mode additionally empties
  `mastery_db`/`progress_db`/ `session_log` in the payload by design (a −90%
  size optimization) — empty there does not mean empty on disk.

### 11. update-db.py exits nonzero — what does the code mean?

Contract (verified in `$CACHE/.claude/hooks/update-db.py`, 2026-07-09):

| Exit | Meaning                                                     | Disk state                                    |
| ---- | ----------------------------------------------------------- | --------------------------------------------- |
| 0    | all 6 DBs written                                           | backup in `.backups/pre-update-<session_id>/` |
| 1    | bad stdin JSON, missing `session_id`/`date`, bad milestones | untouched                                     |
| 2    | load/update/save exception (traceback on stderr)            | untouched                                     |

- **Triage:** exit 1 → fix your payload (example at
  `$CACHE/.claude/references/db-updater-payload.example.json`); exit 2 → read
  the stderr traceback; a corrupt DB file will surface here as a load error. It
  works on deep copies and backs up before writing, so a nonzero exit never
  leaves partial writes.

## Environment traps

### 12. `import whisper` fails but Whisper clearly works on this machine

- **First check:** `which whisper` → `~/.local/bin/whisper` (pipx);
  `python3 -c "import whisper"` → ModuleNotFoundError. Both verified 2026-07-09.
  This is BY DESIGN.
- **Root cause:** Whisper is installed as a pipx CLI only; repo scripts
  subprocess the CLI (`audio_to_anki.py:42`), never import the module.
- **Fix:** none needed. Do NOT `pip install openai-whisper` into system python
  to "fix" an import — write code that shells out to the CLI instead.

### 13. FileNotFoundError in story_reader despite WHISPER_AVAILABLE=True

- **Root cause:** `WHISPER_AVAILABLE` (`story_reader.py:24-34`) only tests that
  `from audio_to_anki import ...` succeeds — it never checks that the `whisper`
  CLI exists. On a machine without the CLI the flag is still True and the
  subprocess raises FileNotFoundError at alignment time.
- **First check:** `which whisper`. Missing → install via
  `pipx install openai-whisper`, or use `--no-align` (accepting trap 1).

### 14. Anki media copied to the wrong profile

- **First check:** there are TWO profiles —
  `ls ~/Library/Application\ Support/Anki2/` → `alex`, `iuliia`.
  `anki_utils.find_anki_media_folder()` picks `profiles[0]` from an UNSORTED
  `iterdir()` and only prints a warning
  (`Найдено N профилей, использую: <name>`). There is no `--profile` flag.
- **Discriminating experiment:** after any `--copy-to-anki` run, confirm where
  files landed:
  `ls -t ~/Library/Application\ Support/Anki2/alex/collection.media | head`.
- **Fix/workaround:** read the script's warning line every run. Currently it
  picks `alex` by filesystem luck; if it ever picks `iuliia`, move the files
  manually and file the missing `--profile` flag as a change-control item.

### 15. `pnpm run format:check` exits 1 but tracked files are clean

- **First check:** read WHICH files it warns about. Verified 2026-07-09: exit 1
  caused by UNTRACKED scratch (`.superpowers/sdd/*.md`, `link/thema_13/les.md` —
  Alex's raw class notes, never to be formatted).
- **Fix:** scope the check to tracked files before trusting the exit code:

  ```bash
  git ls-files '*.md' | xargs pnpm exec prettier --check
  ```

  Do not format `les.md` (raw learner errors are the data) and do not add a
  blanket `--write` run to CI to make the check pass.

## TTS (`scripts/text_to_speech.py`)

### 16. `--update-anki` rewrote my anki file and lost columns

- **Root cause:** `update_anki_file()` (lines 279–325) rewrites the INPUT file
  in place, no backup, and emits exactly 4 columns per matched row:
  `col0 \t col1 \t [sound:...] \t sententiae::{theme}::{level}::audio`. Running
  it on a 5-column Word-format file silently drops columns 3–5
  (Translation/TranslationExample/Tags shift or vanish) and replaces the tags.
- **First check after damage:** `git status <file>` — anki files are tracked, so
  `git diff <file>` shows exactly what was lost and `git checkout -- <file>`
  restores it.
- **Fix:** only run `--update-anki` on 4-column sentence files it was built for;
  for anything else generate a NEW file (the default path) and merge by hand.
  Copy the input aside first if it has uncommitted edits.

### 17. Generated audio is missing paragraphs

- **Root cause:** plain-markdown mode silently skips any paragraph containing
  `...` (`text_to_speech.py:140`, a placeholder heuristic), plus headers,
  tables, blockquotes, pure-italic lines, and anything under 5 chars after
  cleanup.
- **First check:** count spoken sentences in the script's own output list vs
  paragraphs in the source; grep the source for `...`.
- **Fix:** replace literal `...` in prose with `…` (single ellipsis char) or
  rewrite the sentence; keep `...` only in genuine placeholder lines.

## Fluent plugin runtime

### 18. `$CLAUDE_PLUGIN_ROOT` is empty in Bash

- **Verified 2026-07-09:** `printenv CLAUDE_PLUGIN_ROOT` exits 1 (unset) in
  Bash-tool shells. It is only populated for the plugin's own hook invocations.
- **Fix:** resolve the runtime path yourself, version-agnostically:

  ```bash
  CACHE=$(ls -d ~/.claude/plugins/cache/m98/fluent/*/ | sort -V | tail -1)
  python3 "$CACHE/.claude/hooks/read-db.py" | head -c 200
  ```

  Never hardcode `0.3.0` in new scripts or settings — a version bump changes the
  path (the optimizer LaunchAgent plist already hardcodes it; known weak point).

### 19. Weekly optimizer "did nothing" — log says no-op

- **This is NORMAL, not a bug.** Guards (verified
  `$CACHE/.claude/hooks/optimize_weights.py:14-15`): `MIN_TOTAL = 400` reviews
  AND `MIN_NEW = 50` since last optimize, counted PER-ITEM (trap 9).
- **First check:** `tail -3 ~/.claude/logs/fluent-fsrs-optimize.log` — expected
  line shape: `[optimize] insufficient data (185/400, +185 new) — no-op`.
- **Only investigate if:** the log shows an exception/traceback, or the per-item
  review sum is ≥400 with ≥50 new and it STILL no-ops. Until then
  `weights: null` in spaced-repetition metadata (hook uses DEFAULT_W) is the
  correct steady state.

### 20. Edited a Fluent hook, behavior didn't change

- **Root cause:** Claude Code executes hooks from the CACHE
  (`~/.claude/plugins/cache/m98/fluent/<version>/.claude/hooks/`), not from the
  dev clone (`~/Projects/fluent`) or the marketplace clone
  (`~/.claude/plugins/marketplaces/m98`). Editing a clone changes nothing at
  runtime until synced to the cache. The clone→cache sync procedure is
  UNDOCUMENTED (known weak point) — verify state, don't assume.
- **Discriminating experiment:** diff the file you edited against the runtime
  copy:

  ```bash
  diff -q ~/Projects/fluent/.claude/hooks/update-db.py \
      "$CACHE/.claude/hooks/update-db.py"
  ```

  As of 2026-07-09 `update-db.py` DIFFERED between the marketplace clone and the
  cache — direction unverified; verify live before copying either way, and check
  clone sync too:
  `git -C ~/Projects/fluent fetch && git -C ~/Projects/fluent status` vs
  `git -C ~/.claude/plugins/marketplaces/m98 log -1`.

- **Fix:** land the change in the fork (`aymkin/fluent`) first, then sync to
  cache; raw cache edits get silently clobbered by plugin updates. Route via
  `nederlands-change-control`.

## Provenance and maintenance

All claims verified 2026-07-09 against disk/git. Re-verify before trusting:

- Commit stories: `git log --oneline -1 e6f41db 51c5ba6 1c88339 8cd356c`
- Vocab glob + grammar id scheme:
  `grep -n 'woordenlijst\*thema\|gram_' scripts/fluent_import.py`
- Whisper model default: `grep -n '"base"' scripts/audio_to_anki.py`
- WHISPER_AVAILABLE logic: `sed -n '24,34p' scripts/story_reader.py`
- TTS `...` drop + in-place rewrite:
  `grep -n '"\.\.\." in para\|def update_anki_file' scripts/text_to_speech.py`
- Profile roulette: `grep -n 'profiles\[0\]' scripts/anki_utils.py`;
  `ls ~/Library/Application\ Support/Anki2/`
- review_history split + counts: python probe in trap 9 (numbers are volatile —
  225 was the 2026-07-09 value)
- read-db underscore keys:
  `grep -n 'spaced_repetition' "$CACHE/.claude/hooks/read-db.py"`
- update-db exit codes: `grep -n 'sys.exit' "$CACHE/.claude/hooks/update-db.py"`
- Optimizer guards:
  `grep -n 'MIN_TOTAL\|MIN_NEW' "$CACHE/.claude/hooks/optimize_weights.py"` and
  `tail ~/.claude/logs/fluent-fsrs-optimize.log`
- CLAUDE_PLUGIN_ROOT: `printenv CLAUDE_PLUGIN_ROOT; echo $?`
- format:check behavior: `pnpm run format:check` and read the `[warn]` list
- Clone/cache drift: `diff -q` commands in trap 20 (state was CONFLICTING across
  same-day observations — always check live)

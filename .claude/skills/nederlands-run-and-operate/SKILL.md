---
name: nederlands-run-and-operate
description: >-
  Use when running or operating anything in the nederlands repo: importing cards
  with fluent_import.py (--check, --advance, --thema, --taak), running a Fluent
  review session (/fluent-review, read-db.py --review, update-db.py stdin, exit
  codes 0/1/2), restoring fluent-data from .backups, generating audio or readers
  (audio_to_anki.py, text_to_speech.py, story_reader.py), building the vocab
  index, checking LaunchAgent logs, or what publishes to GitHub Pages and how
  read.html ?f= works.
---

# Run and operate: nederlands repo + Fluent ecosystem

Operator's manual: every runnable thing, where its output lands, and how to
recover. All commands and output samples below were re-run and verified on
2026-07-09 unless marked otherwise.

**When NOT to use this skill:** recreating the environment from scratch →
`nederlands-build-and-env`; triaging a failure symptom →
`nederlands-debugging-playbook`; draining the review backlog / advancing the
curriculum → `fluent-backlog-campaign`; before any state-mutating change →
`nederlands-change-control`.

## Path anatomy

| Thing                | Path                                                      |
| -------------------- | --------------------------------------------------------- |
| Repo root            | `/Users/Alex.Naymkin/Projects/nederlands`                 |
| Fluent runtime hooks | `~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/` |
| Fluent data (6 DBs)  | `~/.claude/fluent-data/`                                  |
| Backups              | `~/.claude/fluent-data/.backups/`                         |
| Session results      | `~/.claude/fluent-data/results/fluent-*-session-NNN.md`   |

The `0.3.0` in the cache path is a version pin: a plugin version bump changes
the path AND breaks the optimizer LaunchAgent plist, which hardcodes it. Resolve
dynamically when scripting:

```bash
FLUENT_HOOKS=$(ls -d ~/.claude/plugins/cache/m98/fluent/*/ | sort -V \
  | tail -1)/.claude/hooks
```

## fluent_import.py — the four modes

`scripts/fluent_import.py` (stdlib-only, run with system `python3`) bridges
`link/curriculum.json` (owns sequence/progress) into Fluent's
`spaced-repetition.json` (owns scheduling). It writes ONLY
spaced-repetition.json and backs it up first. All output is in Russian.

| Mode       | Command                                                               | Writes?             |
| ---------- | --------------------------------------------------------------------- | ------------------- |
| Import     | `python3 scripts/fluent_import.py --course link`                      | yes                 |
| Gate check | `python3 scripts/fluent_import.py --course link --check [--thema N]`  | no                  |
| Advance    | `python3 scripts/fluent_import.py --course link --advance`            | yes (manifest + SR) |
| Focus      | `python3 scripts/fluent_import.py --course link --thema N [--taak K]` | yes (SR only)       |

Verified output samples (run live 2026-07-09):

```
$ python3 scripts/fluent_import.py --course link --check
thema_4 — 51 карточек | mastery≥3: 0/51 (0.0%) | красных: 0
⏳ продолжай

$ python3 scripts/fluent_import.py --course link --check --thema 13
thema_13 — 139 карточек | mastery≥3: 0/139 (0.0%) | красных: 0
⏳ продолжай
```

`--check` line format:
`<unit> — <total> карточек | mastery≥3: <n>/<total> (<pct>) | красных: <red>`
then `✅ готов дальше — запусти --advance` or `⏳ продолжай`. Exit code is 0
either way — parse the text, not the code. Ready = total>0 AND mastered/total ≥
0.80 AND red==0 (red = `consecutive_incorrect >= 2`).

Import mode prints (format from `main()` in the script):

```
Импорт thema_N: лексика X, грамматика Y, новых Z
Пропущены модули без жирных примеров: 2.3 Titel; ...   # only if any
```

"новых Z" (new) can be 0 on re-run — the importer is idempotent by `item_id`;
existing items are never touched. `--advance` prints
`→ active: thema_N | added Z`.

Operational rules:

- `--thema N` imports WITHOUT moving the curriculum pointer; `--advance` moves
  it (exactly one unit `active`, else ValueError).
- Edit grammar files BEFORE importing: grammar item_ids are positional
  (`link_t13_gram_3.8_10`); reordering bold examples after import orphans cards.
- Vocab files must match `*woordenlijst*thema{N}*_anki.txt` inside the thema
  dir; a filename missing `thema{N}` is silently not imported.
- As of 2026-07-09 curriculum.json says thema_4 active while real study is thema
  12/13 (focus imports). Repoint is approved in principle but gated — see
  `fluent-backlog-campaign`; do not `--advance` casually.

## Fluent session lifecycle (review flow)

```
/fluent-review (plugin skill)
  └─ python3 $FLUENT_HOOKS/read-db.py --review      # read-only
       → one JSON payload to stdout (capped + trimmed)
  └─ tutor session (questions, feedback, scoring)
  └─ fluent-db-updater skill builds ONE JSON report
       └─ python3 $FLUENT_HOOKS/update-db.py <<'EOF' ... EOF   # stdin
            exit 0: backs up all 6 DBs to
              .backups/pre-update-<session_id>/, writes all 6
              atomically (tmp+fsync+replace), rebuilds review_queue
            exit 1: validation error — disk untouched
            exit 2: load/update/save exception — disk untouched
```

### read-db.py --review payload (verified live 2026-07-09)

```bash
python3 $FLUENT_HOOKS/read-db.py --review > /tmp/payload.json
```

Live run: exit 0, payload 35 KB. What `--review` does server-side:

- Sorts `review_queue.today` by priority (critical→high→medium→low), slices to
  `daily_limits.review_items_per_day` (live value 30; code default 20). Live:
  today queue 335 → payload queue and `items` = 30.
- `computed.due_review_items` is NOT trimmed — it listed all 335 due ids. Use
  `computed.due_reviews_count` for the true backlog,
  `computed.review_queue_trimmed_to` (30) for the session size.
- Empties `mastery_db`, `progress_db`, `session_log` in the payload and filters
  `mistakes_db.error_patterns` to patterns referenced by the capped queue.
  On-disk files are NOT modified.
- Other `computed` keys: `today`, `next_session_id` (live: session-022),
  `streak_active`, `days_since_last_session`.

Exit codes: 0 = all 6 files loaded; 1 = some missing (`_warnings` lists them); 2
= critical error.

**The 30/day cap is enforced ONLY by the plugin skill prompts, not by python.**
Any session that bypasses `/fluent-review` bypasses the cap.

### update-db.py payload contract (verified against main(), 628 lines)

Required: `session_id`, `date` — missing either → stderr
`[Fluent] Error: Missing required field '...'`, exit 1, disk untouched. All
other fields optional. Key optional arrays:

| Field              | Per-entry requirement                                                                     |
| ------------------ | ----------------------------------------------------------------------------------------- |
| `review_results[]` | `item_id` + `quality` (0-5); `score` optional — omit it, historical scores are unreliable |
| `errors[]`         | `pattern_id` (plus category/your_answer/correct_answer)                                   |
| `new_vocabulary[]` | `item_id` (plus content/answer/category)                                                  |
| `milestones[]`     | bare string OR `{"milestone": "...", "date": "..."}`                                      |

Canonical example payload:
`$FLUENT_HOOKS/../references/db-updater-payload.example.json`.

Success output (exit 0) starts
`[Fluent] ✅ Updated 6 databases for session session-NNN` followed by
streak/accuracy/SR summary lines. FSRS-6 is the live scheduler inside
update-db.py (`fsrs.schedule(...)`); `calculate_sm2` still exists in the file as
a rollback path only. Never hand-edit `spaced-repetition.json` — the queue is
rebuilt on every update-db.py call.

## Reading the DBs safely

Payload keys use UNDERSCORES while filenames use hyphens: `spaced_repetition` ↔
`spaced-repetition.json`, `mistakes_db` ↔ `mistakes-db.json`, etc.

Full dump: `python3 $FLUENT_HOOKS/read-db.py` (all 6 DBs + `computed`). For spot
checks, probe the JSON directly (read-only):

```bash
python3 - <<'EOF'
import json, pathlib
sr = json.loads((pathlib.Path.home()
    / ".claude/fluent-data/spaced-repetition.json").read_text())
print({k: len(v) for k, v in sr["review_queue"].items()})
print("items:", len(sr["items"]), "| limits:", sr["daily_limits"])
print("scheduler:", sr["metadata"].get("scheduler"))
EOF
```

Live 2026-07-09: queue
`{'today': 335, 'tomorrow': 12, 'this_week': 15, 'later': 46}`, 408 items,
`review_items_per_day: 30`, scheduler `fsrs-6` (metadata `algorithm` also read
`FSRS-6` on this date). Real review history lives per-item in
`items[*].review_history`; the top-level `review_history` list is empty legacy —
never count from it.

## TTS / reader pipelines — outputs land in course dirs and PUBLISH

All three scripts write output NEXT TO their input. Course dirs deploy to public
GitHub Pages on every push to main (see below) — whatever these scripts generate
inside `link/`, `de_opmaat/`, etc. becomes public.

### audio_to_anki.py (needs ffmpeg + pipx whisper CLI)

```bash
python3 scripts/audio_to_anki.py path/to/dialog.mp3 \
  --transcript path/to/dialog.md --theme gezondheid --copy-to-anki
```

Outputs, both next to the input mp3: `{prefix}_sentences/` (split mp3s) and
`sententiae_{theme}_anki.txt`. Prefer `--transcript` (forced alignment); without
it, whisper-only text is used raw. Transcript speaker names must be single words
(`Anna: ...`).

### text_to_speech.py (needs edge-tts)

```bash
python3 scripts/text_to_speech.py input.md --voice colette --copy-to-anki
```

Auto-detects input format: existing `_anki.txt` / transcript / plain markdown.
Outputs next to input: `{prefix}_sentences/` + `sententiae_{theme}_anki.txt`, or
a single `{prefix}.mp3` with `--whole`.

**WARNING — `--update-anki` rewrites the INPUT `_anki.txt` file in place, no
backup** (verified: `update_anki_file(input_path, ...)`). Copy the file first:

```bash
cp cards_anki.txt cards_anki.txt.bak
python3 scripts/text_to_speech.py cards_anki.txt --update-anki
```

Plain-markdown mode silently drops paragraphs containing `...`. Default voice
`colette`; choices colette/fenna (F), maarten (M).

### story_reader.py (needs edge-tts; whisper CLI for alignment)

```bash
python3 scripts/story_reader.py path/to/verhaal_x.md
```

Output: `<input_stem>_reader.html` next to the input — self-contained HTML with
base64 audio. Default uses Whisper forced alignment; `--no-align` falls back to
VTT greedy matching, which is known-buggy (edge-tts splits cues on `!`/`?`/`:`
and highlights desync). Input must be one sentence per line; `*_reader.html` and
`verhaal_*.md` are prettier-ignored so wrapping never corrupts them.

**Readers embed a frozen copy of text + audio. After editing a story's markdown,
regenerate its `_reader.html`** — content edits do not propagate. Precedent: the
Voldemort-rule scrub (commit 5be6931) explicitly checked whether readers needed
regeneration ("No TTS regeneration needed — ... have no HTML readers yet"). If a
reader had existed, it would have kept publishing the scrubbed text.

## build_vocab_index.py — run BEFORE generating cards

Standing feedback rule: before creating any Anki cards, rebuild and read the
vocab index instead of opening 20+ woordenlijst files:

```bash
python3 scripts/build_vocab_index.py --course link   # or de_opmaat | both
```

Writes `<course>/woordenlijst_index.txt`. No `link_plus` support —
`link_plus/woordenlijst_index.txt` on disk is a stale pre-rename snapshot; do
not trust or regenerate-in-place for Yulia's course.

## LaunchAgents — operations view

Three agents (all present in `~/Library/LaunchAgents/`, verified via `plutil -p`
2026-07-09):

| Agent                           | Schedule    | Log(s)                                      |
| ------------------------------- | ----------- | ------------------------------------------- |
| com.aymkin.claude-plugin-update | daily 09:03 | `/tmp/claude-plugin-update.log`             |
| com.aymkin.claude-dotfiles-sync | daily 09:04 | `~/.claude/logs/sync.log`, `sync-error.log` |
| com.aymkin.fluent-fsrs-optimize | Sun 09:05   | `~/.claude/logs/fluent-fsrs-optimize.log`   |

Green/red criteria per agent:

**plugin-update** — green: per-repo `Already up to date.` / fast-forward blocks;
it also rewrites `skills.lock`. KNOWN unrelated red entries appear on every run
— do not chase them: `[autoresearch] fatal: couldn't find remote ref main` and
`[claude-plugins-official] fatal: not a git repository (or any of the parent directories): .git`
(both verified recurring throughout the log). Occasional
`ssh_dispatch_run_fatal ... Operation timed out` = transient network. Red worth
chasing: a FAILED pull of the `m98` (Fluent) repo.

**dotfiles-sync** — green in `sync.log`:
`Syncing from ~/.claude/ to repo... Done!` followed by an
`auto-sync: YYYY-MM-DD (updated: ...)` commit line. `sync-error.log` is stderr,
and git writes push confirmations to stderr — so lines like
`To github.com:aymkin/claude-dotfiles.git` + `abc1234..def5678  main -> main` in
sync-error.log are SUCCESS, not errors (verified: that is its entire recent
content).

**fluent-fsrs-optimize** — the guarded FSRS weight optimizer. Green no-op (the
log's only line as of 2026-07-09):

```
[optimize] insufficient data (185/400, +185 new) — no-op
```

It activates at ≥400 total reviews AND ≥50 new since last optimize. Its plist
hardcodes `.../cache/m98/fluent/0.3.0/.claude/hooks/optimize_weights.py` and
`.venv-optimizer/bin/python` — a plugin version bump silently breaks it (empty
log growth on Sundays = check the plist path first).

## BACKUP RESTORE RUNBOOK (fluent-data)

Snapshot types under `~/.claude/fluent-data/.backups/` (70 dirs as of
2026-07-09) and what each contains (verified by listing):

| Dir pattern                | Created by           | Contains                                    |
| -------------------------- | -------------------- | ------------------------------------------- |
| `YYYYMMDD/`                | session-end hook     | all 6 JSONs                                 |
| `pre-update-session-NNN/`  | update-db.py         | all 6 JSONs                                 |
| `precompact/` (single dir) | precompact-backup.sh | all 6 JSONs (overwritten each compact)      |
| `pre-migrate-fsrs-<ts>/`   | migrate_to_fsrs.py   | all 6 JSONs                                 |
| `pre-import-<ts>/`         | fluent_import.py     | spaced-repetition.json ONLY                 |
| `pre-optimize-<date>/`     | optimize_weights.py  | none exist yet (optimizer has only no-op'd) |

Restore procedure — all-or-nothing per snapshot, plain copy back:

```bash
# 1. Pick the snapshot (newest matching your incident time)
ls -t ~/.claude/fluent-data/.backups/ | head

# 2. Safety-copy current state first
cp -R ~/.claude/fluent-data ~/.claude/fluent-data.broken-$(date +%s)

# 3. Copy every JSON in the snapshot back (6 files, or 1 for pre-import)
cp ~/.claude/fluent-data/.backups/<DIR>/*.json ~/.claude/fluent-data/

# 4. Verify: exit 0 and sane computed block
python3 $FLUENT_HOOKS/read-db.py > /tmp/verify.json; echo "exit $?"
python3 -c "import json; d=json.load(open('/tmp/verify.json')); \
print(d['computed'])"
```

Never mix files from two snapshots — the 6 DBs cross-reference session ids and
item ids; a partial restore desyncs them. For a `pre-import-*` restore (only
spaced-repetition.json), the other 5 files stay current — that is correct,
because the importer only touched spaced-repetition.json.

## GitHub Pages — everything you commit publishes

`.github/workflows/pages.yml` deploys the ENTIRE repo (`path: .`) to GitHub
Pages on every push to main; sole exclusion is
`rm -f other/nieuw_in_rotterdam/*.epub *.pdf`. Live site (verified via
`gh api repos/aymkin/nederlands/pages`):

```
https://aymkin.github.io/nederlands/
```

URL structure = repo-relative path, e.g.
`https://aymkin.github.io/nederlands/link/thema_13/grammatica_thema13_gas_water_elektriciteit.md`.

`read.html` at the repo root is a client-side markdown reader:

```
https://aymkin.github.io/nederlands/read.html?f=link/thema_13/grammatica_thema13_gas_water_elektriciteit.md
```

Accepts `?f=` or `?file=` (repo-relative path); rejects paths containing `..`,
starting with `/`, or matching `^https?:`. It loads marked@13.0.2 from the
jsdelivr CDN — the repo's one external runtime dependency.

Operational consequence: mp3s and `_reader.html` files generated by the
pipelines above, graded-test PDFs, and raw class notes all go public minutes
after a push. Typo'd filenames (e.g. `opdrach_3.md`) are load-bearing public
URLs — never rename without checking inbound links.

## Provenance and maintenance

Verified 2026-07-09. One re-check command per drift-prone claim:

- Importer modes/flags: `python3 scripts/fluent_import.py --course link --check`
  and read `scripts/fluent_import.py` `main()`.
- Queue/limits/scheduler live values: the python3 probe in "Reading the DBs
  safely" above.
- `--review` cap and trimming:
  `python3 $FLUENT_HOOKS/read-db.py --review | python3 -c "import json,sys; d=json.load(sys.stdin); \ print(d['computed']['review_queue_trimmed_to'])"`.
- update-db.py contract/exit codes:
  `sed -n '547,628p' $FLUENT_HOOKS/update-db.py`.
- Backup dir census: `ls ~/.claude/fluent-data/.backups/ | wc -l` and
  `ls ~/.claude/fluent-data/.backups/<newest>/`.
- LaunchAgent schedules/paths:
  `plutil -p ~/Library/LaunchAgents/com.aymkin.*.plist`.
- Optimizer state: `cat ~/.claude/logs/fluent-fsrs-optimize.log`.
- Known-red plugin-update entries:
  `grep -cE 'autoresearch.*remote ref|claude-plugins-official.*not a git' /tmp/claude-plugin-update.log`.
- Pages URL: `gh api repos/aymkin/nederlands/pages --jq .html_url`.
- Script flags: `python3 scripts/<script>.py --help` (each of the four).
- In-place `--update-anki` behavior:
  `grep -n 'update_anki_file(input_path' scripts/text_to_speech.py`.

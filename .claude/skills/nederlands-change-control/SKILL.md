---
name: nederlands-change-control
description:
  Use when about to commit, push, rename, move, delete, reformat, or mass-edit
  anything in the nederlands repo; before running Prettier over tracked files;
  before editing grammatica files, _anki.txt decks, curriculum.json, or Fluent
  plugin hooks; before touching ~/.claude/fluent-data; when the working tree has
  mixed churn and real changes; when asked to "clean up", "fix" a filename typo,
  migrate tags, bump the Fluent version, or create a study-plan system.
---

# Change control — nederlands repo

How changes are classified, gated, and reviewed here. Every rule below has a
rationale AND a historical incident behind it (commit hashes cited — verify with
`git show <hash> --stat`). Nothing in this repo may route around this skill.

**When NOT to use this skill:** for the story of _how_ an incident unfolded, use
`nederlands-failure-archaeology`; for _running_ importers/scripts, use
`nederlands-run-and-operate`; for content QA formats and evidence bars, use
`nederlands-validation-and-qa`; for the design invariants themselves, use
`nederlands-architecture-contract`; for executing the backlog/curriculum
campaign, use `fluent-backlog-campaign`.

## Prime directive: main is public, live, within minutes

`.github/workflows/pages.yml` is the only CI. On every push to `main` it deploys
the ENTIRE repo (`path: .`) to GitHub Pages. Sole exclusion:
`rm -f other/nieuw_in_rotterdam/*.epub *.pdf` (copyrighted book binaries).
Everything else — PDFs, mp3s, personal notes, graded test results — publishes
publicly minutes after push.

Consequences:

1. **Commit or push only on explicit owner request.** Never proactively.
2. There is no staging environment. A pushed commit IS a deploy.
3. Output files that scripts drop next to their inputs (e.g. `audio_to_anki.py`
   artifacts) get published too if committed.

## Change lanes and their gates

| Lane              | What's in it                                                             | Gate before commit                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **content**       | `link/`, `link_plus/`, `de_opmaat/`, `other/`, `daily/` md + `_anki.txt` | Voldemort grep (below); Anki TSV format check (literal TABs, `#html:true` with `[sound:]`); no renames of existing files; Prettier on md only            |
| **scripts**       | `scripts/*.py`                                                           | `python3 scripts/test_fluent_import.py` → expect **25 passed** (as of 2026-07-09; `scripts/README.md` says 21 — README is stale, don't "fix" tests down) |
| **fluent-plugin** | fork `~/Projects/fluent`, cache hooks                                    | NOT this repo — see multi-repo flow below; never edit cache without syncing the fork first                                                               |
| **docs**          | `docs/superpowers/`, `CLAUDE.md`, READMEs, `.claude/skills/`             | 80-col proseWrap; where CLAUDE.md is documented-stale, correct it or note it — never propagate the stale claim                                           |
| **config**        | `curriculum.json`, `.prettierrc`, `package.json`, `pages.yml`            | curriculum.json: exactly ONE unit `status: "active"` (importer raises ValueError otherwise); pages.yml changes alter public exposure — owner sign-off    |

## Commit protocol

Use the `/commit` command (`.claude/commands/commit.md`). Format:

```
<type>: <summary, imperative, ≤50 chars>

<what changed, wrapped at 72>

<why — motivation from conversation context>
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`. The command shows the
proposed message and asks before committing — keep that confirmation step.

**No attribution footers, ever** (no "Generated with…", "Co-Authored-By…",
"Crafted by…") — owner's global rule, for commits AND PR descriptions.

## Non-negotiables (rule → rationale → incident)

### 1. Voldemort grep gate before any content commit

The words Rusland / Россия must never appear in any content. Characters in
stories come from Oekraïne, Polen, Turkije.

```bash
git grep -inE 'rusland|росси' -- '*.md' '*.txt'
```

Expect zero output. (`-i` matches Cyrillic case on macOS grep/git-grep —
verified 2026-07-09.) Incident: commit `5be6931` (2026-04-21) had to scrub
country-of-origin references from 8 already-published files.

### 2. Never rename load-bearing typo'd files or normalize legacy naming

Files like `de_opmaat/thema_5/opdrach_3.md` (sic) and
`woordenlijst_page_14_anki.txt` (vs `_pagina_` elsewhere) are typos that SHIP.
Renaming breaks public GitHub Pages URLs that exist in the wild, and Anki decks
reference generated tags/media by the old names. Same for `link_plus/` directory
naming: it mixes three eras (`{N}_{task_name}` in thema_1, plain `taak_N`
elsewhere) — do not normalize.

### 3. Never migrate `link::` tag prefixes in link_plus

`link_plus/` files still carry `link::thema{N}::…` Anki tags. That is pre-rename
legacy from commit `78f07e9` (2026-04-17, `link/` → `link_plus/` rename):
Yulia's existing Anki decks were built with `link::` tags and depend on them. A
tag migration would orphan every scheduled card in her collection. Note for
archaeology: before `78f07e9`, `link/` in git history means Yulia's materials,
not Alex's.

### 4. Edit grammar files BEFORE importing, never after

Grammar item*ids are **positional**: `scripts/fluent_import.py:157` builds
`item_id = f"{prefix}gram*{sec['num']}\_{idx}"`where`idx`is the bullet's index
under`### Voorbeelden uit oefeningen`. Inserting, deleting, or reordering
`**bold**`examples in an already-imported grammatica file makes re-import mint
new ids and orphans the learner's scheduled cards. Also never renumber
the`## N.N`H2 module numbers — they are the Link book's own numbering, consumed
by`curriculum.json`.

Sequence: edit grammatica md → THEN
`python3 scripts/fluent_import.py --course link --thema N`.

### 5. Backup-before-write for anything touching fluent-data

`~/.claude/fluent-data/` holds the learner's 6 JSON DBs. Every legitimate writer
snapshots to `.backups/` BEFORE writing. If you write to fluent-data by any path
that does not appear in this table, stop — you are off-process.

| Writer                                    | Backup dir pattern                       |
| ----------------------------------------- | ---------------------------------------- |
| `scripts/fluent_import.py` (`write_sr`)   | `pre-import-<YYYY-MM-DD-HHMMSS>/`        |
| plugin hook `update-db.py` (`backup_all`) | `pre-update-session-NNN/`                |
| plugin hook `migrate_to_fsrs.py`          | `pre-migrate-fsrs-<ISO timestamp>/`      |
| plugin hook `optimize_weights.py`         | `pre-optimize-<YYYY-MM-DD>/`             |
| plugin hook `session-end.py` (daily)      | `<YYYYMMDD>/`                            |
| plugin hook `precompact-backup.sh`        | `precompact/` (overwritten each compact) |

Incident: `a88b1ff` (2026-06-26) — the importer originally used date-only backup
names, so a second import the same day silently overwrote the first backup, and
its fixed temp filename could clobber a concurrent write. Fix: timestamped
backup dir + `.{pid}.tmp` atomic replace. Related near-miss: `350de1a` here /
`44fb945` in the fork (2026-07-04) — FSRS numeric difficulty almost overwrote
the item's `difficulty` key, which is a CEFR STRING ("A2"); it now lives in
`fsrs_difficulty`. Never write item key `difficulty` with a number.

Also protected by design: `fluent_import.py` writes ONLY
`spaced-repetition.json` and deliberately does NOT go through `update-db.py`
(that would falsely increment sessions/streak). Never "fix" this.

### 6. Never create heavyweight templated study-plan systems

Owner rule (stated 2026-07-09). Evidence — two dead plans in the repo:
`daily/maart_2026/` (6-step method, W0–W4 folder scaffolding; ~2 of ~25 days
executed, then abandoned) and `daily/april_2026/experiment_mikel.md` (commit
`e379c80`; abandoned after 2 days). Light, course-anchored workflows
(Link@Danner + Fluent sessions) are what survives. CLAUDE.md still calls the
maart plan "active" — that is documented-stale; do not build on it. New
processes must be light and anchored to the actual course.

### 7. Anki TSV discipline

`_anki.txt` files use literal TAB separators — an editor or formatter that
converts tabs corrupts every card silently (`.prettierignore` excludes them;
keep it that way). `#html:true` is REQUIRED whenever `[sound:…]` tags appear in
fields — incident `8cd356c` (2026-03-03) unified this across all Link files
after cards rendered raw markup.

## Fluent multi-repo change flow

Fluent is a forked Claude Code plugin. Three code locations + one data dir:

| Location                                       | Role                                                                                                                             |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `~/Projects/fluent`                            | dev clone of the fork — **where you edit** (origin = `aymkin/fluent`, upstream = `m98/fluent`)                                   |
| `~/.claude/plugins/marketplaces/aymkin/`       | marketplace clone — **source of truth on rebuild**, `git pull`ed daily at 09:03 by LaunchAgent `com.aymkin.claude-plugin-update` |
| `~/.claude/plugins/cache/aymkin/fluent/0.4.0/` | **the runtime** — Claude Code executes hooks and reads skills from HERE                                                          |
| `~/.claude/fluent-data/`                       | learner data (see backup table above)                                                                                            |

As of 2026-09-16 (verify live):

- The marketplace key is **`aymkin`**, not `m98`. It was `m98` until the fork
  became its own marketplace (2026-07-15, fluent commit `3c1c6b0`); the rename
  moved both the clone path and the cache path, and the plugin id is now
  `fluent@aymkin`. Anything still naming `m98` is pre-rename.

```bash
git -C ~/.claude/plugins/marketplaces/aymkin remote -v
git -C ~/.claude/plugins/marketplaces/aymkin log -1 --format='%h %ad %s' --date=short
git -C ~/Projects/fluent log -1 --format='%h %ad %s' --date=short
diff -rq ~/Projects/fluent/.claude/skills \
  ~/.claude/plugins/cache/aymkin/fluent/0.4.0/.claude/skills
```

- **Three layers, not two — and the clone is the one that wins.** The cache is
  materialized from the marketplace clone, so an edit synced fork→cache lives
  only until the next rebuild (`/plugin update`, reinstall, version bump), which
  silently restores whatever the clone holds. A fork commit that is not pushed
  is therefore a temporary edit: the session runs on it today and reverts later,
  with no error. Verified 2026-09-16 while auditing the session skills — the
  cache carried the new text while the clone still held the old.
- Change order for ANY edit under `.claude/` in the fork: edit in
  `~/Projects/fluent` → commit → **push** → `git -C …/marketplaces/aymkin pull`
  → copy the changed files into the cache → verify fork == clone == cache per
  file → only then run a Fluent session. Skipping the push or the clone pull is
  what makes the edit temporary.
- Upstream `m98` fixes are **not auto-tracked**. Merge them by hand —
  `git -C ~/Projects/fluent fetch upstream && git merge upstream/main` — then
  push.
- **Version-bump risk — this one FIRED.** The optimizer LaunchAgent
  `~/Library/LaunchAgents/com.aymkin.fluent-fsrs-optimize.plist` hardcodes the
  cache path, and still points at
  `…/cache/m98/fluent/0.3.0/.claude/hooks/ optimize_weights.py`, which no longer
  exists. The weekly run (Sunday 09:05) has failed **9 times** with
  `[Errno 2] No such file or directory`
  (`~/.claude/logs/fluent-fsrs-optimize.log`, last 2026-09-13). Impact so far is
  nil — the optimizer no-ops below 400 reviews and the history holds 17 — but it
  fails silently, so it will still be broken when the data arrives. Fix is a
  one-line plist path; any future version bump must update it in the same
  change. Related: the dependency broke once on an API change already (fork
  `133308c`, fsrs-optimizer 6.5.0) — expect it again on pip upgrades.

## The uncommitted working tree (as of 2026-07-09)

`git status --porcelain | wc -l` → 71 entries, sitting since ~2026-07-04: 61
modified, 4 deleted, 6 untracked. Composition:

- ~58 modified md files are **pure Prettier rewrap churn** (same words, new line
  breaks). Confirm per file: `git diff --word-diff <file>` — rewrap-only shows
  identical text split across lines.
- Real changes mixed in: `docs/superpowers/plans/…fsrs-scheduler.md` checkbox
  ticks (`[x]` progress marks), `link/thema_13/` PDF moves (4 × `D` at thema
  root + 4 × `??` inside `taak_N/` — an unstaged rename of binaries),
  `scripts/README.md` edits.
- Untracked: `link/thema_13/les.md` — Alex's RAW class notes **containing his
  own errors by design; never autocorrect this file** — and
  `presentatie_toets_20260702-1747.pdf` at repo root (would publish publicly if
  committed; ask the owner first).

Handling rule: **neither blanket-commit nor blanket-checkout — both lose
information.** Blanket checkout discards the plan ticks and PDF moves; blanket
commit publishes churn noise plus an unreviewed personal PDF. If the owner asks
to clean this up:

```bash
git status --porcelain                    # current census
git diff --stat                           # size of churn
git add <specific real-change paths>      # stage real changes only
# then per-file review of the remainder; commit only on explicit request
```

Stage the PDF move as a rename by adding both the deletions and the new
`taak_N/` copies in one commit. Decide the churn separately (own `chore:` commit
or discard) — never mixed with real changes.

## Provenance and maintenance

All claims verified 2026-07-09 against the working tree and live machine.
Re-verify before relying:

| Claim                              | Command                                                                                                                                                       |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pages deploys whole repo on push   | `cat .github/workflows/pages.yml`                                                                                                                             |
| /commit format + confirmation step | `cat .claude/commands/commit.md`                                                                                                                              |
| Voldemort scrub incident           | `git show 5be6931 --stat`                                                                                                                                     |
| Importer backup hardening          | `git show a88b1ff --stat`                                                                                                                                     |
| fsrs_difficulty collision          | `git show 350de1a --stat; git -C ~/Projects/fluent show 44fb945 --stat`                                                                                       |
| link/→link_plus rename             | `git show 78f07e9 --stat`                                                                                                                                     |
| html:true unification              | `git show 8cd356c --stat`                                                                                                                                     |
| Positional grammar item_id         | `grep -n 'gram_' scripts/fluent_import.py`                                                                                                                    |
| write_sr backup + atomic tmp       | `sed -n '237,246p' scripts/fluent_import.py`                                                                                                                  |
| Backup dir patterns on disk        | `ls ~/.claude/fluent-data/.backups/ \| sort -u`                                                                                                               |
| Marketplace clone remote/HEAD      | `git -C ~/.claude/plugins/marketplaces/aymkin remote -v && git -C ~/.claude/plugins/marketplaces/aymkin log -1`                                               |
| Fork↔clone↔cache drift             | `diff -rq ~/Projects/fluent/.claude ~/.claude/plugins/marketplaces/aymkin/.claude` and the same against `~/.claude/plugins/cache/aymkin/fluent/0.4.0/.claude` |
| Optimizer plist path (BROKEN)      | `plutil -p ~/Library/LaunchAgents/com.aymkin.fluent-fsrs-optimize.plist; tail -3 ~/.claude/logs/fluent-fsrs-optimize.log`                                     |
| Working-tree census (volatile)     | `git status --porcelain \| awk '{print $1}' \| sort \| uniq -c`                                                                                               |
| Test count (25, README stale)      | `python3 scripts/test_fluent_import.py`                                                                                                                       |
| One active curriculum unit         | `python3 -c "import json;print([u['id'] for u in json.load(open('link/curriculum.json'))['units'] if u['status']=='active'])"`                                |
| Dead study plans exist             | `ls daily/maart_2026 daily/april_2026; git show e379c80 --stat`                                                                                               |

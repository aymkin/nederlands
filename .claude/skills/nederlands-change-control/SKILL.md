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

| Lane              | What's in it                                                             | Gate before commit                                                                                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **content**       | `link/`, `link_plus/`, `de_opmaat/`, `other/`, `daily/` md + `_anki.txt` | Voldemort grep (below); Anki TSV format check (literal TABs, `#html:true` with `[sound:]`); no renames of existing files; Prettier on md only                                                       |
| **scripts**       | `scripts/*.py`                                                           | `python3 scripts/test_fluent_import.py` → expect **25 passed**; touching `grammatica_fluent.py` or the rule extracts also needs `python3 scripts/test_grammatica_fluent.py` → expect **всё зелено** |
| **fluent-plugin** | fork `~/Projects/fluent`                                                 | NOT this repo — edit the fork, then release (Fluent change flow below); every release rebuilds the cache from the fork                                                                              |
| **docs**          | `docs/superpowers/`, `CLAUDE.md`, READMEs, `.claude/skills/`             | 80-col proseWrap; where CLAUDE.md is documented-stale, correct it or note it — never propagate the stale claim                                                                                      |
| **config**        | `curriculum.json`, `.prettierrc`, `package.json`, `pages.yml`            | curriculum.json: exactly ONE unit `status: "active"` (importer raises ValueError otherwise); pages.yml changes alter public exposure — owner sign-off                                               |

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
git grep -inE 'rusland|росси' -- \
  link link_plus de_opmaat daily other frequentie werk grammatica
```

Expect zero output. Two things the command's shape carries:

- **Content directories, not the whole repo.** The skills documenting this rule
  spell the words out on purpose; a repo-wide `-- '*.md' '*.txt'` returned 16
  such hits on 2026-09-24, and a gate that is always red is a gate nobody reads.
  Extend the list when a content directory appears.
- **`git grep`, not `grep -r`** — tracked and staged content only, so gitignored
  `private/` stays out without an exclude flag, and a brand-new file is covered
  once you `git add` it.

(`-i` matches Cyrillic case on macOS grep/git-grep — verified 2026-07-09.)
Incident: commit `5be6931` (2026-04-21) had to scrub country-of-origin
references from 8 already-published files.

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

Grammar item ids are **positional**: `scripts/fluent_import.py:157` builds
`item_id = f"{prefix}gram_{sec['num']}_{idx}"`, where `idx` is the bullet's
index under `### Voorbeelden uit oefeningen`. Inserting, deleting, or reordering
`**bold**` examples in an already-imported grammatica file makes re-import mint
new ids and orphans the learner's scheduled cards. Also never renumber the
`## N.N` H2 module numbers — they are the Link book's own numbering, consumed by
`curriculum.json`.

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

### 8. Formatter vs machine-read markdown: diff the parser's output

A file diff cannot tell table alignment from data loss. When a formatter or a
mass-edit touches markdown that a script parses, run that parser over both
versions and compare its **output** — the only diff that shows the damage.

Incident 2026-09-21: `pnpm run format` over `grammatica/regels/` truncated 58
fields across 34 rules. `proseWrap:always` moved `**По-русски:**` mid-line while
`grammatica_fluent.py` captured fields with `^…$`, so seven rules lost their
Russian gloss outright — and silently: no exception, exit 0, "34 правил
разобрано", half-rules bound for the learner's deck.

Which remedy applies depends on whether the format is yours to change:

| Format                          | Remedy            | Why                            |
| ------------------------------- | ----------------- | ------------------------------ |
| `_anki.txt` — literal TABs (§7) | `.prettierignore` | Anki's import format, not ours |
| `**/les.md` — hand-made columns | `.prettierignore` | the layout IS the content      |
| `grammatica/regels/` — prose    | fix the parser    | prose has no layout to protect |

`grammatica/regels/` left `.prettierignore` once the parser read each field to
the next label instead of to end of line. `scripts/test_grammatica_fluent.py`
pins the property: every field of every rule identical when the source is
rewrapped at 60, 80, 120 and one-line widths.

## Fluent change flow: fork, then release

Fluent is a forked Claude Code plugin. Two code locations + one data dir:

| Location                                           | Role                                                                                                                      |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `~/Projects/fluent`                                | the fork — **where you edit** — and the marketplace `aymkin` itself (origin = `aymkin/fluent`, upstream = `m98/fluent`)   |
| `~/.claude/plugins/cache/aymkin/fluent/<version>/` | **the runtime** — Claude Code executes hooks and reads skills from HERE; one directory per release, old ones stay on disk |
| `~/.claude/fluent-data/`                           | learner data (see backup table above)                                                                                     |

A change reaches the runtime only through a **release** (the fork's
`tasks/lessons.md`, entry 2026-10-06; release commits `9120373`, `3ffc74d`):

1. Edit, test and commit in `~/Projects/fluent`.
2. Bump the version in all three fields — `version` in
   `.claude-plugin/plugin.json`, both `metadata.version` and
   `plugins[0].version` in `.claude-plugin/marketplace.json` — and cut
   `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] — YYYY-MM-DD`.
3. Commit that as `chore(release): X.Y.Z` and leave the tree clean:
   `git -C ~/Projects/fluent status --short` prints nothing. The update copies
   the working directory, untracked files included (the 0.7.1 cache holds the
   fork's git-excluded `.claude/worktrees/` and `.devvenv/`), so an uncommitted
   edit would ship under the release commit's sha.
4. `claude plugin update fluent@aymkin --scope user` builds
   `cache/aymkin/fluent/X.Y.Z/` from the fork directory.
5. The owner restarts the app; the update applies only after a restart.
6. Run every behaviour gate twice: against the fork and against the new cache
   directory.

Push is not part of a release — the marketplace is the local directory — and,
like every push, waits for the owner's explicit yes.

Verify live (verified 2026-10-08):

```bash
jq '.aymkin.source' ~/.claude/plugins/known_marketplaces.json  # directory: ~/Projects/fluent
jq -r '.plugins["fluent@aymkin"][0] | .version, .gitCommitSha' \
  ~/.claude/plugins/installed_plugins.json
git -C ~/Projects/fluent rev-parse HEAD  # equals gitCommitSha once released
FLUENT=$(ls -d ~/.claude/plugins/cache/*/fluent/*/ | sort -V | tail -1)
diff -rq -x worktrees -x __pycache__ ~/Projects/fluent/.claude "${FLUENT}.claude"
# expected: no output
```

- **Edit the fork, never the cache.** Every release rebuilds the cache from the
  fork, so a cache edit is silently lost. There is no marketplace clone any more
  — `~/.claude/plugins/marketplaces/aymkin/` does not exist — and the daily
  09:03 job `com.aymkin.claude-plugin-update` pulls only git clones under
  `~/.claude/plugins/marketplaces/` and `~/.claude/skills/`, so nothing updates
  Fluent on its own.
- The marketplace key is **`aymkin`**; it was `m98` until the fork became its
  own marketplace (2026-07-15, fluent commit `3c1c6b0`). The plugin id is
  `fluent@aymkin`. Outside history, anything naming `m98` as a marketplace is
  pre-rename.
- Upstream `m98` fixes are **not auto-tracked**. Merge them by hand —
  `git -C ~/Projects/fluent fetch upstream && git merge upstream/main` — then
  release.
- **Two rules the optimizer zombie produced** (the incident itself is
  `nederlands-failure-archaeology` 12 — a weekly LaunchAgent that failed nine
  Sundays into a log nobody read):
  - Before deleting code "nothing calls", search the **machine** as well as the
    repo — `launchctl list`, `~/Library/LaunchAgents`, crontab. The deletion
    commit that started it claimed "no hook, no cron, no skill", which was true
    of the repository and false of the machine.
  - Anything that points into `~/.claude/plugins/cache/` — a plist, a script, a
    skill — must resolve the path, never name it. Old version directories stay
    on disk, so a named version runs old code without an error: on 2026-10-08,
    22 skill lines still named `0.4.0` while 0.7.1 was live.

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

| Claim                              | Command                                                                                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Pages deploys whole repo on push   | `cat .github/workflows/pages.yml`                                                                                                   |
| /commit format + confirmation step | `cat .claude/commands/commit.md`                                                                                                    |
| Voldemort scrub incident           | `git show 5be6931 --stat`                                                                                                           |
| Importer backup hardening          | `git show a88b1ff --stat`                                                                                                           |
| fsrs_difficulty collision          | `git show 350de1a --stat; git -C ~/Projects/fluent show 44fb945 --stat`                                                             |
| link/→link_plus rename             | `git show 78f07e9 --stat`                                                                                                           |
| html:true unification              | `git show 8cd356c --stat`                                                                                                           |
| Positional grammar item_id         | `grep -n 'gram_' scripts/fluent_import.py`                                                                                          |
| write_sr backup + atomic tmp       | `sed -n '237,246p' scripts/fluent_import.py`                                                                                        |
| Backup dir patterns on disk        | `ls ~/.claude/fluent-data/.backups/ \| sort -u`                                                                                     |
| Fluent topology + release state    | the `bash` block in "Fluent change flow" above                                                                                      |
| Optimizer job stays retired        | `launchctl list \| grep fluent-fsrs` — expect no output; `ls -a ~/Library/LaunchAgents \| grep fsrs` shows only the renamed backups |
| Working-tree census (volatile)     | `git status --porcelain \| awk '{print $1}' \| sort \| uniq -c`                                                                     |
| Test count (25, README stale)      | `python3 scripts/test_fluent_import.py`                                                                                             |
| One active curriculum unit         | `python3 -c "import json;print([u['id'] for u in json.load(open('link/curriculum.json'))['units'] if u['status']=='active'])"`      |
| Dead study plans exist             | `ls daily/maart_2026 daily/april_2026; git show e379c80 --stat`                                                                     |

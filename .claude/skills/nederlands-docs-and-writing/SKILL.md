---
name: nederlands-docs-and-writing
description:
  Use when editing or creating docs or markdown content in the nederlands repo —
  updating CLAUDE.md, writing specs/plans under docs/superpowers, fixing
  scripts/README.md, authoring grammatica_*/verhaal_*/woordenlijst files or
  les.md notes, deciding whether to run Prettier / pnpm run format, choosing doc
  language (Russian vs Dutch vs English), or when CLAUDE.md contradicts disk
  (maart_2026 "active", link taak dirs, anki format rows) or format:check exits
  1.
---

# nederlands — docs of record, house styles, writing discipline

**When NOT to use this skill:** for GENERATING new Anki cards or verhalen, use
the repo commands `/anki-cards` and `/verhaal`
(`.claude/commands/anki-cards.md`, `.claude/commands/verhaal.md`) — they own the
content-generation rules (vocab recycling, level flags, style anti-patterns).
This skill covers the FORMATS those commands emit and the docs around them. For
whether an edit is _allowed_ at all, see `nederlands-change-control`. For why
formats are load-bearing (cloze ids, TSV corruption), see
`nederlands-architecture-contract`.

## 1. The docs of record (hierarchy)

| Doc                           | Role                                         | Language    | Trust                                    |
| ----------------------------- | -------------------------------------------- | ----------- | ---------------------------------------- |
| `CLAUDE.md` (repo root)       | Primary agent instructions                   | English     | Mostly good; KNOWN drift list below      |
| `docs/superpowers/specs/`     | Design-of-record for engineering work        | Mixed RU/EN | Authoritative for design intent          |
| `docs/superpowers/plans/`     | Implementation plans (checkbox tasks)        | Mixed RU/EN | Authoritative; checkboxes track progress |
| `scripts/README.md`           | Script manual                                | Russian     | Partially STALE (see §3)                 |
| `link/fluent_handleiding.md`  | Learner-facing Fluent+Link manual            | Russian     | Good                                     |
| `README.md` (root)            | Joke stub ("Make learnigng Dutch not AI 😂") | —           | Not a doc; ignore, don't "fix"           |
| `.claude/skills/nederlands-*` | This library                                 | English     | Self-contained by design                 |

Project memory exists at
`~/.claude/projects/-Users-Alex-Naymkin-Projects-nederlands/memory/` (24 files,
verified 2026-07-10), but it is user-machine-specific. Skills and repo docs must
be SELF-CONTAINED — never write "see memory/…" as a load-bearing reference in a
doc.

## 2. CLAUDE.md known drift list (verified against disk 2026-07-10)

CLAUDE.md is the primary doc but these four claims are stale. When they matter,
state "CLAUDE.md says X; disk reality is Y":

1. **maart_2026 study plan "active".** CLAUDE.md: "The active study plan uses
   the Evgeniy 6-step method". Reality: abandoned after ~2 executed days; last
   commit touching `daily/maart_2026/` is 04f6ca4 (2026-04-10). The real loop is
   Link@Danner + Fluent reviews.
2. **`link/` directory pattern.** CLAUDE.md: `thema_N/{N}_{task_name}/`.
   Reality: `link/thema_N/taak_1..4/` (plain `taak_N`, e.g.
   `link/thema_8/taak_1/`). The `{N}_{task_name}` pattern exists only in
   `link_plus/thema_1/` (e.g. `4_welkom_nieuwe_buurvrouw/`). Do NOT normalize
   either — public Pages links and importer globs depend on paths.
3. **"Vocabulary with audio" Anki format row**
   (`Dutch | Russian | Notes | Audio | Tags`, `#tags column:5`) matches NO file
   on disk. Actual de*opmaat `#tags column:5` files (thema 8–9
   `woordenlijst_pagina*\*`) use the Link 5-col header `#columns:Word Example
   Translation TranslationExample
   Tags`with tags like`opmaat::thema8::pagina22::A2`.
4. **Prettier ignore list incomplete.** CLAUDE.md lists `_anki.txt`, `*.pdf`,
   `*.mp3`, `*.docx`. Actual `.prettierignore` also has `node_modules/`,
   `**/verhaal_*.md`, `*_reader.html`.

**Routing:** fix CLAUDE.md drift via the `/update-docs` command
(`.claude/commands/update-docs.md` — "review folder structure, update CLAUDE.md,
keep concise"), and treat the edit as a change-controlled doc change (commit
separately from content churn; see `nederlands-change-control`).

## 3. scripts/README.md — stale items (verified 2026-07-10)

Russian-language manual, ~mostly accurate, EXCEPT:

| Claim in README                          | Disk reality                                            | Verify                                      |
| ---------------------------------------- | ------------------------------------------------------- | ------------------------------------------- |
| line 539: tests → "21 passed"            | `python3 scripts/test_fluent_import.py` → **25 passed** | run it                                      |
| line 381: Whisper model at "строка ~104" | `"base"` is at `scripts/audio_to_anki.py:51`            | `grep -n '"base"' scripts/audio_to_anki.py` |

Do NOT "fix" the tests to match the README; fix the README. Also stale
repo-wide: `package.json` `name` still says `de_opmaat` — its URLs are
untrustworthy.

## 4. Engineering docs: docs/superpowers spec→plan flow

Naming: `YYYY-MM-DD-<slug>-design.md` in `specs/`, `YYYY-MM-DD-<slug>.md` in
`plans/`. The flow (spec approved → plan written → plan executed task-by-task
with `- [ ]` checkboxes) has been used twice:

1. `2026-06-26-fluent-curriculum-bridge` (spec + plan, mostly Russian) → shipped
   as `scripts/fluent_import.py`.
2. `2026-07-03-fluent-fsrs-scheduler` (spec + plan, English) → shipped as the
   FSRS-6 migration in the Fluent fork (live 2026-07-04).

For new engineering work: write the spec first, get it approved, then the plan,
then implement. Tick plan checkboxes as tasks complete (checkbox ticks are
legitimate doc edits, not churn). New engineering docs: write in English (the
2026-07 cycle set that precedent; earlier ones are Russian).

## 5. House styles (with exemplar paths — read the exemplar before writing)

### 5.1 grammatica\_\*.md — EDITING IS CHANGE-CONTROL

Exemplar: `link/thema_8/grammatica_thema08_in_mijn_buurt.md`. Structure:

- H1: `# Thema {N}: {Title} — Grammatica`
- H2: `## {book-module-number} {Title}` — numbers like `2.11`, `3.7` are the
  Link book's OWN module numbers, NOT sequential. `link/curriculum.json`
  references them. **Never renumber.**
- Per module: `### Regel …` → table → `### Voorbeelden uit oefeningen` with
  bullet examples containing `**bold**` fragments.
- Written in Dutch.

**Why editing is dangerous:** `scripts/fluent_import.py` turns each bold example
bullet into a cloze card with a POSITIONAL item_id (`link_t12_gram_3.8_10` =
module 3.8, bullet index 10). Inserting, deleting, or reordering bullets AFTER
import orphans existing cards and mints duplicates. Edit grammatica files BEFORE
importing a thema; after import, appending at the end of a module's bullet list
is the only safe shape, and even that should go through
`nederlands-change-control`.

### 5.2 Verhaal (practice story) format

Exemplar: `daily/verhalen/verhaal_2026-04-14_twee_dagen_van_alexander.md`.

- **ALL verbs bolded** (`Ik **wacht** op de trein.`) — pattern recognition.
- **One sentence per line** with blank lines between — TTS scripts
  (`text_to_speech.py`, `story_reader.py`) parse sentence-per-line; wrapped
  prose breaks alignment (incident 51c5ba6).
- Ends with `## Woordenlijst — extra woorden`: a 3-col table
  `| Nederlands | Русский | English |` for words not in the course lists.
- Telegram variants (`*_telegram.md`, e.g.
  `link_plus/thema_1/verhaal_kennismaken_telegram.md`): same story reformatted
  for mobile — emoji markers, `➖` dividers, short `Deel N` chunks. Separate
  file, never the canonical copy.
- Generation rules (level, recycling, flags) live in `/verhaal` — don't restate
  them here or in new docs.

### 5.3 nieuw_in_rotterdam "uitgebreid" format — bold means VOCAB here

Exemplar: `other/nieuw_in_rotterdam/hoofdstuk_01_uitgebreid.md`. Free A1→A2
rewrites of the _Nieuw in Rotterdam_ book chapters. Header blockquote declares:
`**Vet** = belangrijke woorden voor de woordenlijst`. So in this family **bold =
vocabulary words**, NOT verbs, and text is normal wrapped prose (not
sentence-per-line). Two bolding conventions exist in this repo — never mix them:
verhaal\_\* bolds verbs; uitgebreid bolds vocab.

### 5.4 woordenlijst.md (per-taak vocab doc, distinct from \*\_anki.txt)

Exemplar: `link/thema_8/taak_1/woordenlijst.md`. Structure:

- H1: `# Woordenlijst — thema {N} · taak {K}: {Taak title}`
- Source-citation blockquote: `> Извлечено из \`{file}.pdf\` (LINK … © Boom
  uitgevers Amsterdam, 2019)` — keep the citation; it is the provenance of
  copyrighted course material.
- A short Russian context paragraph, then `## Woorden (N)` with a 2-col table
  `| Woord | Vertaling |` (Dutch word with article → Russian gloss, usage notes
  inline in the gloss).

### 5.5 les.md — learner's RAW class notes. NEVER autocorrect.

Exemplar: `link/thema_13/les.md` (untracked as of 2026-07-10). These are Alex's
verbatim in-class notes and contain HIS OWN ERRORS ("Tegenwoodig", "Verladen
tijd", "sportschoool", "Standart"). The errors are the data — they feed
error-pattern analysis. Do not fix spelling, do not Prettier-wrap, do not "clean
up". Treat as read-only capture.

## 6. Prettier discipline

Config (`.prettierrc`, verified 2026-07-10): `proseWrap: always`,
`printWidth: 80`, `tabWidth: 2`, `useTabs: false`; override
`daily/verhalen/**/*.md` → `proseWrap: never` (belt) on top of
`.prettierignore`'s `**/verhaal_*.md` (suspenders) — verhaal sentence-per-line
semantics must survive.

`.prettierignore`: `node_modules/`, `*.pdf`, `*.mp3`, `*.docx`, `*_anki.txt`,
`**/verhaal_*.md`, `*_reader.html`.

**Never format:**

- `*_anki.txt` — literal TABs are field separators; any tab→space conversion
  silently corrupts decks (already covered by ignore, but don't bypass it with
  editor formatters either).
- `verhaal_*.md` — line = sentence = TTS/highlight unit.
- `les.md` raw notes (NOT in `.prettierignore` — rely on discipline).

**Format everything else** at 80 cols, including these skill files.

**Commands and their traps** (`package.json` scripts, verified):

- `pnpm run format:check` — read-only, but as of 2026-07-10 it exits 1 on ~18
  files, mostly UNTRACKED scratch (`.superpowers/sdd/*.md`,
  `link/thema_13/les.md`). Do not trust the bare exit code; scope to the files
  you touched: `pnpm exec prettier --check <paths>`.
- `pnpm run format` — writes ALL `**/*.md`, tracked and untracked. Running it
  blanket rewraps untracked raw notes and generates the tree-wide churn
  documented in `nederlands-change-control`. Prefer
  `pnpm exec prettier --write <paths-you-edited>`.

## 7. Language policy

| Audience / artifact                                                 | Language                                                                                      |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Learner-facing prose (woordenlijst glosses, manuals, context notes) | Russian (base language)                                                                       |
| Grammar terminology inside explanations                             | Dutch terms (voltooid deelwoord, lidwoord, inversie…) with a brief Russian gloss on first use |
| Course content itself (grammatica files, verhalen, dialogs)         | Dutch                                                                                         |
| Engineering docs (new specs/plans, this skill library, commits)     | English                                                                                       |

The words «Россия»/"Rusland" must never appear in any content (Voldemort rule,
commit 5be6931) — grep before committing:

```bash
grep -rniE 'rusland|россия' link link_plus de_opmaat daily other \
  --include='*.md'
```

## 8. Doc-change checklist

1. Is it CLAUDE.md? → route through `/update-docs`, keep it concise, fix the §2
   drift items while you're there if they still hold.
2. Is it a grammatica file for an already-imported thema? → STOP, read §5.1 and
   `nederlands-change-control` first.
3. Does the file family have an exemplar in §5? → open the exemplar, match it
   exactly.
4. Prettier: format only the files you touched; never the §6 never-list.
5. Voldemort grep before commit.
6. Commit doc fixes separately from content/churn (message style: `/commit`
   command; no attribution footers).

## Provenance and maintenance

All claims verified 2026-07-10 against the working tree. Re-verify before
trusting:

- CLAUDE.md drift items:
  `grep -n "active study plan\|{N}_{task_name}\|Vocabulary with audio" CLAUDE.md`
  vs `ls link/thema_8/` and
  `head -4 de_opmaat/thema_8/woordenlijst_pagina_22_anki.txt`
- maart_2026 dead:
  `git log -1 --format='%h %ad' --date=short -- daily/maart_2026/` (→ 04f6ca4
  2026-04-10)
- Test count: `python3 scripts/test_fluent_import.py` (→ 25 passed) vs
  `grep -n "passed" scripts/README.md`
- Whisper model line: `grep -n '"base"' scripts/audio_to_anki.py` (→ :51)
- Prettier config: `cat .prettierrc .prettierignore`
- format:check state: `pnpm run format:check` (fails on untracked scratch as of
  2026-07-10; recheck the file list)
- Spec/plan inventory: `ls docs/superpowers/specs docs/superpowers/plans`
- Grammatica exemplar shape:
  `head -30 link/thema_8/grammatica_thema08_in_mijn_buurt.md`
- les.md rawness: `head -10 link/thema_13/les.md` (untracked; may be committed
  later)
- Commands referenced: `ls .claude/commands/` (anki-cards, commit, update-docs,
  verhaal)

---
name: nederlands-external-positioning
description:
  Use when anything touches the project's public face — committing or adding
  files (they auto-publish to GitHub Pages), asking what is publicly visible,
  copyright/privacy questions about published PDFs/mp3s/book text,
  aymkin.github.io/nederlands URLs, read.html ?f= links breaking, the
  aymkin/fluent fork's visibility, or before stating externally that anything
  was "achieved" (FSRS-6, personal weights, Parkiet, importer) — what may be
  claimed vs what is open/unproven.
---

# External positioning: what is public, and what may be claimed

This skill covers the project's public face: the GitHub Pages deploy pipeline,
the honest exposure surface, copyright/privacy posture, the `read.html` reader,
repo visibility, and the standards for any claim made outside this repo.

**When NOT to use this skill:** gating an internal change (commit, rename,
reformat, delete) is `nederlands-change-control`. This skill tells you what
publishing means; that one tells you whether and how to make the change.

## 1. The deploy pipeline: every push to main publishes everything

`.github/workflows/pages.yml` is the ONLY CI workflow in this repo. Verified
verbatim 2026-07-10, it does exactly this on every push to `main`:

1. `actions/checkout@v4`
2. `rm -f "other/nieuw_in_rotterdam"/*.epub "other/nieuw_in_rotterdam"/*.pdf`
   (sole exclusion — the copyrighted book _binaries_)
3. `actions/upload-pages-artifact@v3` with `path: .` — **the entire repo**
4. `actions/deploy-pages@v4`

Published site: <https://aymkin.github.io/nederlands/> (Pages
`build_type: workflow`, confirmed live via
`gh api repos/aymkin/nederlands/pages`).

Consequences you must internalize:

- **"Add file" = "publish file."** There is no staging, no review, no allowlist.
  Anything committed to `main` is on the public internet within minutes.
- Script outputs land next to their inputs (e.g. `audio_to_anki.py` writes
  mp3s/TSVs beside the source mp3) — committing them publishes them.
- `.gitignore` is the only pre-commit filter and it excludes almost nothing
  content-wise (`.DS_Store`, `node_modules`, `__pycache__`, `.pnp.cjs`,
  `.yarn/`, `music/` — verified 2026-07-10).
- Removing a file from `main` later does NOT unpublish its git history: the repo
  itself is public (see §4), so old blobs stay fetchable via clones and the
  GitHub API. True removal requires history rewrite — a
  `nederlands-change-control` matter, owner decision required.

## 2. The exposure surface, honestly (verified live 2026-07-10)

Every row below was confirmed with `git ls-files` counts AND a live
`curl -s -o /dev/null -w '%{http_code}'` against the published site.

| What                                          | Count | Live check (2026-07-10) |
| --------------------------------------------- | ----- | ----------------------- |
| _Nieuw in Rotterdam_ full book text (md in    | 36    | 200 (publishes!)        |
| `other/nieuw_in_rotterdam/origineel/`)        |       |                         |
| Same book's `.epub`/`.pdf` (tracked in git)   | 2     | 404 (the one exclusion) |
| Tracked PDFs total                            | 65    | —                       |
| — incl. Alex's GRADED test results            | 2     | 200                     |
| (`beoordeling_toets_de_opmaat_t1/t3.pdf`)     |       |                         |
| — incl. phone scans of the commercial Link    | ~40   | —                       |
| course book (`link*/thema_N/taak_N/10000…`)   |       |                         |
| — incl. a personal bank-payment receipt       | 1     | —                       |
| (`other/bank payment - boom nt2 naar a2.pdf`) |       |                         |
| `work_daily/` employer standup/refinement     | 6     | 200 — real transcripts  |
| transcripts                                   |       | with colleague names    |
| Tracked mp3s total                            | 96    | —                       |
| — incl. Parkiet TTS test artifacts            | 52+1  | 200                     |
| (`parkiet_test_audio/` + root output)         |       |                         |

Notes:

- The epub/pdf exclusion protects only the book _binaries_. The book's complete
  text lives as 36 tracked markdown files in `origineel/` and publishes anyway.
  The exclusion is cosmetic relative to the actual copyright exposure.
- The `1000050xxx.pdf` files are photographed pages of the Link course book
  (commercial NT2 textbook, nt2.nl). The exclusion commit ecda869 itself labels
  the Rotterdam book "copyrighted" — the same reasoning was never applied to
  these scans or the book text.
- `work_daily/` transcripts name real colleagues (e.g. the 2026-03-30 standup
  names participants) at Alex's employer.
- The repo has **no LICENSE file** (`git ls-files 'LICENSE*'` is empty), so
  default all-rights-reserved applies to original content, while the third-party
  © material carries its owners' rights regardless.

**Policy status: OPEN.** As of 2026-07-10 the owner has not prioritized an
exposure policy. Do not silently delete or rewrite history to "fix" this — that
is an owner decision routed through `nederlands-change-control`. Your
obligations meanwhile: (a) never ADD new sensitive/copyrighted material, (b)
flag exposure when you touch adjacent files, (c) treat every commit as a
publication decision.

## 3. read.html — the public markdown reader

`read.html` at the repo root is a client-side markdown reader, verified against
source 2026-07-10:

- URL shape: `https://aymkin.github.io/nederlands/read.html?f=<path>.md`
  (`?file=` also accepted).
- Rejects paths containing `..`, starting with `/`, or matching `^https?:` —
  same-origin repo files only.
- Renders with `marked@13.0.2` loaded from `cdn.jsdelivr.net` — **the project's
  single external runtime dependency**. If jsdelivr is down or blocked, every
  reader link shows only "Document laden…". Keep this in mind before blaming
  repo content for a "broken" reader.
- Sets the page title from the first `# h1`; injects a TOC when a document has
  ≥3 `## h2` headings.
- Because links encode file paths, **renaming any tracked md file breaks public
  reader URLs** — including the load-bearing typo'd filenames (`opdrach_3.md`,
  `woordenlijst_page_…`). Never "fix" filename typos without
  `nederlands-change-control`.

## 4. Repo visibility (verified 2026-07-10 via `gh repo view`)

| Repo                | Visibility | Contents                           |
| ------------------- | ---------- | ---------------------------------- |
| `aymkin/nederlands` | PUBLIC     | everything in §2, full git history |
| `aymkin/fluent`     | PUBLIC     | plugin code fork, 61 tracked files |

The Fluent fork was spot-checked 2026-07-10: it tracks code, hooks, and
`data-examples/*-template.json` templates only — **no learner data** (learner
DBs live in `~/.claude/fluent-data/`, outside any repo). Its tracked
`.claude/settings.local.json` holds harmless permission entries. Keep it that
way: never commit anything from `fluent-data/` (real review history, error
patterns, session logs are personal data) into the fork.

## 5. Claim standards: achieved vs open

No marketing language, anywhere. Before stating anything externally (README,
fork description, blog-style writeup, conversation with the course school),
classify it:

### May be stated as achieved (evidence exists, re-verified 2026-07-10)

| Claim                                                                   | Evidence + re-verify command                                                                                                                                                                                                                                          |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FSRS-6 scheduler is live (since 2026-07-04)                             | `python3 -c "import json;print(json.load(open('$HOME/.claude/fluent-data/spaced-repetition.json'))['metadata'])"` → `scheduler: fsrs-6`, `algorithm: FSRS-6` (algorithm key stamped by fork commit 4205bf1 on 2026-07-09; before that a stale `SM-2` string lingered) |
| The stdlib FSRS port is numerically cross-checked against py-fsrs 6.3.1 | `~/Projects/fluent/.devvenv/bin/python ~/Projects/fluent/tests/test_fsrs_crosscheck.py` — ran 2026-07-10: `OK`. Skips (does not pass) if py-fsrs is absent — an `OK` from a skip is not evidence; check for the skip message.                                         |
| Importer test suite passes: 25 tests                                    | `python3 scripts/test_fluent_import.py` → "25 passed" (scripts/README.md says 21 — stale; do not quote docs, run the suite)                                                                                                                                           |

### Open / candidate — UNPROVEN, must not be claimed as achieved

| Claim someone will be tempted to make                    | Actual status (2026-07-10)                                                                                                                                                                                                                                                                                                                                       |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Personal FSRS weights beat defaults"                    | `metadata.weights: null` — DEFAULT_W in use. The weekly optimizer has NEVER activated: log shows `insufficient data (185/400, +185 new) — no-op` (guard: ≥400 total reviews AND ≥50 new; per-item total was 225 on 2026-07-10). Even after activation, "beats defaults" requires an evaluation (e.g. log-loss/calibration vs DEFAULT_W) that does not exist yet. |
| "Parkiet multi-voice TTS works well"                     | Experiment PAUSED since 2026-04-17 (commit 1a6d78a). 52 test mp3s are published but no quality evaluation was ever recorded. Owner explicitly did NOT choose this as a research direction.                                                                                                                                                                       |
| "Content is generated within a comprehensibility budget" | Chosen research direction, nothing built or measured. See `nederlands-research-frontier`.                                                                                                                                                                                                                                                                        |
| "Closed-loop tutoring improves toets results"            | Chosen research direction; the metric (real toets results) has no baseline pipeline yet. See `nederlands-research-frontier`.                                                                                                                                                                                                                                     |

### The reproducibility bar

Any claim made outside this repo must ship all three:

1. **Commands** — exact, copy-pasteable, the ones a stranger runs to see the
   same thing.
2. **Data/state** — what the commands ran against (item counts, review totals,
   file versions), since this project's numbers are volatile.
3. **Date** — when it was true. "225 reviews" without "on 2026-07-10" is already
   a broken claim a week later.

This is the same pattern this skill library uses internally
(`nederlands-validation-and-qa` defines what counts as evidence; this section
applies it to external statements).

## Provenance and maintenance

All facts above verified 2026-07-10. Re-verify before relying on any of them:

- Workflow is unchanged and still the only one:
  `cat .github/workflows/pages.yml && ls .github/workflows/`
- Site still serves / exclusion still holds:
  `curl -s -o /dev/null -w '%{http_code}\n' https://aymkin.github.io/nederlands/read.html`
  and the same for
  `other/nieuw_in_rotterdam/Nieuw%20in%20Rotterdam%20-%20Eboek.pdf` (expect 200
  then 404)
- Exposure counts: `git ls-files '*.pdf' | wc -l` (65),
  `git ls-files '*.mp3' | wc -l` (96),
  `git ls-files 'other/nieuw_in_rotterdam/origineel/*.md' | wc -l` (36),
  `git ls-files | grep -c work_daily/` (6), `git ls-files | grep beoordeling` (2
  graded toets PDFs)
- Repo visibility: `gh repo view aymkin/nederlands --json visibility` and
  `gh repo view aymkin/fluent --json visibility` (both PUBLIC)
- No license: `git ls-files 'LICENSE*'` (empty)
- Scheduler/weights state: the python one-liner in §5 (expect
  `scheduler: fsrs-6`, `weights: None`)
- Optimizer still dormant: `tail -3 ~/.claude/logs/fluent-fsrs-optimize.log`
- Crosscheck gate: the `.devvenv` command in §5 (expect `OK`, not a skip)
- Reader CDN pin: `grep jsdelivr read.html` (marked@13.0.2)

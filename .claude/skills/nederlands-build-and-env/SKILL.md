---
name: nederlands-build-and-env
description:
  Use when setting up this project on a new Mac or when a tool is missing or
  broken — "ModuleNotFoundError: No module named 'whisper'", edge-tts not
  found, ffmpeg missing, pnpm/prettier install fails, recreating scripts/.venv
  or ~/.claude/fluent-data/.venv-optimizer, Anki profile or media-path
  questions, Fluent plugin marketplace/cache remotes, LaunchAgent plists not
  firing, or when hunting for a requirements.txt (none exists — this skill IS
  the dependency record).
---

# nederlands — build & environment from scratch

Recreate the full working environment for the `nederlands` repo and its
Fluent-plugin ecosystem on a fresh Mac, plus the traps that make naive setup
fail. All versions/paths verified live on 2026-07-09 — treat them as the
known-good baseline, not eternal truth.

**When NOT to use this skill:** for _running_ the importer, TTS scripts,
sessions, or restoring backups, use `nederlands-run-and-operate`. For tunable
settings and live config values, use `nederlands-config-and-flags`. For "which
environment broke and why", start at `nederlands-debugging-playbook`.

## The one rule that prevents most breakage

**There is NO requirements.txt, pyproject.toml, or lockfile for Python anywhere
in this repo.** The catalog below is the only dependency record. Do not
"helpfully" create one without checking `nederlands-change-control` first, and
do not pip-install packages into environments the table says don't own them —
the separation is deliberate.

## Environment catalog (as of 2026-07-09)

| Component         | Version                                        | Install method                            | Location                                       |
| ----------------- | ---------------------------------------------- | ----------------------------------------- | ---------------------------------------------- |
| python3 (default) | 3.14.5                                         | `brew install python@3.14`                | `/opt/homebrew/bin/python3`                    |
| python3.11        | 3.11.15                                        | `brew install python@3.11`                | `/opt/homebrew/opt/python@3.11/bin/python3.11` |
| ffmpeg            | 8.1.1                                          | `brew install ffmpeg`                     | `/opt/homebrew/bin/ffmpeg`                     |
| edge-tts          | 7.2.7                                          | pip into Homebrew python (module + CLI)   | `/opt/homebrew/bin/edge-tts`                   |
| openai-whisper    | 20250625                                       | **pipx ONLY** (CLI, no importable module) | `~/.local/bin/whisper`                         |
| node              | v20.17.0                                       | nvm                                       | `~/.nvm/versions/node/v20.17.0/`               |
| pnpm              | 10.29.2                                        | corepack (ships with node)                | symlink in nvm bin dir                         |
| prettier          | 3.8.1 (spec `^3.7.4`)                          | `pnpm install` in repo                    | `node_modules/.bin/prettier`                   |
| scripts/.venv     | py 3.14.5, torch 2.11.0, transformers 5.5.4    | manual venv                               | repo `scripts/.venv/` — **Parkiet only**       |
| .venv-optimizer   | py 3.11.15, FSRS-Optimizer 6.5.0, torch 2.12.1 | manual venv                               | `~/.claude/fluent-data/.venv-optimizer/`       |
| Anki desktop      | profiles `alex`, `iuliia`                      | app install                               | `~/Library/Application Support/Anki2/`         |

Repo scripts (`fluent_import.py`, `build_vocab_index.py`, `anki_utils.py`, test
suite) are **stdlib-only** and run on plain Homebrew python3. The only pip
package the repo scripts import is `edge_tts` (used by `text_to_speech.py` and
`story_reader.py`).

## Step 1 — clone + JS toolchain

```bash
git clone git@github.com:aymkin/nederlands.git ~/Projects/nederlands
cd ~/Projects/nederlands
pnpm install   # installs prettier only — the sole JS dependency
```

Traps:

- `package.json` is **stale**: `name` is `de_opmaat` and its repository/bugs
  /homepage URLs point at `aymkin/de_opmaat`. The real remote is
  `git@github.com:aymkin/nederlands.git`. Trust `git remote -v`, never the
  package.json URLs. Do not fix without change control.
- pnpm comes via corepack under nvm's node v20.17.0. If `pnpm` is missing:
  install nvm, `nvm install 20`, then `corepack enable`.
- A `~/.npmrc` referencing `${FSO_PAT_TOKEN}` (work registry) prints a WARN on
  every pnpm run; harmless for this repo.
- Pushing to `main` deploys the whole repo to public GitHub Pages — cloning is
  safe, committing is not casual (see `nederlands-external-positioning`).

## Step 2 — Python core (Homebrew)

```bash
brew install python@3.14 ffmpeg pipx
pipx ensurepath          # puts ~/.local/bin on PATH
```

### edge-tts — module AND CLI in Homebrew python

`text_to_speech.py` / `story_reader.py` do `import edge_tts`; other flows call
the `edge-tts` CLI. Both come from one pip install into Homebrew python.
Homebrew python 3.14 is PEP-668 "externally managed" (the `EXTERNALLY-MANAGED`
marker exists in its stdlib dir), so a plain `pip install` refuses:

```bash
python3 -m pip install edge-tts --break-system-packages
```

This is the one sanctioned exception to "don't pip into Homebrew python".

### whisper — pipx ONLY, and that is BY DESIGN

```bash
pipx install openai-whisper
```

- CLI lands at `~/.local/bin/whisper` (shebang points into
  `~/.local/pipx/venvs/openai-whisper/`).
- `python3 -c "import whisper"` **fails with ModuleNotFoundError in the Homebrew
  python — this is correct, not a bug.** Repo scripts never import whisper;
  `audio_to_anki.py` (and `story_reader.py` via it) subprocess the `whisper` CLI
  (`cmd = ["whisper", ...]` around line 42 of audio_to_anki.py, model `base`
  hardcoded).
- Do NOT `pip install openai-whisper --break-system-packages` to "fix" the
  import error. That drags torch into the system python and couples repo scripts
  to a heavyweight, breakage-prone dependency for zero benefit.
- Known gap: `story_reader.py`'s `WHISPER_AVAILABLE` flag does not actually
  probe the CLI; a missing CLI surfaces later as `FileNotFoundError`.

## Step 3 — the two venvs (know why each exists)

### scripts/.venv — paused Parkiet experiment. SKIP by default.

Exists solely for `scripts/parkiet_test.py` (multi-voice TTS experiment, paused
since 2026-04-17, commit 1a6d78a). Contains torch 2.11.0 + transformers 5.5.4
(~GBs). **Do not recreate it unless you are resuming Parkiet.** No other script
uses it. If resuming:

```bash
python3 -m venv scripts/.venv
scripts/.venv/bin/pip install torch transformers
# run per the script's own docstring:
# PYTORCH_ENABLE_MPS_FALLBACK=1 python scripts/parkiet_test.py
```

### ~/.claude/fluent-data/.venv-optimizer — FSRS weight optimizer

Used only by the weekly LaunchAgent that runs `optimize_weights.py` (in the
Fluent plugin cache) to retrain FSRS-6 weights from review history.

Why it is separate — three deliberate reasons:

1. Fluent's **runtime hooks are stdlib-only by design** (no venv is guaranteed
   at hook runtime). The optimizer needs `fsrs-optimizer`, which pulls in torch
   — that cannot live in the hook environment.
2. It is pinned to **python 3.11** for fsrs-optimizer/torch compatibility,
   independent of whatever Homebrew's default python3 currently is.
3. fsrs-optimizer's API already broke once on upgrade (adapted in fork commit
   133308c) — isolating it in its own venv contains the blast radius. Expect
   breakage on pip upgrades; don't upgrade casually.

Recreate:

```bash
brew install python@3.11
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv \
  ~/.claude/fluent-data/.venv-optimizer
~/.claude/fluent-data/.venv-optimizer/bin/pip install fsrs-optimizer
# torch comes as a dependency of fsrs-optimizer; no separate install
```

Baseline 2026-07-09: FSRS-Optimizer 6.5.0, torch 2.12.1. The optimizer is
guarded (no-op below 400 total reviews / +50 new); its only run so far logged
`[optimize] insufficient data (185/400, +185 new) — no-op`.

## Step 4 — Anki desktop

Install Anki. Two profiles exist: **alex** and **iuliia**. Media dir used by the
repo's `--copy-to-anki` flows:

```
~/Library/Application Support/Anki2/alex/collection.media/   (~10,000 files)
```

**Trap:** `scripts/anki_utils.py::find_anki_media_folder()` picks `profiles[0]`
from an **unsorted** `Path.iterdir()` and only prints a warning when multiple
profiles exist. It currently lands on `alex` by filesystem luck; there is no
`--profile` override. On a fresh machine, verify which profile it picks before
trusting `--copy-to-anki` (see checklist). If it picks `iuliia`, copy media
manually instead of patching without change control.

## Step 5 — Fluent plugin (fork + marketplace + cache)

Fluent is a Claude Code plugin, forked `m98/fluent` → `aymkin/fluent`; the fork
is the source of truth. Four locations matter:

| Location                                    | Role                                                                              |
| ------------------------------------------- | --------------------------------------------------------------------------------- |
| `~/Projects/fluent`                         | dev clone of the fork (origin = `aymkin/fluent`) — source of truth for FSRS code  |
| `~/.claude/plugins/marketplaces/m98/`       | marketplace clone — the **fork `aymkin/fluent`** (repointed 2026-07-11), has FSRS |
| `~/.claude/plugins/cache/m98/fluent/0.3.0/` | **the runtime** — Claude Code executes hooks from HERE (has FSRS)                 |
| `~/.claude/fluent-data/`                    | 6 learner JSON DBs + `.backups/` + `.venv-optimizer/`                             |

Verify the remotes (verified 2026-07-11):

```bash
git -C ~/.claude/plugins/marketplaces/m98 remote -v
# actual: origin  https://github.com/aymkin/fluent.git  <-- the fork (repointed 2026-07-11)
git -C ~/Projects/fluent remote -v
# actual: origin  https://github.com/aymkin/fluent.git  <-- the fork
```

The FSRS hooks (`fsrs.py`, `migrate_to_fsrs.py`, `optimize_weights.py`) now
exist in the fork dev clone, the marketplace clone, AND the runtime cache. A
fresh plugin install now pulls the fork, so the old SM-2-reversion danger is
resolved at the source. See `nederlands-architecture-contract` §3 for the
remaining open point (the cache lags the fork on two files; the fork→cache sync
is still manual but no longer dangerous).

Traps:

- **Claude executes the CACHE copy**, not the marketplace clone and not
  `~/Projects/fluent`. Hook edits must reach
  `~/.claude/plugins/cache/m98/fluent/0.3.0/.claude/hooks/` or they do nothing.
  The clone→cache sync procedure is **undocumented — known weak point** (see
  `nederlands-architecture-contract`).
- A version bump 0.3.0→x changes the cache path AND silently breaks the
  optimizer LaunchAgent, whose plist **hardcodes**
  `.../cache/m98/fluent/0.3.0/.claude/hooks/optimize_weights.py`.
- Post-repoint (2026-07-11) the marketplace clone and dev clone both track the
  fork; after the same-day `read-db.py` sync the cache matches the fork on all
  live hooks (only the dead `migrate_to_fsrs.py` still differs). Before the
  repoint they diverged (marketplace on upstream `86fb80f` vs fork `4205bf1`).
  Never assume they match — check live:

```bash
git -C ~/Projects/fluent fetch && git -C ~/Projects/fluent status
git -C ~/.claude/plugins/marketplaces/m98 log -1 --format="%h %s"
git -C ~/Projects/fluent log -1 --format="%h %s"
```

## Step 6 — LaunchAgents (from the claude-dotfiles repo)

The three morning jobs live as plists in a separate repo,
`git@github.com:aymkin/claude-dotfiles.git` (locally
`~/Projects/claude-dotfiles/launchd/`). Its `install.sh` deploys them to
`~/Library/LaunchAgents/`, substituting the literal `/Users/Alex.Naymkin` with
`$HOME`. Keep the literal path in the committed plists.

| Plist (com.aymkin.\*)  | Schedule              | Does                                                                                               |
| ---------------------- | --------------------- | -------------------------------------------------------------------------------------------------- |
| `claude-plugin-update` | daily 09:03           | `git pull` all marketplaces/skills, rewrite skills.lock                                            |
| `claude-dotfiles-sync` | daily 09:04           | sync `~/.claude/` → dotfiles repo, auto-commit+push                                                |
| `fluent-fsrs-optimize` | Sun 09:05 (Weekday 0) | optimizer venv python → cache `optimize_weights.py`, log `~/.claude/logs/fluent-fsrs-optimize.log` |

On a new machine: clone claude-dotfiles, run its `install.sh` (backs up
overwritten files, merges `mcp.json` into `~/.claude.json` via jq, loads
LaunchAgents). Details are that repo's own README/CLAUDE.md territory.

## Verification checklist — run all, compare outputs

| Command                                                                  | Expected (2026-07-09 baseline)                                                                        |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `python3 --version`                                                      | `Python 3.14.5` (Homebrew; `which python3` → `/opt/homebrew/bin/python3`)                             |
| `ffmpeg -version \| head -1`                                             | `ffmpeg version 8.1.1 ...`                                                                            |
| `edge-tts --version`                                                     | `edge-tts 7.2.7`                                                                                      |
| `python3 -c "import edge_tts; print('ok')"`                              | `ok`                                                                                                  |
| `which whisper`                                                          | `/Users/<you>/.local/bin/whisper`                                                                     |
| `whisper --help \| head -1`                                              | `usage: whisper [-h] [--model MODEL] ...`                                                             |
| `python3 -c "import whisper"`                                            | **ModuleNotFoundError — this is the CORRECT state**                                                   |
| `pipx list \| grep whisper`                                              | `package openai-whisper 20250625 ...`                                                                 |
| `pnpm --version`                                                         | `10.29.2` (any 10.x fine)                                                                             |
| `node_modules/.bin/prettier --version`                                   | `3.8.1` (any ^3.7.4)                                                                                  |
| `python3 scripts/test_fluent_import.py \| tail -1`                       | `25 passed` (scripts/README.md says 21 — README is stale)                                             |
| `python3 scripts/audio_to_anki.py --help`                                | usage text, exit 0 (stdlib import check)                                                              |
| `ls "$HOME/Library/Application Support/Anki2/"`                          | contains `alex` and `iuliia`                                                                          |
| `~/.claude/fluent-data/.venv-optimizer/bin/python --version`             | `Python 3.11.15`                                                                                      |
| `~/.claude/fluent-data/.venv-optimizer/bin/pip list \| grep -i fsrs`     | `FSRS-Optimizer 6.5.0`                                                                                |
| `git -C ~/.claude/plugins/marketplaces/m98 remote -v`                    | origin = `aymkin/fluent` (the fork, repointed 2026-07-11 — has FSRS); dev fork is `~/Projects/fluent` |
| `ls ~/.claude/plugins/cache/m98/fluent/`                                 | `0.3.0` (if different: plist path is now broken)                                                      |
| `plutil -p ~/Library/LaunchAgents/com.aymkin.fluent-fsrs-optimize.plist` | valid plist; Hour 9, Minute 5, Weekday 0; ProgramArguments uses the venv python + cache path          |
| `launchctl list \| grep aymkin`                                          | three `com.aymkin.*` entries, status `0`                                                              |

Note on `pnpm run format:check`: it currently exits 1 on untracked scratch files
— a non-zero exit does NOT prove your environment is broken. Scope prettier
checks to tracked files (see `nederlands-validation-and-qa`).

## Provenance and maintenance

Every claim above was re-verified 2026-07-09 by running the command on the live
machine. Re-verify drift-prone items with:

- Tool versions:
  `python3 --version && ffmpeg -version | head -1 && edge-tts --version && pipx list | grep whisper && pnpm --version`
- whisper-is-CLI-only design: `grep -n '"whisper"' scripts/audio_to_anki.py`
  (subprocess arg, ~line 42)
- edge_tts is the only non-stdlib repo import:
  `grep -rn "^import \|^from " scripts/*.py | grep -v "scripts/parkiet" | sort -u`
  and eyeball
- PEP 668 marker:
  `python3 -c "import sysconfig,os; print(os.path.exists(os.path.join(sysconfig.get_path('stdlib'), 'EXTERNALLY-MANAGED')))"`
- Parkiet venv contents:
  `scripts/.venv/bin/pip list | grep -Ei "torch|transformers"`
- Optimizer venv:
  `~/.claude/fluent-data/.venv-optimizer/bin/pip list | grep -Ei "fsrs|torch"`
- Anki profiles + picker behavior:
  `ls "$HOME/Library/Application Support/Anki2/"` and
  `grep -n "profiles\[0\]" scripts/anki_utils.py`
- Fluent remotes / cache version / clone drift: the three git commands in Step 5
  plus `ls ~/.claude/plugins/cache/m98/fluent/`
- LaunchAgents:
  `plutil -p ~/Library/LaunchAgents/com.aymkin.*.plist | grep -E "Label|Hour|Minute|Weekday"`
  and `launchctl list | grep aymkin`
- Test count: `python3 scripts/test_fluent_import.py | tail -1`
- package.json staleness vs real remote: `git remote -v` vs
  `grep -n "de_opmaat" package.json`

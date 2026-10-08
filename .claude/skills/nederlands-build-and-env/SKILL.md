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

| Component         | Version                                     | Install method                            | Location                                       |
| ----------------- | ------------------------------------------- | ----------------------------------------- | ---------------------------------------------- |
| python3 (default) | 3.14.5                                      | `brew install python@3.14`                | `/opt/homebrew/bin/python3`                    |
| python3.11        | 3.11.15                                     | `brew install python@3.11`                | `/opt/homebrew/opt/python@3.11/bin/python3.11` |
| ffmpeg            | 8.1.1                                       | `brew install ffmpeg`                     | `/opt/homebrew/bin/ffmpeg`                     |
| edge-tts          | 7.2.7                                       | pip into Homebrew python (module + CLI)   | `/opt/homebrew/bin/edge-tts`                   |
| openai-whisper    | 20250625                                    | **pipx ONLY** (CLI, no importable module) | `~/.local/bin/whisper`                         |
| node              | v20.17.0                                    | nvm                                       | `~/.nvm/versions/node/v20.17.0/`               |
| pnpm              | 10.29.2                                     | corepack (ships with node)                | symlink in nvm bin dir                         |
| prettier          | 3.8.1 (spec `^3.7.4`)                       | `pnpm install` in repo                    | `node_modules/.bin/prettier`                   |
| scripts/.venv     | py 3.14.5, torch 2.11.0, transformers 5.5.4 | manual venv                               | repo `scripts/.venv/` — **Parkiet only**       |
| .venv-optimizer   | DELETED 2026-09-16 (freed 993 MB)           | do not recreate                           | `~/.claude/fluent-data/.venv-optimizer/`       |
| Anki desktop      | profiles `alex`, `iuliia`                   | app install                               | `~/Library/Application Support/Anki2/`         |

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

### ~/.claude/fluent-data/.venv-optimizer — NOT part of a fresh setup

**Do not create this venv.** It served `optimize_weights.py`, deleted from the
plugin in fork commit `09618f3` (2026-08-17); its weekly LaunchAgent was retired
2026-09-16 (`nederlands-failure-archaeology` entry 12). A fresh machine needs
nothing here — `fsrs.py` uses the built-in `DEFAULT_W`, which is what ran all
along: `metadata.weights` has always been `null`.

It was deleted on 2026-09-16, freeing **993 MB** (it held python 3.11.15,
FSRS-Optimizer 6.5.0, torch 2.12.1). The six learner JSONs beside it were
verified unchanged by checksum before and after.

Why it was ever separate, since the reasoning still applies to any future
attempt: Fluent's runtime hooks are **stdlib-only by design** (no venv is
guaranteed at hook runtime), `fsrs-optimizer` drags in torch, and it needed
pinning to python 3.11 independent of Homebrew's default. Its API broke once on
upgrade already (fork `133308c`).

## Step 4 — Anki desktop

Install Anki. Two profiles exist: **alex** and **iuliia**. Media dir used by the
repo's `--copy-to-anki` flows:

```
~/Library/Application Support/Anki2/alex/collection.media/   (~10,000 files)
```

**The profile is pinned:** every script targets `ANKI_PROFILE = "alex"` in
`scripts/anki_utils.py`, so a fresh machine needs an Anki profile named exactly
`alex`. Without it, `find_anki_media_folder()` returns `None` and prints the
profiles it found. `anki_utils.py import` refuses unless `alex` is the profile
open in Anki. Until 2026-09-28 the media picker took `profiles[0]` from an
unsorted `Path.iterdir()`, which let audio and notes end up in different
profiles.

## Step 5 — Fluent plugin (fork + cache)

Fluent is a Claude Code plugin, forked `m98/fluent` → `aymkin/fluent`; the fork
is the source of truth and, as a `directory` source, the marketplace `aymkin`
itself. Three locations matter:

| Location                                           | Role                                                                                    |
| -------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `~/Projects/fluent`                                | the fork (origin = `aymkin/fluent`) and the marketplace — source of truth for FSRS code |
| `~/.claude/plugins/cache/aymkin/fluent/<version>/` | **the runtime** — Claude Code executes hooks from HERE (has FSRS)                       |
| `~/.claude/fluent-data/`                           | 6 learner JSON DBs + `.backups/` + `results/`                                           |

Verify the wiring (verified 2026-10-08):

```bash
jq -c '.aymkin.source' ~/.claude/plugins/known_marketplaces.json
# actual: {"source":"directory","path":"/Users/Alex.Naymkin/Projects/fluent"}
git -C ~/Projects/fluent remote -v
# actual: origin  https://github.com/aymkin/fluent.git  <-- the fork
```

The FSRS hook `fsrs.py` exists in the fork AND the runtime cache.
(`migrate_to_fsrs.py` and `optimize_weights.py` were also FSRS hooks; both were
deleted in fork `09618f3`, 2026-08-17 — the migration was one-shot and already
run, the optimizer is retired.) A plugin install or update copies the fork
directory, so a rebuild can no longer revert the scheduler to SM-2.

Traps:

- **Claude executes the CACHE copy**, not `~/Projects/fluent`. A hook edit
  reaches `~/.claude/plugins/cache/aymkin/fluent/<version>/.claude/hooks/` only
  through a release — version bump, release commit,
  `claude plugin update fluent@aymkin`, restart; the steps are in
  `nederlands-change-control` (Fluent change flow).
- A version bump 0.3.0→x changes the cache path AND silently breaks the
  optimizer LaunchAgent, whose plist **hardcoded** a cache path (job retired
  2026-09-16, script deleted in fork `09618f3` — see
  `nederlands-change-control`).
- A fork commit without a release is not live, and every release leaves the
  previous version directories in the cache. Never assume the runtime matches
  the fork — compare the installed commit with the fork's HEAD:

```bash
git -C ~/Projects/fluent fetch && git -C ~/Projects/fluent status
jq -r '.plugins["fluent@aymkin"][0] | .version, .gitCommitSha' \
  ~/.claude/plugins/installed_plugins.json
git -C ~/Projects/fluent log -1 --format="%H %s"
```

## Step 6 — LaunchAgents (from the claude-dotfiles repo)

The three morning jobs live as plists in a separate repo,
`git@github.com:aymkin/claude-dotfiles.git` (locally
`~/Projects/claude-dotfiles/launchd/`). Its `install.sh` deploys them to
`~/Library/LaunchAgents/`, substituting the literal `/Users/Alex.Naymkin` with
`$HOME`. Keep the literal path in the committed plists.

| Plist (com.aymkin.\*)  | Schedule           | Does                                                                                        |
| ---------------------- | ------------------ | ------------------------------------------------------------------------------------------- |
| `claude-plugin-update` | daily 09:03        | `git pull` all marketplaces/skills, rewrite skills.lock                                     |
| `claude-dotfiles-sync` | daily 09:04        | sync `~/.claude/` → dotfiles repo, auto-commit+push                                         |
| `fluent-fsrs-optimize` | RETIRED 2026-09-16 | booted out; script deleted in fork `09618f3`, log `~/.claude/logs/fluent-fsrs-optimize.log` |

On a new machine: clone claude-dotfiles, run its `install.sh` (backs up
overwritten files, merges `mcp.json` into `~/.claude.json` via jq, loads
LaunchAgents). Details are that repo's own README/CLAUDE.md territory.

## Verification checklist — run all, compare outputs

| Command                                                           | Expected (2026-07-09 baseline)                                                                                                                   |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `python3 --version`                                               | `Python 3.14.5` (Homebrew; `which python3` → `/opt/homebrew/bin/python3`)                                                                        |
| `ffmpeg -version \| head -1`                                      | `ffmpeg version 8.1.1 ...`                                                                                                                       |
| `edge-tts --version`                                              | `edge-tts 7.2.7`                                                                                                                                 |
| `python3 -c "import edge_tts; print('ok')"`                       | `ok`                                                                                                                                             |
| `which whisper`                                                   | `/Users/<you>/.local/bin/whisper`                                                                                                                |
| `whisper --help \| head -1`                                       | `usage: whisper [-h] [--model MODEL] ...`                                                                                                        |
| `python3 -c "import whisper"`                                     | **ModuleNotFoundError — this is the CORRECT state**                                                                                              |
| `pipx list \| grep whisper`                                       | `package openai-whisper 20250625 ...`                                                                                                            |
| `pnpm --version`                                                  | `10.29.2` (any 10.x fine)                                                                                                                        |
| `node_modules/.bin/prettier --version`                            | `3.8.1` (any ^3.7.4)                                                                                                                             |
| `python3 scripts/test_fluent_import.py \| tail -1`                | `25 passed` (scripts/README.md says 21 — README is stale)                                                                                        |
| `python3 scripts/audio_to_anki.py --help`                         | usage text, exit 0 (stdlib import check)                                                                                                         |
| `ls "$HOME/Library/Application Support/Anki2/"`                   | contains `alex` and `iuliia`                                                                                                                     |
| `jq '.aymkin.source' ~/.claude/plugins/known_marketplaces.json`   | `directory` → `~/Projects/fluent`: the fork is the marketplace, no clone under `marketplaces/`                                                   |
| `ls -d ~/.claude/plugins/cache/*/fluent/*/ \| sort -V \| tail -1` | the runtime — equals `installPath` in `~/.claude/plugins/installed_plugins.json`; older version dirs stay beside it, so nothing may hardcode one |
| `launchctl list \| grep aymkin`                                   | two entries (`claude-plugin-update`, `claude-dotfiles-sync`); the optimizer job was retired 2026-09-16                                           |

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
- Anki profiles + pinned target: `ls "$HOME/Library/Application Support/Anki2/"`
  and `grep -n ANKI_PROFILE scripts/anki_utils.py`
- Fluent remotes / cache version / clone drift: the three git commands in Step 5
  plus `ls ~/.claude/plugins/cache/aymkin/fluent/`
- LaunchAgents:
  `plutil -p ~/Library/LaunchAgents/com.aymkin.*.plist | grep -E "Label|Hour|Minute|Weekday"`
  and `launchctl list | grep aymkin`
- Test count: `python3 scripts/test_fluent_import.py | tail -1`
- package.json staleness vs real remote: `git remote -v` vs
  `grep -n "de_opmaat" package.json`

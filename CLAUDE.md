# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dutch language learning materials repository (NT2 - Nederlands als Tweede Taal).
Contains two courses, vocabulary lists, tests, audio files, Anki flashcard
materials, daily study plans, and learning methodology notes. Base language is
Russian.

**Two learners:**

- `de_opmaat/` — materials for **Alex** (De Opmaat, A2 level)
- `link/` — materials for **Alex** (Link, praktisch geschoolden track, nt2.nl)
- `link_plus/` — materials for **Yulia** (Link+, theoretisch geschoolden track,
  B1→B2, nt2.nl)

## Commands

```bash
pnpm run format        # Format all markdown files with Prettier
pnpm run format:check  # Check formatting without changes
```

**Prettier config:** `proseWrap: always`, `printWidth: 80`, tabs off. When
writing markdown, keep lines wrapped at 80 characters. Prettier ignores
`_anki.txt`, `*.pdf`, `*.mp3`, `*.docx` files (see `.prettierignore`).

## Deployment

Pushes to `main` auto-deploy the entire repo to GitHub Pages via
`.github/workflows/pages.yml`. All content becomes publicly accessible.

`private/` is gitignored and therefore never published. Put third-party source
texts there — a scanned NT2 adaptation is a copyrighted derivative work even
when the original is public domain, so its text must not reach Pages. Generated
readers built from it belong in a private Artifact, not in the repo.

## Directory Structure

```
de_opmaat/          # De Opmaat course (A2, Alex) — thema_1/ through thema_9/ + transcriptions/
link/               # Link praktisch geschoolden (Alex, nt2.nl) — thema_N/{N}_{task_name}/
link_plus/              # Link+ theoretisch geschoolden (Yulia, B1→B2, nt2.nl) — thema_N/{N}_{task_name}/
daily/              # Daily practice and study planning
  templates/        #   Generic reusable templates (les, week review, monthly)
  maart_2026/       #   Monthly study plan with weekly/daily structure
    W{N}_{month}/   #     Week folders (W0_feb, W1_mrt, etc.)
      DD_MM/les.md  #       Daily lesson files with pre-filled resources
      week_review.md#       Weekly review template
    controle/       #     Baseline and monthly progress measurements
  archive/          #   Old daily practice files (pre-maart_2026)
  dutch_stories/    #   Dutch story subtitles and transcripts
  frequentie_2026/  #   Frequency-core plan 14.09–13.12.2026 (single plan.md, no templates)
frequentie/         # Frequency-core Anki deck for Alex (note type "Frequentie NL", RU→NL) + README
grammatica/         # Alex's grammar track (leading since 2026-09-16): regels/ = Link+ rule extracts + README
other/              # Learning methodology notes and analysis
  language_learning_methods/  # Evgeniy 6-step, Alisher immersion, comparisons
scripts/            # Automation utilities (audio_to_anki.py, text_to_speech.py, etc.)
private/            # Gitignored: third-party source texts, never deployed
```

## Study Plan System (daily/maart_2026/)

The active study plan uses the **Evgeniy 6-step method** with a two-day cycle:

- **Evening (30 min):** Steps 1-3 on NEW material (cold watch, analyze, extract
  phrases)
- **Next day commute + lunch:** Steps 4-6 on YESTERDAY's material (shadowing,
  dictation, expressive repetition)

Weekly resource rotation: Mon=Heb je zin?, Tue=De Opmaat audio, Wed=Net in
Nederland, Thu=NOS Jeugdjournaal, Fri=Het Klokhuis/Easy Dutch + weekly review.

Progressive difficulty across weeks: W0-1 steps 1-3 only, W2 adds steps 4-5, W3
activates all 6, W4 full protocol + monthly test.

Roadmap overview: `daily/roadmap_maart_2026.md`

## Scripts

> **Detailed docs:** `scripts/README.md`

Four scripts share `anki_utils.py` (Anki profile detection + media copying):

```
audio_to_anki.py ──┐
                   ├─→ anki_utils.py (find profiles, validate, copy to media)
text_to_speech.py ─┘

story_reader.py ──────┐ standalone readers
multivoice_reader.py ─┘ (edge-tts Python API + WordBoundary timings;
                        multivoice_reader imports align_timings from story_reader)
```

### audio_to_anki.py — Audio to Anki Sentence Cards

Splits audio dialogues into sentences and generates Anki cards with original
textbook audio. Dependencies:
`brew install ffmpeg && pip install openai-whisper`

```bash
python3 scripts/audio_to_anki.py de_opmaat/thema_7/2/h07_oefening_02.mp3 \
    --transcript de_opmaat/thema_7/2/h07_oefening_02.md \
    --theme gezondheid \
    --copy-to-anki
```

| Param            | Description             | Default    |
| ---------------- | ----------------------- | ---------- |
| `audio`          | Path to MP3 file        | (required) |
| `--transcript`   | MD file with transcript | -          |
| `--theme`        | Theme for Anki tags     | `general`  |
| `--level`        | CEFR level              | `A2`       |
| `--copy-to-anki` | Auto-copy to Anki media | off        |

Two modes: **Forced Alignment** (with `--transcript`, recommended — exact
boundaries + clean text) and **Whisper-only** (without transcript — quick
start).

### text_to_speech.py — TTS Audio Generation

Generates Dutch TTS audio (edge-tts, Microsoft Azure voices: colette, fenna,
maarten). Auto-detects three input formats: transcript (`Speaker: text`), plain
markdown, or existing Anki TSV (updates cards with audio). Dependency:
`pip install edge-tts`

Speech rate defaults to `-10%` (0.9x native) for A2–B1 listeners; `--rate` takes
any edge-tts percentage, where `-X%` yields exactly `1/(1-X/100)` duration.

```bash
python3 scripts/text_to_speech.py input.md --voice colette --copy-to-anki
python3 scripts/text_to_speech.py input.md --rate -20%   # 0.8x, slower
```

### story_reader.py — Interactive HTML Reader

Creates self-contained HTML pages with synchronized sentence highlighting and
embedded audio (base64). Supports playback speed 0.7x-1.5x. No server needed —
opens in browser. Dependency: `pip install edge-tts`

Sentence timings come from the edge-tts Python API's `boundary="WordBoundary"`
events, whose text is the input's own — no Whisper, no fuzzy matching. Same
`--rate` default as above. Alignment checks:
`python3 scripts/test_story_reader.py`

```bash
python3 scripts/story_reader.py de_opmaat/thema_8/verhaal_studentenhuis/verhaal_studentenhuis_deel1.md
```

### multivoice_reader.py — Cast Reader (dialogue, several voices)

Same idea as `story_reader.py`, but for texts with a narrator and characters:
each role gets its own voice and speech rate, segments are synthesised
separately and concatenated with ffmpeg, so sentence boundaries are exact by
construction rather than aligned after the fact. Roles are colour-coded in the
page and listed in a cast table. Only three Dutch voices exist, so distinguish
more characters by rate — a slow role and a fast role read as different people
on the same voice.

Input is a markdown cast script: `---` frontmatter with `title` / `subtitle` /
`verse_role` / `footer` and a `cast:` block of `role: voice rate`; then `# ` for
a chapter, `**Role:**` for that role's speech, `> ` for verse (lines kept, each
highlights separately), anything else the narrator. Blank lines separate
segments. `--dry-run` reports the segment plan without synthesising.

Verhaal files work as cast scripts unchanged: `**bold**` vocabulary renders as
`<b>` and is stripped before TTS, a lone `---` becomes a scene rule plus pause,
and parsing stops at `## Vragen` / `## Woordenlijst` (`STOP_HEADINGS`, shared
with `story_reader.py`) so exercises are read, not narrated. Metadata lines
(`_..._`), HTML comments and table rows are skipped.

An unknown role is a hard error, so `--dry-run` also catches a narrator
paragraph that the `**Role:**` pattern grabbed by accident.

```bash
python3 scripts/multivoice_reader.py private/verhaal.md --dry-run
python3 scripts/multivoice_reader.py private/verhaal.md --out ~/Desktop/verhaal
```

Parser checks: `python3 scripts/test_multivoice_reader.py`

### build_vocab_index.py / check_recycling.py — /anki-cards toolchain

Both serve the `/anki-cards` command and need nothing beyond Python 3 stdlib.
`build_vocab_index.py` writes `<course>/woordenlijst_index.txt` — every
woordenlijst word the learner has met, grouped by thema, so card generation
reads one file instead of 40 decks. One index per course, because each course
has its own learner (`link/` Alex, `link_plus/` Yulia).

`check_recycling.py` gates style rule 4 on a finished deck: every example must
reuse 2-4 words from that index, at least one from an earlier thema. It folds
Dutch inflection crudely (doubled letters collapsed, infinitive `-en` dropped,
prefix match) and ignores rule 3's discourse markers plus closed-class words, so
its count is a floor — read a flagged example before rewriting it. Exit 1 means
at least one card recycles too little.

```bash
python3 scripts/build_vocab_index.py --course link_plus
python3 scripts/check_recycling.py link/thema_13/taak_1/woordenlijst_thema13_taak1_anki.txt
```

### anki_vandaag.py — Anki → Fluent Bridge (frequentie)

Prints the words whose Anki cards got their **first** review on a given day
(default today, Anki's 04:00 rollover respected). Reads a copy of
`collection.anki2`, never writes. Stdlib only. Feeds the "Frequentie bridge"
rule in Tutor Mode; deck spec and daily cycle in `frequentie/README.md`.

```bash
python3 scripts/anki_vandaag.py --out private/frequentie/vandaag.md
python3 scripts/anki_vandaag.py --date 2026-06-30 --notetype "LINK Vocabulary"
```

### frequentie_fluent.py — Fluent под частотный план

Разделение труда: **Anki держит слова, Fluent — предложения** на этих словах
плюс собственные ошибки Alex. Одно слово в одном SRS, не в двух.

```bash
python3 scripts/frequentie_fluent.py --reset                    # только error_pattern, история обнулена
python3 scripts/frequentie_fluent.py --zinnen private/frequentie/vandaag.md
python3 scripts/frequentie_fluent.py --zinnen … --dry-run       # отчёт без записи
```

Предложения дня заводятся с приоритетом `critical`: `read-db.py --review`
сортирует по приоритету и режет по `daily_limits.review_items_per_day`, поэтому
всё, что ниже среза, не подаётся вообще. Бэкап в
`.backups/pre-frequentie-<режим>-<timestamp>/` перед каждой записью.

### grammatica_fluent.py — грамматический трек в Fluent

Заводит правила из `grammatica/regels/` как `grammar_rule` (`gram_lp_1.1`), **по
одной карточке на правило** — чтобы у каждого правила копилась своя
`review_history`, то есть число попыток. Без знаменателя «ошибся 7 раз» ничего
не значит; `mistakes-db` его не даёт, а карточка на правило даёт.

```bash
python3 scripts/grammatica_fluent.py --regels grammatica/regels --per-dag 2 --dry-run
python3 scripts/grammatica_fluent.py --regels grammatica/regels --per-dag 2
```

Fluent не настраивается — **расписание и объём живут в базе**: `--per-dag`
раскладывает `due_date` по рабочим дням (воскресенье пропускается),
`rebuild_queue` бакетит по `due_date`, `daily_limits` режет по объёму. Правка
скилла в кэше плагина запрещена: её затрёт пересборка, и она обязана идти через
форк. Идемпотентно — уже заведённое правило не трогается.

`VOORRANG` поднимает `7.1`/`7.2` в начало: `1.1` и `4.1` ссылаются на них
вперёд, после перестановки ссылок вперёд ноль (`grammatica/README.md`). Бэкап —
тем же `save()`, что у `frequentie_fluent.py`.

### fluent_import.py — Curriculum → Fluent Bridge

Seeds Link/De Opmaat vocab and grammar into Fluent's spaced-repetition database.
No dependencies beyond Python 3 stdlib.

```bash
python3 scripts/fluent_import.py --course link          # import active unit
python3 scripts/fluent_import.py --course link --check  # mastery gate check
python3 scripts/fluent_import.py --course link --advance # advance + import next
```

- Per-course progress lives in `<course>/curriculum.json` (units with
  `status: done|active|locked`; exactly one `active` at a time).
- Writes only `~/.claude/fluent-data/spaced-repetition.json`; backs it up to
  `.backups/pre-import-<timestamp>/` before every write. Idempotent: stable
  `item_id` prefixed `{course}_t{N}_` so re-running is safe.
- SM-2 scheduling is owned by Fluent — the importer only seeds new items and
  rebuilds the review queue.
- Advancement threshold: ≥ 80% of the unit's cards at `mastery_level ≥ 3` AND
  zero "red" cards (`consecutive_incorrect ≥ 2`).

## Anki Integration

**Profile:** `alex` — media at
`~/Library/Application Support/Anki2/alex/collection.media/`

### Anki File Formats

Files ending in `_anki.txt` use tab-separated format with header directives:

| Format                      | Header                                         | Fields                                                |
| --------------------------- | ---------------------------------------------- | ----------------------------------------------------- |
| Vocabulary with audio       | `#separator:tab` `#html:true` `#tags column:5` | Dutch \| Russian \| Notes \| Audio \| Tags            |
| Sentence-only               | `#separator:tab` `#html:false`                 | Dutch \| Russian                                      |
| Sentence cards with audio   | `#separator:tab` `#html:true` `#tags column:4` | Dutch \| Russian \| Audio \| Tags                     |
| Construction (multisensory) | `#separator:tab` `#html:true` `#tags column:6` | Russian \| Dutch \| Context \| Image \| Audio \| Tags |

**Tag structures:**

- Sentences: `sententiae::{theme}::{level}::audio`
- Constructions: `constructies::{category}::{level}` (categories: mening,
  vragen, oorzaak, tijd, contrast, dagelijks, fillers)

### Link Course Anki Formats (`link/`)

**Words & phrases** (woordenlijst, uitdrukkingen) — 5 columns:

```
#separator:tab
#html:true
#columns:Word	Example	Translation	TranslationExample	Tags
#tags column:5
```

| Column             | Description                             |
| ------------------ | --------------------------------------- |
| Word               | Dutch word/phrase with article if noun  |
| Example            | Dutch example sentence                  |
| Translation        | Russian translation                     |
| TranslationExample | Russian translation of example sentence |
| Tags               | `link::thema{N}::taak{N}::A2`           |

**Dialog sentences** (zinnen) — 3 columns:

```
#separator:tab
#html:true
#tags column:3
```

| Column  | Description                       |
| ------- | --------------------------------- |
| Dutch   | Dutch sentence from the dialog    |
| Russian | Russian translation               |
| Tags    | `link::thema{N}::taak{N}::zinnen` |

Uitdrukkingen (vaste uitdrukkingen) use the 5-column word format with tag suffix
`::uitdrukkingen` instead of `::A1`.

### Card Templates

Front: `{{Front}} {{Audio}}` — Back: `{{FrontSide}}<hr id="answer">{{Back}}`

Audio references: `[sound:filename.mp3]` (ElevenLabs, Amazon Polly, or
audio_to_anki.py output)

## File Naming Conventions

| Pattern                               | Purpose                                          |
| ------------------------------------- | ------------------------------------------------ |
| `opdracht_{N}.md`                     | Numbered exercises (thema 5, 8-9)                |
| `{N}_opdracht.md`                     | Numbered exercises (thema 6-7)                   |
| `woordenlijst_pagina_{N}_anki.txt`    | Vocabulary by page                               |
| `grammatica_{topic}.md`               | Grammar explanations                             |
| `taalhulp_{topic}.md`                 | Grammar/phrase reference (non-Anki)              |
| `taalhulp_{topic}_anki.txt`           | Topic-specific flashcards                        |
| `sententiae_{theme}_anki.txt`         | Sentence cards with audio                        |
| `constructies_{topic}_anki.txt`       | Construction cards                               |
| `verhaal_{NN}_{title}.md`             | Story exercises                                  |
| `dialog.md` / `dialog_{N}.md`         | Link course dialog transcripts                   |
| `zinnen.md`                           | Link course sentence lists                       |
| `luisteren_thema{N}_taak{N}_anki.txt` | Link listening exercise cards                    |
| `lezen_thema{N}_taak{N}_anki.txt`     | Link reading exercise cards                      |
| `*_telegram.md`                       | Telegram-formatted story versions (Link, mobile) |

## Content Conventions

- Dutch nouns must include articles: `het stokbrood`, `de stroopwafel`
- Provide Russian translations; English as supplementary
- Exercise corrections: ✅ correct, ❌ incorrect, ~~strikethrough~~ for wrong
  parts
- Story files: **bolded verbs** for pattern recognition + grammar tables +
  vocabulary list (Dutch -> Russian -> English)
- Error tracking: Date stamp + tables (Error | Correction | Rule/Tip)

## Grammar Reference

Use tables for Dutch word order patterns:

| Conjunction | Word Order         | Example                            |
| ----------- | ------------------ | ---------------------------------- |
| **want**    | normal (S + V)     | Ik blijf thuis, want ik ben ziek.  |
| **omdat**   | verb to end        | Ik blijf thuis, omdat ik ziek ben. |
| **als**     | verb to end        | Als het regent, blijf ik thuis.    |
| (inversie)  | V + S after adverb | Morgen ga ik naar Amsterdam.       |

## Language Context

- Primary language: Dutch (Nederlands)
- Base language: Russian (English as supplementary)
- Alex: A2 (elementary), approaching B1 — De Opmaat (`de_opmaat/`) + Link
  praktisch (`link/`)
- Yulia: A1+ (between A1 and A2), working toward Link+ B1→B2 — Link+ theoretisch
  (`link_plus/`)

## Tutor Mode

When acting as a Dutch tutor (vocabulary questions, grammar explanations,
conversational practice), follow these rules:

### Session Flow

1. **Greeting** — начни на нидерландском, спроси тему занятия
2. **Warm-up review** — естественно вплети повторение ранее изученных слов и
   грамматики из текущей темы (для Alex — `de_opmaat/` и `link/`, для Yulia —
   `link_plus/`)
3. **Core work** — новый материал, вопросы, упражнения
4. **Wrap-up** — кратко подведи итог, что разобрали

### Response Algorithm (vocabulary & grammar questions)

При вопросе о слове, фразе или грамматической конструкции:

1. **Суть** — объясни значение через контекст, не просто перевод
2. **Нюансы** — формальность (formeel / informeel / slang), культурные
   особенности, типичные ошибки
3. **Грамматика** — род, число, управление, место в предложении — если
   релевантно
4. **3 примера** — из реальных ситуаций (формальная, бытовая, профессиональная),
   на нидерландском с переводом на русский
5. **Проверка** — спроси, всё ли понятно или нужны дополнения

### Grammatica-traject (Alex, ведущий трек с 2026-09-16)

- **Грамматика ведущая, слова нанизываются.** Правила лежат в Fluent как
  `grammar_rule` с `item_id` вида `gram_lp_1.1`; свод — `grammatica/regels/`,
  спецификация — `grammatica/README.md`.
- Упражнение строится **на правиле дня**, а наполнение берётся из слов в
  `private/frequentie/vandaag.md`. Правило — единственная трудность в задании.
- **Карточки Anki привязываются к правилам по дню, а не по счёту слов.** 20 слов
  и 2 правила в день — значит 10 слов на правило. Тег карточки несёт день
  (`frequentie::kern::dagNN`), день совпадает с `due_date` правила. Партия из
  100 карточек покрывает 5 дней, не 10 — следующую партию готовить заранее,
  иначе слова кончатся раньше правил.
- Затачивать пример под правило нужно **не всегда**. Правила делятся на три
  рода: _фоновые_ (формы глагола, `de`/`het`, местоимения, множественное число,
  орфография — присутствуют в любом корректном предложении, специальный пример
  не нужен), _точечные_ (`niet`, `geen`, вопросы, модальные + инфинитив, `gaan`
  - инфинитив, императив, два глагола — пример лепится намеренно) и
    _метаязыковые_ («что такое глагол», «что такое подлежащее» — примером не
    показываются, это проверка понимания). Фиксированное соотношение слов к
    правилам даёт работу там, где она не нужна.
- **Держи ступень задания низкой.** Порядок возрастания: (1) пропуск в готовом
  предложении, (2) найти и исправить одну ошибку, (3) своя фраза до 6 слов в
  одну часть, (4) фраза с вынесенным вперёд обстоятельством, (5) две части с
  союзом. Рабочая ступень Alex — 3. Ступень 5 давать не чаще раза в неделю и как
  замер, не как тренировку.
- Причина правила: 2026-09-15 упражнения строились сразу на ступени 5, каждое
  требовало до 11 решений при одном проверяемом — Alex остановил сессию на 18-м
  задании из 30. Подробности в `daily/frequentie_2026/plan.md`, раздел 5.
- **Предложения выдумывать из его жизни**, не абстрактные: код, файлы, коллеги,
  дорога, Hilversum. Проверено там же: искусственная ситуация не сцепляется.
- Если Alex пишет «угадал» или «не уверен» — ставить `quality: 3`, не 5.
  Угаданная пятёрка уводит карточку на недели и ломает расписание.

### Frequentie bridge (Fluent sessions for Alex)

- Перед `/fluent-review` (и любой Fluent-сессией для Alex) прочитай
  `private/frequentie/vandaag.md`, если он датирован сегодня. Это слова, которые
  Alex утром ввёл в Anki по частотной колоде (`frequentie/`).
- Упражнения на `grammar_rule` строй **на этих словах**: они попадают в
  предложения на инверсию, `omdat`-порядок, perfectum и т.д.
- Упражнения на `error_pattern` — тоже: сама ошибка задана карточкой, но
  предложение-носитель свободно, и брать для него надо слова дня. Правило про
  спойлер остаётся: верную форму разбираемой ошибки в формулировку не выносить.
- `vocabulary`-карточки **не трогай**: они проверяют собственное слово, подмена
  ломает то, что они измеряют. Считай, что мост покрывает два типа из трёх.
- Раздел «Al bekend» в файле — слова, которые Alex уже знает. Это опора: из них
  строй остаток предложения, чтобы новое слово было единственной трудностью.
- **Не** заводи их в `new_vocabulary[]` — их интервалы ведёт Anki; второй SRS на
  то же слово — двойная работа без прибавки (Mondria & Wiersma 2004).
- Файла нет или он вчерашний — работай как обычно, слова не выдумывай. Обновить:
  `python3 scripts/anki_vandaag.py --out private/frequentie/vandaag.md`.

### Content Generation (Anki cards, reading texts)

- Опирайся на уже изученную лексику и грамматику из пройденных тем
- Перед генерацией проверь woordenlijst и grammatica файлы текущей и предыдущих
  тем
- Отслеживай фокус текущей сессии: какие слова и конструкции разбирались
- Новые слова вводи дозированно, с опорой на знакомый контекст

### Tone

Дружелюбный, терпеливый, поддерживающий — как опытный репетитор. Никогда не
давай голый перевод без объяснения.

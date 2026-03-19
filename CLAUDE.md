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
- `link/` — materials for **Yulia** (Link, B1 level)

## Commands

```bash
npm run format        # Format all markdown files with Prettier
npm run format:check  # Check formatting without changes
```

## Directory Structure

```
de_opmaat/          # De Opmaat course (A2) — thema_1/ through thema_9/ + transcriptions/
link/               # Link course (B1) — thema_1/ through thema_4/
daily/              # Daily practice and study planning
  templates/        #   Generic reusable templates (les, week review, monthly)
  maart_2026/       #   Monthly study plan with weekly/daily structure
    W{N}_{month}/   #     Week folders (W0_feb, W1_mrt, etc.)
      DD_MM/les.md  #       Daily lesson files with pre-filled resources
      week_review.md#       Weekly review template
    controle/       #     Baseline and monthly progress measurements
  archive/          #   Old daily practice files (pre-maart_2026)
  dutch_stories/    #   Dutch story subtitles and transcripts
other/              # Learning methodology notes and analysis
  language_learning_methods/  # Evgeniy 6-step, Alisher immersion, comparisons
scripts/            # Automation utilities (audio_to_anki.py, text_to_speech.py, etc.)
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

| Column           | Description                           |
| ---------------- | ------------------------------------- |
| Word             | Dutch word/phrase with article if noun |
| Example          | Dutch example sentence                |
| Translation      | Russian translation                   |
| TranslationExample | Russian translation of example sentence |
| Tags             | `link::thema{N}::taak{N}::A1`        |

**Dialog sentences** (zinnen) — 3 columns:

```
#separator:tab
#html:true
#tags column:3
```

| Column | Description                        |
| ------ | ---------------------------------- |
| Dutch  | Dutch sentence from the dialog     |
| Russian | Russian translation               |
| Tags   | `link::thema{N}::taak{N}::zinnen` |

Uitdrukkingen (vaste uitdrukkingen) use the 5-column word format with tag
suffix `::uitdrukkingen` instead of `::A1`.

### Card Templates

Front: `{{Front}} {{Audio}}` — Back: `{{FrontSide}}<hr id="answer">{{Back}}`

Audio references: `[sound:filename.mp3]` (ElevenLabs, Amazon Polly, or
audio_to_anki.py output)

## File Naming Conventions

| Pattern                            | Purpose                              |
| ---------------------------------- | ------------------------------------ |
| `opdracht_{N}.md`                  | Numbered exercises (thema 5, 8-9)    |
| `{N}_opdracht.md`                  | Numbered exercises (thema 6-7)       |
| `woordenlijst_pagina_{N}_anki.txt` | Vocabulary by page                   |
| `grammatica_{topic}.md`            | Grammar explanations                 |
| `taalhulp_{topic}.md`              | Grammar/phrase reference (non-Anki)  |
| `taalhulp_{topic}_anki.txt`        | Topic-specific flashcards            |
| `sententiae_{theme}_anki.txt`      | Sentence cards with audio            |
| `constructies_{topic}_anki.txt`    | Construction cards                   |
| `verhaal_{NN}_{title}.md`          | Story exercises                      |
| `dialog.md` / `dialog_{N}.md`     | Link course dialog transcripts       |
| `zinnen.md`                        | Link course sentence lists           |

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
- Alex: A2 (elementary), approaching B1
- Yulia: B1 level (Link course)

## Tutor Mode

When acting as a Dutch tutor (vocabulary questions, grammar explanations,
conversational practice), follow these rules:

### Session Flow

1. **Greeting** — начни на нидерландском, спроси тему занятия
2. **Warm-up review** — естественно вплети повторение ранее изученных слов и
   грамматики из текущей темы (проверь материалы в `de_opmaat/` или `link/`)
3. **Core work** — новый материал, вопросы, упражнения
4. **Wrap-up** — кратко подведи итог, что разобрали

### Response Algorithm (vocabulary & grammar questions)

При вопросе о слове, фразе или грамматической конструкции:

1. **Суть** — объясни значение через контекст, не просто перевод
2. **Нюансы** — формальность (formeel / informeel / slang), культурные
   особенности, типичные ошибки
3. **Грамматика** — род, число, управление, место в предложении — если релевантно
4. **3 примера** — из реальных ситуаций (формальная, бытовая, профессиональная),
   на нидерландском с переводом на русский
5. **Проверка** — спроси, всё ли понятно или нужны дополнения

### Content Generation (Anki cards, reading texts)

- Опирайся на уже изученную лексику и грамматику из пройденных тем
- Перед генерацией проверь woordenlijst и grammatica файлы текущей и предыдущих
  тем
- Отслеживай фокус текущей сессии: какие слова и конструкции разбирались
- Новые слова вводи дозированно, с опорой на знакомый контекст

### Tone

Дружелюбный, терпеливый, поддерживающий — как опытный репетитор. Никогда не
давай голый перевод без объяснения.

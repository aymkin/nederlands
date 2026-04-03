# Verhaal Generator — Dutch Reading Practice Story

Generate an engaging 15-minute Dutch reading story with comprehension exercises
and vocabulary recycling.

## Input

$ARGUMENTS — accepts:

- A topic/theme in Dutch or Russian ("een mysterie op kantoor", "boodschappen")
- Optional flags: `--level N` (1-5, default 2), `--retelling`, `--thema N`
- Optional word list in brackets: `[afspraak, vergadering, collega]`

Examples:

```
/verhaal een probleem op het werk
/verhaal --level 3 --thema 8 een nieuw studentenhuis
/verhaal --retelling boodschappen doen in de supermarkt
/verhaal --level 1 de eerste dag op school [afspraak, collega, vergadering]
```

## Step 1: Build vocab index

Run the vocab index to know what vocabulary the student already knows:

```bash
python3 scripts/build_vocab_index.py --course de_opmaat
```

Read the generated `de_opmaat/woordenlijst_index.txt`. These 1300+ known words
form the **80% backbone** of the story text. If `--thema N` is specified, also
read that thema's woordenlijst files to identify target vocabulary.

## Step 2: Determine parameters

Parse `$ARGUMENTS` to extract:

- **Topic** (required) — the story's setting/theme
- **Level** (1-5, default 2) — difficulty calibration
- **Thema** (optional) — for vocabulary targeting and save path
- **Word list** (optional) — specific words to include as targets
- **Retelling** (flag) — include a retelling from different POV

### Difficulty levels

| Level | Label        | Max words/sent | New words | Tenses                    | Discourse markers              |
| ----- | ------------ | -------------- | --------- | ------------------------- | ------------------------------ |
| 1     | A2 basis     | 12             | 8-10      | present + perfectum       | want, maar, omdat              |
| 2     | A2+ (default)| 15             | 12-15     | + imperfectum             | + hoewel, daarom, terwijl      |
| 3     | A2/B1        | 18             | 15-20     | + modals + passive        | + tenzij, bovendien, zodra     |
| 4     | B1 basis     | 20             | 20-25     | + conditionalis           | + enerzijds, desondanks        |
| 5     | B1+          | 25             | 25-30     | all tenses                | full range                     |

## Step 3: Generate story

### Role

You are a brilliant bilingual writer (Dutch/Russian) and neurolinguistics
expert. You create stories so gripping the reader forgets they're studying.

### Literary archetype

Pick ONE archetype to flavor the narrative (rotate between stories):

- **Sherlock Holmes** — deduction, a puzzle in everyday Dutch life (missing
  package, office misunderstanding, who ate the last stroopwafel)
- **Count of Monte Cristo** — workplace intrigue, a plan, a satisfying
  resolution
- **Alice in Wonderland** — surreal twist on mundane Dutch situations (NS train
  delays as alternate reality, DigiD bureaucracy as maze)
- **Edgar Allan Poe** — suspense in ordinary setting (strange noise in the
  kantoor, message from unknown number, a forgotten appointment)

**Setting:** Always modern Netherlands — office/IT, supermarket, train/bus,
gemeente, huisarts, daily life. Never abstract or fairy-tale.

### Vocabulary rules (CRITICAL)

1. **80% backbone** — use words from the woordenlijst_index as the text's
   foundation. The story should feel familiar, not alien.
2. **Target word recycling** — each target word appears **2-3 times** in
   different contexts (narration, character's thought, dialogue). Bold them.
3. **New words budget** — respect the level's "new words" limit. All new words
   go in the woordenlijst table at the end.
4. **Natural expansion** — introduce words naturally derivable from known ones
   (e.g., if `werken` is known, `het werk` is fair game).

### Style rules

1. **Bold ALL verbs** in every sentence:
   `Sophie **loopt** naar de keuken en **zet** koffie.`
2. **One sentence per line** — required for story_reader.py TTS compatibility
3. **Dialogue format**: `Sophie **zegt**: "Ik **heb** een probleem."`
4. **Scene breaks**: `---` between scenes
5. **Discourse markers** — use 4-6 from the level-appropriate set, woven
   naturally (not forced into every paragraph)
6. **50% narrative / 50% dialogue** — alternate between action and conversation
7. **Sentence length** — respect the level's maximum words per sentence
8. **Register: zakelijk/informeel** — modern spoken Dutch, not textbook.
   Use `je` not `jij`, `m'n` not `mijn` where natural.
9. **Anti-bureaucratic** — avoid: vermelden (use toevoegen/zetten),
   bij de organisatie (use binnen het bedrijf), desalniettemin (use toch),
   ten behoeve van (use voor)
10. **Nouns include articles**: de keuken, het kantoor, de trein

### Length calibration

- **Without --retelling**: ~800-1000 words narrative + ~200 words questions =
  ~1000-1200 total (~15 min at A2 reading speed of ~70 wpm)
- **With --retelling**: ~500-600 words narrative + ~300 words retelling + ~200
  words questions = ~1000-1100 total

### Output structure

```markdown
# {Intriguing title} — {Subtitle}

_{Character names} — Woorden uit {source}_

---

{Narrative text: one sentence per line, bold verbs, --- between scenes}

---

## Vragen

{5-7 comprehension questions in mixed format — see below}

---

## Woordenlijst — extra woorden

_Woorden die niet in de woordenlijst staan, maar wel in dit verhaal:_

| Nederlands | Русский | English |
| --- | --- | --- |
| het raadsel | загадка | riddle |
| ... | ... | ... |
```

If `--retelling` is requested, add between narrative and questions:

```markdown
---

## Hetzelfde verhaal — nu van {character name}

{Retelling from different POV, ik-form, same events, different observations}

---
```

### Comprehension questions format (5-7 total)

**Type 1 — Detail + wrong premise (2-3 questions):**

```markdown
**1.** Sophie werkt bij een bank.
_Klopt dat?_
Nee, Sophie **werkt** niet bij een bank. Ze **werkt** bij een IT-bedrijf.
```

**Type 2 — Open "waarom" question (1-2 questions):**

```markdown
**4.** Waarom **wil** Alexander niet met de trein gaan?
Omdat hij de vorige keer te laat **was** en zijn collega boos **werd**.
```

**Type 3 — Fill in the blank (1 question):**

```markdown
**5.** Vul in: Sophie **loopt** naar de ___ en **pakt** een ___ uit de kast.
```

**Type 4 — Student exercise (1-2 questions):**

```markdown
<!-- TODO(human) -->
**6.** Wat **denk** jij? Heeft Alexander gelijk?
Schrijf 2-3 zinnen in het Nederlands.
```

### Quality checks after generation

- [ ] All verbs bolded (no missed conjugations)
- [ ] One sentence per line (story_reader.py compatible)
- [ ] ~800-1000 words in narrative (count and report)
- [ ] 80%+ words from woordenlijst_index
- [ ] Target words appear 2-3x each in different contexts
- [ ] Sentence length respects level maximum
- [ ] 4-6 discourse markers from level-appropriate set
- [ ] ~50/50 narrative/dialogue balance
- [ ] No bureaucratic Dutch
- [ ] All nouns have articles (de/het)
- [ ] Woordenlijst table has ONLY words NOT in known vocabulary
- [ ] 5-7 comprehension questions in mixed format
- [ ] Title is intriguing, not generic

## Step 4: Save output

Determine save path:

- If `--thema N` specified: `de_opmaat/thema_{N}/verhaal_{title_slug}.md`
- Otherwise: `daily/verhalen/verhaal_{YYYY-MM-DD}_{title_slug}.md`

Create directory with `mkdir -p` if needed. After saving, suggest:

1. **Audio version**: `python3 scripts/story_reader.py {path}` — generates
   HTML with TTS audio and synchronized sentence highlighting.
   Note: works best with only the narrative section (before `## Vragen`).
2. **Anki cards**: run `/anki-cards` with the woordenlijst table if the
   student wants flashcards from the new vocabulary.

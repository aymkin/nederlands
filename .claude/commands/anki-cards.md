---
description:
  Anki woordenlijst cards for a Link, Link+ or De Opmaat thema/taak. Use when
  asked for woordenlijst cards, flashcards from a word list, or cards for a
  taak's new vocabulary.
argument-hint: link thema 13 taak 4 | <word list> | <path to source file>
---

# Anki Woordenlijst Card Generator

Generate Anki vocabulary cards in modern spoken Dutch, tagged so they land in
the right learner's deck.

## Input

$ARGUMENTS — either:

- A thema/taak reference: `link thema 13 taak 4`, `link_plus thema 7 taak 2`,
  `de_opmaat thema 9`
- A list of Dutch words/phrases
- A path to a source file (woordenlijst transcription, lesson notes)

## Step 1: Course, learner, level

| Input references | Course            | Learner | Examples written at                                        |
| ---------------- | ----------------- | ------- | ---------------------------------------------------------- |
| `link/`          | Link praktisch    | Alex    | A2 → B1                                                    |
| `link_plus/`     | Link+ theoretisch | Yulia   | **A1–A2** — the textbook is B1→B2, her actual level is not |
| `de_opmaat/`     | De Opmaat         | Alex    | A2                                                         |

## Step 2: Build the vocab index for that course

```bash
python3 scripts/build_vocab_index.py --course <link|link_plus|de_opmaat>
```

Read the `<course>/woordenlijst_index.txt` it writes — that one file replaces
reading 20+ deck files. One index per learner: recycling Alex's vocabulary into
Yulia's cards teaches her words she has never seen.

## Step 3: Get the word list

Where the words come from, by input branch:

- **word list in arguments** — use it as given
- **file path** — read that file
- **thema/taak reference** — look in `{course}/thema_{N}/taak_{K}/`: read
  `woordenlijst.md` when it exists (thema 8–9 only); otherwise read the scanned
  textbook page PDF sitting in that directory (`Read` with `pages`), which is
  the source for every other taak

Every word in that source list gets a card. Existing decks run 22–30 cards per
taak.

## Step 4: Generate the cards

Header, exactly — literal tabs, never spaces:

```
#separator:tab
#html:true
#columns:Word	Example	Translation	TranslationExample	Tags
#tags column:5
```

Tags, as they exist on disk rather than as the directory names suggest:

| Course       | Tag                               |
| ------------ | --------------------------------- |
| `link/`      | `link::thema{N}::taak{K}::A2`     |
| `link_plus/` | `link::thema{N}::taak{K}::A2`     |
| `de_opmaat/` | `opmaat::thema{N}::pagina{P}::A2` |

Yulia's cards keep the `link::` prefix: it is legacy from the `link/` →
`link_plus/` rename (commit `78f07e9`) and her scheduled Anki cards depend on
it, so `link_plus::` would orphan every one of them. De Opmaat thema 9 carries a
flat `opmaat::thema9::woordenlijst::A2` for the same historical reason — leave
both alone.

### Style rules (CRITICAL)

Target register **zakelijk/informeel** — modern spoken Dutch as heard in
Amsterdam or Utrecht today, the line a colleague, a friend or a shop assistant
actually says. A formal example fits only when the word itself is formal
(`de vergunning`, `de aanvraag`).

| Register  | Where it lives            | Markers                            |
| --------- | ------------------------- | ---------------------------------- |
| formeel   | gemeente letter, contract | Kunt u, gaarne, met betrekking tot |
| zakelijk  | work call, Slack          | Kun je, zou je, even kijken naar   |
| informeel | friends, WhatsApp         | Hé, zal ik, ff, lekker             |

1. **Natural contractions** where appropriate: `je` not `jij`, `m'n` not `mijn`,
   `'s ochtends` not `in de ochtend`
2. **Real situations**: rushing to work, choosing food, work calls, emotions,
   everyday requests — never `Het boek ligt op de tafel`
3. **Discourse markers** in ~50-60% of examples (1-2 per sentence, not every
   one): eigenlijk, gewoon, even, toch, wel, hoor, best, nou, echt, lekker
4. **Vocabulary recycling**: each example reuses 2-4 words from the index built
   in Step 2, **at least one of them from an earlier thema** — that is what
   re-activates older material. Words from this taak's own list count on top:
   letting the siblings carry each other (`de energie` → de vriezer) locks the
   block being learned today
5. **Natural expansion**: let context carry frequent words missing from the
   lists but obvious from known ones (kapot, vies, de lift, geverfd, `het werk`
   from `werken`, `een kop thee`). Sparingly — one per example at most.
6. **Unique situations**: each card gets its own scenario and its own sentence
   pattern
7. **Translation captures tone**, not literal meaning:
   - Good: "Я сейчас дико занят, извини" for "Ik heb het nu even heel druk"
   - Bad: "Я сейчас имею это очень занято"

### Say this instead

| Bureaucratic / bookish | Use instead                 | Why                           |
| ---------------------- | --------------------------- | ----------------------------- |
| vermelden              | toevoegen, zetten, noemen   | vermelden = official reports  |
| bij de organisatie     | binnen het bedrijf, bij ons | bij sounds like "visiting"    |
| implementatie          | de oplossing, de aanpak     | too abstract for speech       |
| Kunt je?               | Kun je?                     | -t drops in inversion with je |
| ten behoeve van        | voor                        | bureaucratic                  |
| desalniettemin         | toch, maar toch             | literary                      |

## Step 5: Save, then gate

| Course                | Path                                                                 |
| --------------------- | -------------------------------------------------------------------- |
| `link/`, `link_plus/` | `{course}/thema_{N}/taak_{K}/woordenlijst_thema{N}_taak{K}_anki.txt` |
| `de_opmaat/`          | `de_opmaat/thema_{N}/woordenlijst_pagina_{P}_anki.txt`               |

Run the mechanical gates. The first four print nothing when they pass; the fifth
prints its counts and exits 0:

```bash
f=<the saved file>
head -5 "$f" | sed -n l                 # separators must appear as \t
awk -F'\t' '!/^#/ && NF && NF!=5' "$f"  # every card line has 5 fields
grep -L '#html:true' "$f"               # header must declare html
rg -i 'rusland|россия' "$f"             # Voldemort grep
python3 scripts/check_recycling.py "$f" # rule 4, card by card
```

`check_recycling.py` names every example that recycles too little; rewrite those
examples rather than lowering its `--min`. Its count is a floor (it misses stem
changes like `reizen` ~ `reis`), so read a flagged example before trusting the
number.

Then confirm each of these holds:

- [ ] Every word from the Step 3 source list has a card
- [ ] Every Dutch noun carries its article (`het stokbrood`, `de buurt`)
- [ ] Every style rule above applied — register, markers in ~50-60% of examples,
      no repeated scenario, translations carry tone

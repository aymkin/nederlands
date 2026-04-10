# Anki Woordenlijst Card Generator

Generate high-quality Anki vocabulary cards in modern spoken Dutch.

## Input

$ARGUMENTS — either:

- A list of Dutch words/phrases to create cards for
- A path to a source file (woordenlijst PDF transcription, lesson notes, etc.)
- A thema/taak reference like "link thema 5 taak 2" or "de_opmaat thema 8"

## Step 1: Build vocab index

Before generating cards, always run the vocab index to know what vocabulary the
student already knows:

```bash
python3 scripts/build_vocab_index.py --course <link|de_opmaat|both>
```

Then read the generated index file to understand existing vocabulary.

## Step 2: Determine course and tags

- If input references `link/` → course is Link (Yulia, B1)
- If input references `de_opmaat/` → course is De Opmaat (Alex, A2)
- Tags format: `link::thema{N}::taak{N}::A2` or `de_opmaat::thema{N}::A2`

## Step 3: Generate cards

Output format (tab-separated, 5 columns):

```
#separator:tab
#html:true
#columns:Word	Example	Translation	TranslationExample	Tags
#tags column:5
```

### Style rules (CRITICAL)

**Target register: zakelijk/informeel** — modern spoken Dutch as heard in
Amsterdam or Utrecht today. Not a textbook, not a government letter.

1. **Natural contractions** where appropriate: `je` not `jij`, `m'n` not `mijn`,
   `'s ochtends` not `in de ochtend`
2. **Real situations**: rushing to work, choosing food, work calls, emotions,
   everyday requests — not "Het boek ligt op de tafel"
3. **Discourse markers** in ~50-60% of examples (1-2 per sentence, not every
   one): eigenlijk, gewoon, even, toch, wel, hoor, best, nou, echt, lekker
4. **Vocabulary recycling**: each example reuses 2-4 words from previous themas
5. **Unique situations**: no two cards share the same scenario
6. **Translation captures tone**, not literal meaning:
   - Good: "Я сейчас дико занят, извини" for "Ik heb het nu even heel druk"
   - Bad: "Я сейчас имею это очень занято"

### Anti-patterns to AVOID

| Bureaucratic / bookish | Use instead                 | Why                           |
| ---------------------- | --------------------------- | ----------------------------- |
| vermelden              | toevoegen, zetten           | vermelden = official reports  |
| bij de organisatie     | binnen het bedrijf, bij ons | bij sounds like "visiting"    |
| Kunt je? (with je)     | Kun je?                     | -t drops in inversion with je |
| ten behoeve van        | voor                        | bureaucratic                  |
| desalniettemin         | toch, maar toch             | literary                      |

### Quality checks after generation

- [ ] No bureaucratic patterns from the anti-pattern table
- [ ] Discourse markers present in ~50-60% of examples
- [ ] No repeated constructions/situations across cards
- [ ] Translations convey tone and emotion, not literal meaning
- [ ] Nouns include articles (de/het)
- [ ] Words from previous themas recycled in examples

## Step 4: Save output

Save the generated cards to the appropriate location following naming
convention: `woordenlijst_thema{N}_taak{N}_anki.txt`

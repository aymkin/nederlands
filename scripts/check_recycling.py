#!/usr/bin/env python3
"""
Checks vocabulary recycling in a woordenlijst Anki deck.

Style rule 4 of /anki-cards: every example reuses 2-4 words from the course
vocabulary index, at least one of them from an earlier thema.

What counts as a recycled word:
  - an entry of <course>/woordenlijst_index.txt, article stripped, matched as a
    whole word (multiword entries as a phrase)
  - NOT the card's own headword
  - NOT one of rule 3's ten discourse markers: those are mandated separately,
    so counting them would let a card pass on a word it had to contain anyway
  - NOT a closed-class function word (pronouns, articles, basic copulas)

Matching folds Dutch inflection the cheap way: doubled letters are collapsed
and the infinitive's -en is dropped, then an example token counts when it
starts with that stem (passen ~ past, maken ~ maakt, gemakkelijk ~
gemakkelijker, bon ~ bonnen). Stem changes it cannot see stay missed
(reizen ~ reis, invriezen ~ vries ... in), so the count remains a floor — read
a reported example before rewriting it.

Exit 1 when a card carries fewer than --min recycled words or none from an
earlier thema. Cards above --max are reported as warnings, not failures.

Usage:
    python3 scripts/check_recycling.py \
        link/thema_13/taak_1/woordenlijst_thema13_taak1_anki.txt
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Rule 3 mandates these, so they earn no recycling credit.
MARKERS = {
    "eigenlijk", "gewoon", "even", "toch", "wel", "hoor", "best", "nou",
    "echt", "lekker",
}

# Closed-class words: present in the index as A1 vocabulary, but matching them
# would score grammar, not recycling.
FUNCTION_WORDS = {
    "dat", "dit", "deze", "die", "een", "en", "hij", "zij", "ze", "we", "wij",
    "jij", "je", "jou", "jouw", "haar", "hem", "hen", "hun", "ons", "onze",
    "mij", "mezelf", "me", "uw", "zijn", "hebben", "worden", "niet", "niks",
    "niets", "maar", "want", "ook", "nu", "ja", "wat", "waar", "meer", "heel",
    "al", "er", "daar", "alle", "allemaal", "iedereen", "hetzelfde", "anders",
}


def find_index(deck: Path) -> Path:
    """The index lives at the root of the deck's own course directory."""
    try:
        course = deck.resolve().relative_to(PROJECT_ROOT).parts[0]
    except ValueError:
        sys.exit(f"✗ {deck} is outside {PROJECT_ROOT}")
    index = PROJECT_ROOT / course / "woordenlijst_index.txt"
    if not index.exists():
        sys.exit(
            f"✗ no index at {index}\n"
            f"  run: python3 scripts/build_vocab_index.py --course {course}"
        )
    return index


def normalize(entry: str) -> str:
    entry = re.sub(r"\s*\(.*?\)", "", entry.strip().lower())
    return re.sub(r"^(de|het|een)\s+", "", entry)


def parse_index(index: Path) -> dict[int, set[str]]:
    """Map thema number -> its vocabulary entries."""
    themas: dict[int, set[str]] = {}
    thema = None
    for line in index.read_text(encoding="utf-8").splitlines():
        if line.startswith("##"):
            m = re.search(r"thema[\s_](\d+)", line)
            thema = int(m.group(1)) if m else None
            continue
        if line.startswith("#") or not line.strip() or thema is None:
            continue
        for raw in line.split(", "):
            entry = normalize(raw)
            if entry and entry not in MARKERS and entry not in FUNCTION_WORDS:
                themas.setdefault(thema, set()).add(entry)
    return themas


def read_deck(deck: Path) -> tuple[int, list[tuple[str, str]]]:
    """Return the deck's own thema number and its (headword, example) rows."""
    rows = []
    thema = None
    for line in deck.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        rows.append((normalize(cols[0]), cols[1]))
        if thema is None and len(cols) >= 5:
            m = re.search(r"thema(\d+)", cols[4])
            if m:
                thema = int(m.group(1))
    if thema is None:
        m = re.search(r"thema(\d+)", deck.name)
        if not m:
            sys.exit(f"✗ cannot tell which thema {deck.name} belongs to")
        thema = int(m.group(1))
    return thema, rows


def fold(word: str) -> str:
    """Collapse doubled letters: maakt -> makt, passen -> pasen, bonnen -> bonen."""
    return re.sub(r"([a-zà-ÿ])\1", r"\1", word)


def stem(entry: str) -> str:
    """Cheap Dutch stem: drop the infinitive -en, then fold."""
    if len(entry) > 4 and entry.endswith("en"):
        entry = entry[:-2]
    return fold(entry)


def tokenize(text: str) -> set[str]:
    return {fold(t) for t in re.findall(r"[a-zà-ÿ']+", text.lower())}


def matched_tokens(entry: str, tokens: set[str]) -> set[str]:
    """Example tokens this entry accounts for; empty when it does not occur.

    A token counts when it starts with the entry's stem and is at most three
    letters longer, so `pas` reaches `past` and `paste` but not `paspoort`. A
    multiword entry needs every part present and accounts for all of them.
    """
    parts = entry.split()
    if len(parts) > 1:
        hits = set()
        for p in parts:
            hit = matched_tokens(p, tokens)
            if not hit:
                return set()
            hits |= hit
        return hits
    s = stem(entry)
    return {t for t in tokens if t.startswith(s) and len(t) <= len(s) + 3}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("deck", type=Path, help="the *_anki.txt deck to check")
    ap.add_argument("--index", type=Path, help="override the course index path")
    ap.add_argument("--min", type=int, default=2, dest="minimum")
    ap.add_argument("--max", type=int, default=4, dest="maximum")
    args = ap.parse_args()

    if not args.deck.exists():
        sys.exit(f"✗ no such deck: {args.deck}")

    themas = parse_index(args.index or find_index(args.deck))
    own_thema, rows = read_deck(args.deck)

    earlier = {w for n, words in themas.items() if n < own_thema for w in words}
    siblings = themas.get(own_thema, set()) - earlier

    failures, warnings, totals = [], [], []
    for head, example in rows:
        tokens = tokenize(example) - matched_tokens(head, tokenize(example))
        hit_e: set[str] = set()
        for w in earlier:
            hit_e |= matched_tokens(w, tokens)
        hit_s: set[str] = set()
        for w in siblings:
            hit_s |= matched_tokens(w, tokens)
        hit_s -= hit_e  # a word in both is credited to the earlier thema
        total = len(hit_e) + len(hit_s)
        totals.append((len(hit_e), len(hit_s)))

        if not hit_e:
            failures.append((head, example, "no word from an earlier thema"))
        elif total < args.minimum:
            failures.append((head, example, f"only {total} recycled word(s)"))
        elif total > args.maximum:
            warnings.append((head, example, f"{total} recycled words"))

    n = len(rows)
    avg_e = sum(e for e, _ in totals) / n
    avg_s = sum(s for _, s in totals) / n
    print(f"{args.deck}")
    print(f"  {n} cards · earlier themas {avg_e:.1f} words/example · "
          f"thema {own_thema} siblings {avg_s:.1f} words/example")

    for head, example, why in warnings:
        print(f"  ⚠ {head}: {why}\n      {example}")
    for head, example, why in failures:
        print(f"  ✗ {head}: {why}\n      {example}")

    if failures:
        print(f"  {len(failures)}/{n} cards fail rule 4")
        return 1
    print(f"  ✅ all {n} cards satisfy rule 4")
    return 0


if __name__ == "__main__":
    sys.exit(main())

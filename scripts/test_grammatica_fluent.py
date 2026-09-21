#!/usr/bin/env python3
"""Parser checks for grammatica_fluent.py. Stdlib only:

    python3 scripts/test_grammatica_fluent.py

The load-bearing one is wrap-invariance. The rule extracts are prose, and
anything that rewraps them (Prettier's proseWrap:always, a hand edit, an
editor's fill-paragraph) moves a `**Label:**` mid-line and splits a rule
across lines. While the field regexes were `^…$` anchored, that truncated 58
fields across 34 rules — and truncated silently: the parser still returned 34
rules and wrote half of each into the learner's deck. A crash would have been
the kinder failure, so the property is pinned here instead.
"""
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grammatica_fluent import parse_regels, sorteer, velden  # noqa: E402

REGELS = Path(__file__).resolve().parent.parent / "grammatica" / "regels"
VELDEN = ("title", "gloss", "regel", "russisch", "valkuil", "voorbeelden")


# Widths to rewrap at. 10**6 collapses each paragraph to one line, the layout
# the extracts were written in; the rest are plausible printWidths. Invariance
# has to hold across all of them, not at Prettier's current 80.
BREEDTES = (60, 80, 120, 10**6)


def herwikkel(md: str, breedte: int) -> str:
    """Rewrap prose paragraphs, leaving tables, lists and headings alone.

    Stands in for Prettier so the test needs no node_modules. Breaks at spaces
    only — `break_on_hyphens` would split `По-русски` mid-word, which no
    formatter does and which would test an imaginary hazard.
    """
    uit = []
    for blok in md.split("\n\n"):
        regels = blok.split("\n")
        structureel = any(r.lstrip().startswith(("|", "-", "#", ">", "```")) for r in regels)
        if structureel or not blok.strip():
            uit.append(blok)
        else:
            uit.append(textwrap.fill(" ".join(r.strip() for r in regels), breedte,
                                     break_on_hyphens=False, break_long_words=False))
    return "\n\n".join(uit)


def parse_tekst(md: str, naam: str, tmp: Path) -> dict:
    pad = tmp / naam
    pad.write_text(md, encoding="utf-8")
    return {r["id"]: r for r in parse_regels(pad)}


def test_wrap_invariant(tmp: Path) -> list[str]:
    fouten = []
    for bron in sorted(REGELS.glob("thema_*.md")):
        md = bron.read_text(encoding="utf-8")
        recht = parse_tekst(md, bron.name, tmp)
        for breedte in BREEDTES:
            gewikkeld = parse_tekst(herwikkel(md, breedte), bron.name, tmp)
            if set(recht) != set(gewikkeld):
                fouten.append(f"{bron.name} @{breedte}: набор правил разъехался")
                continue
            for rid in recht:
                for veld in VELDEN:
                    if recht[rid][veld] != gewikkeld[rid][veld]:
                        fouten.append(
                            f"{bron.name} {rid}.{veld} @{breedte}: "
                            f"{recht[rid][veld]!r} → {gewikkeld[rid][veld]!r}")
    return fouten


def test_velden_compleet() -> list[str]:
    """Every rule carries a Dutch formulation and a Russian gloss."""
    fouten = []
    for bron in sorted(REGELS.glob("thema_*.md")):
        for r in parse_regels(bron):
            for veld in ("regel", "russisch"):
                if not r[veld].strip():
                    fouten.append(f"{bron.name} {r['id']}: пустое поле {veld}")
    return fouten


def test_geen_markup() -> list[str]:
    """Card text is plain: no `**` or backticks leak through strip_md."""
    fouten = []
    for bron in sorted(REGELS.glob("thema_*.md")):
        for r in parse_regels(bron):
            for veld in ("regel", "russisch", "valkuil"):
                if "**" in r[veld] or "`" in r[veld]:
                    fouten.append(f"{bron.name} {r['id']}.{veld}: разметка в тексте")
    return fouten


def test_voorrang() -> list[str]:
    """7.1 and 7.2 lead: 1.1 and 4.1 cite them, so forward references must be 0."""
    alle = [r for bron in sorted(REGELS.glob("thema_*.md")) for r in parse_regels(bron)]
    volgorde = [r["id"] for r in sorteer(alle)]
    return ([] if volgorde[:2] == ["7.1", "7.2"]
            else [f"порядок начинается с {volgorde[:2]}, ожидалось ['7.1', '7.2']"])


def main() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    alles = []
    for naam, fn in (("инвариантность к переносу", lambda: test_wrap_invariant(tmp)),
                     ("поля заполнены", test_velden_compleet),
                     ("разметка вычищена", test_geen_markup),
                     ("VOORRANG соблюдён", test_voorrang)):
        fouten = fn()
        print(f"{'✓' if not fouten else '✗'} {naam}"
              + (f" — {len(fouten)}" if fouten else ""))
        for f in fouten[:8]:
            print(f"    {f}")
        alles += fouten
    print(f"\n{'всё зелено' if not alles else f'ошибок: {len(alles)}'}")
    return 1 if alles else 0


if __name__ == "__main__":
    raise SystemExit(main())

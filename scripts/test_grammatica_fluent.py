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

The second family pins the two rule sources apart. Link+ and the frames both
number their rules N.M; under one prefix the frames would be skipped as
already imported or would take ids Link+ reserves — again without an error.
"""
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grammatica_fluent  # noqa: E402
from grammatica_fluent import (  # noqa: E402
    KOP_RE, PROFIELEN, do_regels, parse_regels, sorteer)

GRAMMATICA = Path(__file__).resolve().parent.parent / "grammatica"
REGELS = GRAMMATICA / "regels"
SKELET = GRAMMATICA / "skelet"
VELDEN = ("title", "gloss", "regel", "russisch", "valkuil", "voorbeelden")
VANDAAG = "2026-10-08"


def bronnen() -> list[Path]:
    """Every rule file of every profile, in the folder the profile names."""
    return [b for naam, p in PROFIELEN.items()
            for b in sorted((GRAMMATICA / naam).glob(p["glob"]))]


def regels_van(map_: Path) -> list[dict]:
    p = PROFIELEN[map_.name]
    return [r for b in sorted(map_.glob(p["glob"])) for r in parse_regels(b)]


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
    for bron in bronnen():
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
    for bron in bronnen():
        for r in parse_regels(bron):
            for veld in ("regel", "russisch"):
                if not r[veld].strip():
                    fouten.append(f"{bron.name} {r['id']}: пустое поле {veld}")
    return fouten


def test_geen_markup() -> list[str]:
    """Card text is plain: no `**` or backticks leak through strip_md."""
    fouten = []
    for bron in bronnen():
        for r in parse_regels(bron):
            for veld in ("regel", "russisch", "valkuil"):
                if "**" in r[veld] or "`" in r[veld]:
                    fouten.append(f"{bron.name} {r['id']}.{veld}: разметка в тексте")
    return fouten


def test_koppen() -> list[str]:
    """Every `### ` heading is a rule heading. One with `-` for `·` would not
    match KOP_RE and its block would silently merge into the rule above."""
    fouten = []
    for bron in bronnen():
        for n, regel in enumerate(bron.read_text(encoding="utf-8").splitlines(), 1):
            if regel.startswith("### ") and not KOP_RE.match(regel):
                fouten.append(f"{bron.name}:{n}: заголовок не разобран: {regel!r}")
    return fouten


def test_voorrang() -> list[str]:
    """7.1 and 7.2 lead: 1.1 and 4.1 cite them, so forward references must be 0."""
    volgorde = [r["id"] for r in sorteer(regels_van(REGELS))]
    return ([] if volgorde[:2] == ["7.1", "7.2"]
            else [f"порядок начинается с {volgorde[:2]}, ожидалось ['7.1', '7.2']"])


def test_skelet_volgorde() -> list[str]:
    """Frames go 1.1 … 1.11 by number: no VOORRANG, no string sort (1.10 < 1.2)."""
    rules = regels_van(SKELET)
    volgorde = [r["id"] for r in sorteer(rules, PROFIELEN["skelet"]["voorrang"])]
    verwacht = [f"1.{n}" for n in range(1, 12)]
    return [] if volgorde == verwacht else [f"порядок {volgorde}, ожидалось {verwacht}"]


def test_skelet_voorbeelden() -> list[str]:
    """Each frame has ≥ 2 example sentences: the first two are the prime. Fewer
    would fall back to backtick fragments, which are not sentences."""
    fouten = []
    for r in regels_van(SKELET):
        zinnen = [v for v in r["voorbeelden"] if v.endswith((".", "?", "!"))]
        if len(zinnen) < 2:
            fouten.append(f"skelet {r['id']}: примеров-предложений {len(zinnen)}")
    return fouten


def test_skelet_prefix() -> list[str]:
    """A frames run next to gram_lp_1.1–1.9 adds 11 gram_sk_* and no gram_lp_*;
    a second run adds nothing."""
    sr = {"items": {f"gram_lp_1.{n}": {"id": f"gram_lp_1.{n}"} for n in range(1, 10)}}
    profiel = PROFIELEN["skelet"]
    fouten = []
    res = do_regels(sr, regels_van(SKELET), VANDAAG, 1, profiel)
    sk = sorted(k for k in sr["items"] if k.startswith("gram_sk_"))
    lp = [k for k in sr["items"] if k.startswith("gram_lp_")]
    if res["added"] != 11 or len(sk) != 11:
        fouten.append(f"добавлено {res['added']}, gram_sk_* {len(sk)}, ожидалось 11")
    if len(lp) != 9:
        fouten.append(f"gram_lp_* стало {len(lp)}, ожидалось 9")
    for k in sk:
        it = sr["items"][k]
        if not isinstance(it["difficulty"], str) or it["difficulty"] != "A2":
            fouten.append(f"{k}: difficulty {it['difficulty']!r}")
        if it["category"] != "grammatica_sk_kaders":
            fouten.append(f"{k}: category {it['category']!r}")
        if it["priority"] != "high":
            fouten.append(f"{k}: priority {it['priority']!r}, ожидалось high")
        if "SKELET.md" not in it["content"]:
            fouten.append(f"{k}: в content нет указателя на рецепт")
    if do_regels(sr, regels_van(SKELET), VANDAAG, 1, profiel)["added"] != 0:
        fouten.append("повторный прогон добавил карточки")
    return fouten


def test_lp_ongewijzigd() -> list[str]:
    """Link+ output is what it was before the profiles: golden check on 7.1."""
    sr = {"items": {}}
    do_regels(sr, regels_van(REGELS), VANDAAG, 2)
    it = sr["items"].get("gram_lp_7.1")
    if it is None:
        return ["gram_lp_7.1 не создан"]
    verwacht = {"category": "grammatica_lp_thema04", "difficulty": "A2",
                "bron": "regels/thema_04_lekker.md#7.1", "priority": "critical",
                "due_date": VANDAAG}
    fouten = [f"gram_lp_7.1.{k}: {it.get(k)!r}, ожидалось {v!r}"
              for k, v in verwacht.items() if it.get(k) != v]
    if "SKELET" in it["content"]:
        fouten.append("gram_lp_7.1: в content попал указатель рамок")
    if any(not isinstance(i["difficulty"], str) for i in sr["items"].values()):
        fouten.append("difficulty не строка")
    return fouten


def kaart(iid: str, due: str, reviews: int = 0, quality: int = 3, mastery: int = 0,
          prio: str = "high", eerste: str | None = None) -> dict:
    cat = "grammatica_sk_kaders" if "_sk_" in iid else (
        "grammatica_lp_thema04" if iid.startswith("gram_lp_7") else "grammatica_lp_thema01")
    it = {"id": iid, "type": "grammar_rule", "due_date": due, "total_reviews": reviews,
          "last_quality": quality, "mastery_level": mastery, "priority": prio,
          "category": cat}
    if eerste:
        it["review_history"] = [{"date": eerste, "quality": quality}]
    return it


def test_prioriteit() -> list[str]:
    """One intro a day per profile, one retry, the rest high or low; idempotent;
    cards that are not rules keep their priority."""
    gisteren, morgen = "2026-10-07", "2026-10-09"
    items = {k["id"]: k for k in (
        kaart("gram_sk_1.1", VANDAAG), kaart("gram_sk_1.2", gisteren),
        kaart("gram_sk_1.3", VANDAAG),
        kaart("gram_sk_1.4", gisteren, reviews=2, quality=1),
        kaart("gram_sk_1.5", VANDAAG, reviews=1, quality=2),
        kaart("gram_sk_1.6", VANDAAG, reviews=6, quality=5, mastery=3),
        kaart("gram_sk_1.7", morgen),
        kaart("gram_lp_1.1", gisteren), kaart("gram_lp_7.1", VANDAAG),
        kaart("gram_lp_7.2", VANDAAG, reviews=2, quality=4, prio="critical"))}
    items["freq_zin_x"] = {"id": "freq_zin_x", "type": "grammar_rule",
                           "due_date": VANDAAG, "priority": "critical"}
    items["grammar_y"] = {"id": "grammar_y", "type": "error_pattern",
                          "due_date": VANDAAG, "priority": "high"}
    sr = {"items": items}
    grammatica_fluent.prioriteit(sr, VANDAAG)
    verwacht = {"gram_sk_1.1": "critical",   # intro: first never-reviewed due frame
                "gram_sk_1.2": "high", "gram_sk_1.3": "high",   # one intro, not a pile
                "gram_sk_1.4": "critical",   # retry: oldest failed due card
                "gram_sk_1.5": "high",       # second failure waits
                "gram_sk_1.6": "low",        # mastered
                "gram_sk_1.7": "high",       # not due yet
                "gram_lp_7.1": "critical",   # VOORRANG leads the Link+ intro
                "gram_lp_1.1": "high",
                "gram_lp_7.2": "high",       # the eternal critical is lifted
                "freq_zin_x": "critical", "grammar_y": "high"}   # not rule cards
    fouten = [f"{k}: {items[k]['priority']}, ожидалось {v}"
              for k, v in verwacht.items() if items[k]["priority"] != v]
    if grammatica_fluent.prioriteit(sr, VANDAAG):
        fouten.append("повторный проход что-то поменял")
    # a frame first reviewed today means today's intro already happened
    sr2 = {"items": {k["id"]: k for k in (
        kaart("gram_sk_1.1", morgen, reviews=1, quality=4, eerste=VANDAAG),
        kaart("gram_sk_1.2", VANDAAG))}}
    grammatica_fluent.prioriteit(sr2, VANDAAG)
    if sr2["items"]["gram_sk_1.2"]["priority"] != "high":
        fouten.append("второе введение за день")
    return fouten


def test_onbekende_map(tmp: Path) -> list[str]:
    """An unknown folder stops the run before any data is read."""
    onbekend = tmp / "onbekend"
    onbekend.mkdir(exist_ok=True)
    (onbekend / "README.md").write_text("### 1.1 · Iets (что-то)\n", encoding="utf-8")
    argv, laden = sys.argv, grammatica_fluent.load
    sys.argv = ["grammatica_fluent.py", "--regels", str(onbekend), "--dry-run"]
    grammatica_fluent.load = lambda: (_ for _ in ()).throw(AssertionError("load() вызван"))
    try:
        grammatica_fluent.main()
    except SystemExit as e:
        return [] if "unknown rules folder" in str(e.code) else [f"выход: {e.code!r}"]
    except AssertionError as e:
        return [str(e)]
    finally:
        sys.argv, grammatica_fluent.load = argv, laden
    return ["неизвестная папка не остановила прогон"]


def main() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    alles = []
    for naam, fn in (("инвариантность к переносу", lambda: test_wrap_invariant(tmp)),
                     ("поля заполнены", test_velden_compleet),
                     ("разметка вычищена", test_geen_markup),
                     ("заголовки разобраны", test_koppen),
                     ("VOORRANG соблюдён", test_voorrang),
                     ("рамки по порядку 1.1…1.11", test_skelet_volgorde),
                     ("у рамок ≥ 2 примеров", test_skelet_voorbeelden),
                     ("рамки не задевают gram_lp_*", test_skelet_prefix),
                     ("Link+ без изменений", test_lp_ongewijzigd),
                     ("приоритеты правил на день", test_prioriteit),
                     ("неизвестная папка — отказ", lambda: test_onbekende_map(tmp))):
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

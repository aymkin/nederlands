#!/usr/bin/env python3
"""Checks for check_recycling.py. Stdlib only:

    python3 scripts/test_check_recycling.py

The first three reproduce what building the Link+ thema 8-9 decks turned up on
2026-09-28: the article het earned credit through heten, the marker hoor
through horen, and staat went unrecognised as staan. test_main_park replays the
warning that gave it away — "5 recycled words" on an example that recycles 4.
"""
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_recycling
from check_recycling import fold, matched_tokens, tokenize


def credited(entry, example):
    return matched_tokens(entry, tokenize(example))


def test_het_not_via_heten():
    assert credited("heten", "Ik loop graag in het park.") == set()


def test_hoor_not_via_horen():
    assert credited("horen", "Dat klopt wel, hoor.") == set()


def test_staat_via_staan():
    assert credited("staan", "De fiets staat buiten.") == {fold("staat")}


def test_heet_still_counts():
    # Articles are dropped before folding: folded, heet (hot) reads het.
    assert credited("heet", "Pas op, het strijkijzer is nog heet!") == {
        fold("heet")}


def test_hoort_still_counts():
    # Only the bare word goes, so the verb in `ik hoor` goes with the marker.
    assert credited("horen", "Hoor je dat? Hij hoort je niet.") == {
        fold("hoort")}


def test_phrase_with_article():
    # tokenize() never yields de, so the rest of the phrase must carry it.
    assert credited("op de hoogte", "Hou me even op de hoogte!") == {
        "op", fold("hoogte")}


def test_short_verbs():
    assert credited("gaan", "Ga je mee? Hij gaat ook.") == {"ga", fold("gaat")}
    assert credited("doen", "Wat doet ze?") == {"doet"}
    assert credited("zien", "Zie je dat? Ze ziet het niet.") == {"zie", "ziet"}


def test_short_stem_has_no_window():
    # ga, zie, sta, vanda with the usual three-letter window would take these.
    assert credited("gaan", "Kom je gauw? De gast wacht.") == set()
    assert credited("zien", "Ik ben ziek.") == set()
    assert credited("staan", "De stad is mooi.") == set()
    assert credited("vandaan", "Ik werk vandaag thuis.") == set()


def test_docstring_stems_unchanged():
    assert credited("passen", "Dat past niet.") == {"past"}
    assert credited("maken", "Hij maakt koffie.") == {fold("maakt")}
    assert credited("gemakkelijk", "Dit is gemakkelijker.") == {
        fold("gemakkelijker")}
    assert credited("bon", "Twee bonnen, graag.") == {fold("bonnen")}
    assert credited("pas", "Waar is mijn paspoort?") == set()


def test_main_park():
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp, "woordenlijst_index.txt")
        index.write_text("## thema 1 · taak 1\nik, in, graag, heten\n"
                         "## thema 3 · taak 1\nlopen\n", encoding="utf-8")
        deck = Path(tmp, "woordenlijst_thema8_taak1_anki.txt")
        deck.write_text("#separator:tab\nhet park\tIk loop graag in het park."
                        "\tпарк\tЯ люблю гулять в парке."
                        "\tlink::thema8::taak1::A2\n", encoding="utf-8")
        argv = ["check_recycling.py", str(deck), "--index", str(index),
                "--max", "3"]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out):
            code = check_recycling.main()
    assert code == 0 and "park: 4 recycled words" in out.getvalue(), \
        out.getvalue()


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

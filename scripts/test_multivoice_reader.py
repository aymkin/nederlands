"""Checks for the multivoice_reader cast-script parser.

Run: python3 scripts/test_multivoice_reader.py
"""

import tempfile
from pathlib import Path

import multivoice_reader as mv

HEAD = """---
title: Proef
cast:
  verteller: colette +0%
  Majoor: maarten -12%
---
"""


def _parse(body: str, head: str = HEAD):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.md"
        p.write_text(head + body, encoding="utf-8")
        return mv.parse_script(p)


def test_frontmatter_and_cast():
    meta, cast, _ = _parse("\nHallo.\n")
    assert meta["title"] == "Proef"
    assert cast["Majoor"] == ("maarten", "-12%")
    assert cast["verteller"] == ("colette", "+0%")


def test_narrator_chapter_and_role():
    _, _, b = _parse("""
# Eerste deel

Het is nacht. De dieren slapen.

**Majoor:** Lieve vrienden. Luister goed.
""")
    assert [x["type"] for x in b] == ["chapter", "speech", "speech"]
    assert b[0]["title"] == "Eerste deel"
    assert b[1]["role"] == "" and len(b[1]["sentences"]) == 2
    assert b[2]["role"] == "Majoor"
    assert b[2]["sentences"] == ["Lieve vrienden.", "Luister goed."]


def test_verse_keeps_lines_and_uses_verse_role():
    head = HEAD.replace("title: Proef", "title: Proef\nverse_role: Majoor")
    _, _, b = _parse("""
> Lieve dieren, luister goed,
> een mooie tijd breekt aan.
""", head)
    assert b[0]["verse"] is True
    assert b[0]["role"] == "Majoor"
    assert b[0]["sentences"] == ["Lieve dieren, luister goed,",
                                 "een mooie tijd breekt aan."]


def test_sentence_split_keeps_numbers_and_quotes():
    assert mv.split_sentences("Hij is 12 jaar oud. Klopt dat?") == [
        "Hij is 12 jaar oud.", "Klopt dat?"]
    assert mv.split_sentences("Niet een! Maar twee.") == [
        "Niet een!", "Maar twee."]
    # a colon must not split
    assert len(mv.split_sentences("Vier dieren: drie honden en de kat.")) == 1


def test_multiline_paragraph_is_one_segment():
    _, _, b = _parse("\nEen zin\ndie doorloopt. En nog een.\n")
    assert len(b) == 1
    assert b[0]["sentences"] == ["Een zin die doorloopt.", "En nog een."]


def test_rejects_missing_frontmatter():
    try:
        _parse("Hallo.\n", head="")
    except ValueError as e:
        assert "frontmatter" in str(e)
    else:
        raise AssertionError("should have rejected a script with no frontmatter")


def test_rejects_unknown_role():
    try:
        _parse("\n**Napoleon:** Ik ben de baas.\n")
    except ValueError as e:
        assert "Napoleon" in str(e)
    else:
        raise AssertionError("should have rejected a role missing from the cast")


def test_rejects_bad_cast_line():
    bad = "---\ntitle: X\ncast:\n  Majoor: klaas -12%\n---\n"
    try:
        _parse("\nHallo.\n", head=bad)
    except ValueError as e:
        assert "bad cast line" in str(e)
    else:
        raise AssertionError("should have rejected an unknown voice name")


def test_scene_rule_becomes_a_break():
    _, _, blocks = _parse("\nEerste scene.\n\n---\n\nTweede scene.\n")
    assert [b["type"] for b in blocks] == ["speech", "break", "speech"]


def test_stops_at_exercise_headings():
    _, _, blocks = _parse(
        "\nHet verhaal.\n\n## Vragen\n\n**1.** Klopt dat?\n")
    assert [b["type"] for b in blocks] == ["speech"]
    assert blocks[0]["sentences"] == ["Het verhaal."]


def test_skips_metadata_comments_and_tables():
    _, _, blocks = _parse(
        "\n_Yulia — thema 7_\n\n<!-- TODO(human) -->\n\n"
        "| nl | ru |\n\nHet verhaal.\n")
    assert [b["type"] for b in blocks] == ["speech"]


def test_bold_survives_to_html_but_not_to_speech():
    sentence = "Ik **heb** koorts."
    assert mv.md_to_html(sentence) == "Ik <b>heb</b> koorts."
    assert mv.strip_md(sentence) == "Ik heb koorts."


def test_bold_paragraph_is_not_mistaken_for_a_role():
    _, _, blocks = _parse("\n**Stress**, **stress**, **stress**.\n")
    assert blocks[0]["role"] == ""


def test_slugify_is_css_safe():
    assert mv.slugify("Majoor zingt") == "majoor-zingt"
    assert mv.slugify("De eenden") == "de-eenden"
    assert mv.slugify("") == "verteller"


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

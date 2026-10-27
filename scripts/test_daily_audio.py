"""Checks for the daily_audio pair parser, four-part plan and offline build (no network).

The build test fakes edge-tts with ffmpeg sine tones, so it needs ffmpeg/ffprobe.

Run: python3 scripts/test_daily_audio.py
"""

import os
import subprocess
import tempfile
from pathlib import Path

import daily_audio as da

PAIRS = [
    ("Gisteren heb ik ticket 2553 afgerond.", "Вчера я закончил тикет 2553."),
    ("Daar ben ik nu mee bezig.", "Сейчас я над ним работаю."),
    ("Geen blokkades.", "Блокеров нет."),
]


def _parse(body: str):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dag.txt"
        p.write_text(body, encoding="utf-8")
        return da.parse_pairs(p)


def _fails(body: str) -> str:
    try:
        _parse(body)
    except ValueError as e:
        return str(e)
    raise AssertionError("ValueError expected")


def _spoken(seg):
    return [s for s in seg if isinstance(s, da.Spraak)]


def _part(seg, i):
    """Сегменты части i (1-based): от метки «deel i» до метки следующей части."""
    marks = [k for k, s in enumerate(seg) if isinstance(s, da.Merk)]
    start = marks[i - 1]
    end = marks[i] if i < len(marks) else len(seg)
    return seg[start:end]


# ─── parse_pairs ──────────────────────────────────────────────────────


def test_parse_pairs_blocks_and_comments():
    pairs = _parse("# dag 28.10\n\nGeen blokkades.\nБлокеров нет.\n\n\n"
                   "Daar ben ik nu mee bezig.\n  Сейчас   я над ним работаю.  \n")
    assert pairs == [("Geen blokkades.", "Блокеров нет."),
                     ("Daar ben ik nu mee bezig.", "Сейчас я над ним работаю.")]


def test_parse_pairs_last_block_without_trailing_blank_line():
    assert _parse("Geen blokkades.\nБлокеров нет.") == [PAIRS[2]]


def test_parse_pairs_rejects_odd_block_with_line_number():
    msg = _fails("Geen blokkades.\nБлокеров нет.\n\nDaar ben ik nu mee bezig.\n")
    assert "dag.txt:4" in msg and "1 строк" in msg


def test_parse_pairs_rejects_swapped_languages():
    assert "кириллица" in _fails("Блокеров нет.\nGeen blokkades.\n")
    assert "нет кириллицы" in _fails("Geen blokkades.\nGeen blokkades.\n")


def test_parse_pairs_rejects_empty_file():
    assert "нет ни одной пары" in _fails("# alleen commentaar\n\n")


# ─── pauze ────────────────────────────────────────────────────────────


def test_pauze_scales_with_the_sentence_and_never_cuts_it_short():
    assert abs(da.pauze(6.0) - (1.6 * 6.0 + 2.0)) < 1e-9
    assert da.pauze(6.0, factor=2.0) > da.pauze(6.0)
    assert da.pauze(0.5) > 0.5 * 1.6  # даже на самую короткую фразу есть запас


# ─── plan ─────────────────────────────────────────────────────────────


def test_part1_is_dutch_normal_in_order():
    spoken = [s for s in _part(da.plan(PAIRS), 1) if isinstance(s, da.Spraak)]
    assert spoken[0].taal == "ru" and "первая" in spoken[0].tekst
    assert [(s.taal, s.tekst, s.rate) for s in spoken[1:]] == [
        ("nl", n, da.NORMAAL) for n, _ in PAIRS]


def test_part2_is_dutch_then_russian_per_sentence():
    spoken = [s for s in _part(da.plan(PAIRS), 2) if isinstance(s, da.Spraak)][1:]
    assert [(s.taal, s.tekst) for s in spoken] == [
        x for n, r in PAIRS for x in (("nl", n), ("ru", r))]


def test_part3_is_dutch_slow():
    spoken = [s for s in _part(da.plan(PAIRS), 3) if isinstance(s, da.Spraak)][1:]
    assert [(s.taal, s.tekst, s.rate) for s in spoken] == [
        ("nl", n, da.LANGZAAM) for n, _ in PAIRS]


def test_part4_is_two_rounds_of_ru_pause_nl():
    seg = da.plan(PAIRS)
    body = [s for s in seg[seg.index(da.Merk("deel 4")):]
            if isinstance(s, (da.Spraak, da.Antwoord))]
    triples = [s for s in body if not (isinstance(s, da.Spraak)
                                       and s.tekst in (da.DEEL[3], da.RONDE_TWEE))]
    assert len(triples) == 2 * len(PAIRS) * 3
    one_round = [("ru", r) if isinstance(s, da.Spraak) and s.taal == "ru"
                 else ("pauze", n) if isinstance(s, da.Antwoord)
                 else ("nl", s.tekst)
                 for (n, r), chunk in zip(PAIRS * 2, zip(*[iter(triples)] * 3))
                 for s in chunk]
    assert one_round[:9] == [x for n, r in PAIRS
                             for x in (("ru", r), ("pauze", n), ("nl", n))]
    assert one_round[9:] == one_round[:9]


def test_part4_answer_pause_follows_the_russian_cue_and_precedes_the_check():
    seg = da.plan(PAIRS)
    for k, s in enumerate(seg):
        if isinstance(s, da.Antwoord):
            assert isinstance(seg[k - 1], da.Spraak) and seg[k - 1].taal == "ru"
            assert seg[k + 1] == da.Spraak("nl", s.tekst, da.NORMAAL)


def test_plan_synthesises_each_distinct_text_once():
    distinct = {s for s in da.plan(PAIRS) if isinstance(s, da.Spraak)}
    # NL нормально и медленно + RU по предложению + 5 объявлений (4 части + 2-й круг)
    assert len(distinct) == 3 * len(PAIRS) + 5


def test_plan_ends_with_speech_not_silence():
    assert isinstance(da.plan(PAIRS)[-1], da.Spraak)


def test_marks_name_every_part_in_order():
    labels = [s.label for s in da.plan(PAIRS) if isinstance(s, da.Merk)]
    assert labels == ["deel 1", "deel 2", "deel 3", "deel 4", "deel 4, круг 2"]


def test_trim_removes_silence_at_both_ends():
    """edge-tts даёт ≈0,25 с тишины спереди и ≈0,9 с сзади; паузы считаются от речи."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1,adelay=500|500,apad=pad_dur=1",
                        "-ar", "24000", "-ac", "1", "-q:a", "4", str(p), "-y"],
                       check=True)
        before = da.duur(p)
        da._trim(p)
        after = da.duur(p)
    assert before > 2.4
    assert 1.0 <= after <= 1.3, after  # речь 1,0 с + запас 2×0,08 с


def _fake_synth(text, voice, rate, path, tries=2):
    sec = 0.5 + 0.06 * len(text)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={sec:.2f}", "-ar", "24000",
                    "-ac", "1", "-q:a", "4", str(path), "-y"], check=True)


def test_build_with_relative_out_path_lands_where_asked():
    """Регресс 2026-10-27: ffmpeg шёл с cwd=tmp, и относительный --out терялся."""
    real, here = da.synth, os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        try:
            da.synth = _fake_synth
            os.chdir(d)
            Path("sub").mkdir()
            marks = da.build(da.plan(PAIRS), "maarten", "svetlana", Path("sub/dag.mp3"))
            assert Path("sub/dag.mp3").stat().st_size > 5 * 1024
            assert not list(Path("sub").glob(".*.part"))
            assert [m[0] for m in marks][0] == "deel 1"
        finally:
            da.synth = real
            os.chdir(here)


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

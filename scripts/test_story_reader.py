"""Checks for story_reader's word-stream → sentence-span alignment.

Run: python3 scripts/test_story_reader.py
"""

import story_reader as sr


def _words(*specs):
    """[('Majoor', 0.1, 0.7), ...] → word-event dicts."""
    return [{"text": t, "start": s, "end": e} for t, s, e in specs]


def test_speakable_tokens_ignores_punctuation():
    assert sr._speakable_tokens("Hij is 12 jaar oud.") == 5
    assert sr._speakable_tokens("'Lieve vrienden,' zegt hij.") == 4
    assert sr._speakable_tokens("Ja — nee.") == 2
    assert sr._speakable_tokens("**Majoor** komt.") == 2


def test_exact_walk():
    sentences = ["Majoor komt.", "Hij is oud."]
    words = _words(
        ("Majoor", 0.0, 0.5), ("komt", 0.5, 1.0),
        ("Hij", 2.0, 2.3), ("is", 2.3, 2.5), ("oud", 2.5, 3.0),
    )
    assert sr.align_timings(sentences, words) == [
        {"start": 0.0, "end": 1.0},
        {"start": 2.0, "end": 3.0},
    ]


def test_spans_stay_ordered_and_nonoverlapping():
    sentences = ["Een twee.", "Drie vier vijf.", "Zes."]
    words = _words(*[(f"w{i}", i * 1.0, i * 1.0 + 0.8) for i in range(6)])
    t = sr.align_timings(sentences, words)
    assert len(t) == len(sentences)
    assert all(t[i]["end"] <= t[i + 1]["start"] for i in range(len(t) - 1))
    assert t[0]["start"] == 0.0 and t[-1]["end"] == 5.8


def test_rescales_on_token_mismatch():
    """A short event stream must still span every sentence, not drift."""
    sentences = ["Een twee drie.", "Vier vijf zes."]
    words = _words(("a", 0.0, 1.0), ("b", 1.0, 2.0))  # 6 tokens, 2 events
    t = sr.align_timings(sentences, words)
    assert len(t) == 2
    assert t[0]["end"] <= t[1]["start"]
    assert t[-1]["end"] == 2.0


def test_empty_sentence_gets_zero_span():
    t = sr.align_timings(["Hallo.", "**", "Doei."], _words(
        ("Hallo", 0.0, 0.5), ("Doei", 1.0, 1.5),
    ))
    assert t[1]["start"] == t[1]["end"]
    assert t[2] == {"start": 1.0, "end": 1.5}


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

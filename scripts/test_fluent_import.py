import json
import tempfile
from pathlib import Path

import fluent_import as fi


def test_unit_prefix():
    assert fi.unit_prefix("link", "thema_8") == "link_t8_"
    assert fi.unit_prefix("de_opmaat", "thema_12") == "de_opmaat_t12_"


def test_date_helpers():
    assert fi.tomorrow("2026-06-26") == "2026-06-27"
    assert fi.date_plus_days("2026-06-26", 7) == "2026-07-03"


def test_active_unit_ok():
    m = {"course": "link", "units": [
        {"id": "thema_8", "status": "active"},
        {"id": "thema_9", "status": "locked"}]}
    assert fi.active_unit(m)["id"] == "thema_8"


def test_active_unit_requires_exactly_one():
    m = {"course": "link", "units": [
        {"id": "thema_8", "status": "done"},
        {"id": "thema_9", "status": "locked"}]}
    try:
        fi.active_unit(m)
        assert False, "expected ValueError"
    except ValueError:
        pass
    m2 = {"course": "link", "units": [
        {"id": "thema_8", "status": "active"},
        {"id": "thema_9", "status": "active"}]}
    try:
        fi.active_unit(m2)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_load_manifest():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "curriculum.json"
        p.write_text(json.dumps({"course": "link", "units": []}))
        assert fi.load_manifest(Path(d))["course"] == "link"


def test_slug():
    assert fi.slug("de buurt") == "de-buurt"
    assert fi.slug("'s morgens") == "s-morgens"


def test_parse_woordenlijst():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "woordenlijst_thema8_taak1_anki.txt"
        p.write_text(
            "#separator:tab\n#html:true\n#tags column:5\n"
            "de buurt\tIk woon in de buurt.\tрайон\tЯ живу в районе.\tlink::thema8\n"
            "lopen\tIk loop.\tходить\tЯ хожу.\tlink::thema8\n",
            encoding="utf-8")
        rows = fi.parse_woordenlijst(p)
        assert rows == [("de buurt", "район"), ("lopen", "ходить")]


def test_vocab_items():
    with tempfile.TemporaryDirectory() as d:
        unit_dir = Path(d) / "thema_8" / "taak_1"
        unit_dir.mkdir(parents=True)
        (unit_dir / "woordenlijst_thema8_taak1_anki.txt").write_text(
            "#separator:tab\n"
            "de buurt\tIk woon in de buurt.\tрайон\tЯ живу.\tlink::thema8\n",
            encoding="utf-8")
        unit = {"id": "thema_8", "status": "active"}
        items = fi.vocab_items("link", unit, Path(d))
        assert len(items) == 1
        it = items[0]
        assert it["item_id"] == "link_t8_voc_taak1_de-buurt"
        assert it["item_type"] == "vocabulary"
        assert it["content"] == "de buurt"
        assert it["answer"] == "район"
        assert it["category"] == "link_thema8"


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

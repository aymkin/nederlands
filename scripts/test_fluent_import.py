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
            "kapot\ttwee kolommen\n"
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
        assert it["priority"] == "medium"


GRAMMAR_SAMPLE = """# Thema X

## 2.1 Het werkwoord: ik, we + werkwoord

### Regel
| Persoon | Vorm |
|---|---|
| ik | **werk** |

### Voorbeelden uit oefeningen
- Ik **werk** in Rotterdam.
- We **werken** in Rotterdam.

## 3.1 Alleen een tabel

### Regel
| a | b |
|---|---|
"""


def test_parse_grammar_clozes_basic():
    items, skipped = fi.parse_grammar_clozes(GRAMMAR_SAMPLE, "all", "link_t8_")
    assert len(items) == 2
    first = items[0]
    assert first["item_id"] == "link_t8_gram_2.1_1"
    assert first["item_type"] == "grammar_rule"
    assert first["answer"] == "werk"
    assert first["content"] == "Ik ___ in Rotterdam. (Het werkwoord: ik, we + werkwoord)"
    # модуль 3.1 без жирных примеров — пропущен
    assert any("3.1" in s for s in skipped)


def test_parse_grammar_clozes_module_filter():
    items, skipped = fi.parse_grammar_clozes(GRAMMAR_SAMPLE, ["3.1"], "link_t8_")
    assert items == []  # 2.1 отфильтрован, 3.1 без примеров
    assert any("3.1" in s for s in skipped)


def test_add_items_idempotent():
    sr = {"items": {}, "review_queue": {}, "metadata": {}}
    items = [{"item_id": "link_t8_voc_taak1_de-buurt", "item_type": "vocabulary",
              "content": "de buurt", "answer": "район", "category": "link_thema8",
              "priority": "medium"}]
    assert fi.add_items(sr, items, "2026-06-26") == 1
    assert fi.add_items(sr, items, "2026-06-26") == 0  # второй раз — 0
    it = sr["items"]["link_t8_voc_taak1_de-buurt"]
    assert it["due_date"] == "2026-06-27"
    assert it["easiness_factor"] == 2.5
    assert it["mastery_level"] == 0


def test_rebuild_queue_buckets():
    sr = {"items": {
        "a": {"due_date": "2026-06-25"},   # < today
        "b": {"due_date": "2026-06-27"},   # tomorrow
        "c": {"due_date": "2026-06-30"},   # this_week
        "d": {"due_date": "2026-08-01"},   # later
        "e": {"due_date": "2026-06-26"},   # == today  -> today bucket
        "f": {"due_date": "2026-07-03"},   # == today+7 -> this_week upper edge
    }, "review_queue": {}, "metadata": {}}
    fi.rebuild_queue(sr, "2026-06-26")
    q = sr["review_queue"]
    assert q["today"] == ["a", "e"]
    assert q["tomorrow"] == ["b"]
    assert q["this_week"] == ["c", "f"]
    assert q["later"] == ["d"]
    assert sr["metadata"]["total_items_tracked"] == 6


def test_write_sr_backs_up_and_writes():
    with tempfile.TemporaryDirectory() as d:
        sr_path = Path(d) / "spaced-repetition.json"
        sr_path.write_text(json.dumps({"items": {}, "metadata": {}}))
        fi.write_sr({"items": {"x": {}}, "metadata": {}}, sr_path)
        assert json.loads(sr_path.read_text())["items"] == {"x": {}}
        backups = list((Path(d) / ".backups").rglob("spaced-repetition.json"))
        assert len(backups) == 1  # старая версия сохранена
        # first write to a non-existent path: file created, no backup needed
        fresh = Path(d) / "sub" / "spaced-repetition.json"
        fresh.parent.mkdir()
        fi.write_sr({"items": {"y": {}}, "metadata": {}}, fresh)
        assert json.loads(fresh.read_text())["items"] == {"y": {}}


def _make_repo(d):
    root = Path(d)
    (root / "link" / "thema_8" / "taak_1").mkdir(parents=True)
    (root / "link" / "gramatica").mkdir(parents=True)
    (root / "link" / "thema_8" / "taak_1" /
     "woordenlijst_thema8_taak1_anki.txt").write_text(
        "#separator:tab\nde buurt\tIk woon in de buurt.\tрайон\tЯ живу.\tt\n",
        encoding="utf-8")
    (root / "link" / "gramatica" / "grammatica_thema08_in_mijn_buurt.md").write_text(
        "## 1.1 Test\n\n### Voorbeelden uit oefeningen\n- Ik **werk** hier.\n",
        encoding="utf-8")
    (root / "link" / "curriculum.json").write_text(json.dumps({
        "course": "link", "units": [
            {"id": "thema_8", "grammar_file": "grammatica_thema08_in_mijn_buurt.md",
             "grammar_modules": "all", "status": "active"}]}), encoding="utf-8")
    return root


def test_do_import_end_to_end_and_idempotent():
    with tempfile.TemporaryDirectory() as d:
        root = _make_repo(d)
        sr_path = root / "spaced-repetition.json"
        sr_path.write_text(json.dumps({"items": {}, "metadata": {}}))
        s1 = fi.do_import("link", root, sr_path, "2026-06-26")
        assert s1["vocab"] == 1 and s1["grammar"] == 1 and s1["added"] == 2
        sr = json.loads(sr_path.read_text())
        assert "link_t8_voc_taak1_de-buurt" in sr["items"]
        assert "link_t8_gram_1.1_1" in sr["items"]
        assert sr["review_queue"]["tomorrow"]  # due завтра
        s2 = fi.do_import("link", root, sr_path, "2026-06-26")
        assert s2["added"] == 0  # idempotent


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

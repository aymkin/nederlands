#!/usr/bin/env python3
"""Проверки fluent_rebuild_queue.py. Запуск: python3 scripts/test_fluent_rebuild_queue.py

Всё через CLI — это единственный интерфейс скрипта. Главный тест —
test_lag_detected: воспроизводит лаг, ради которого скрипт написан.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "fluent_rebuild_queue.py"
TODAY = "2026-09-21"
EMPTY = {"today": [], "tomorrow": [], "this_week": [], "later": []}


def run(root, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--data-dir", str(root), "--date", TODAY, *args],
        capture_output=True, text=True)


def setup(d, items, queue=EMPTY):
    p = Path(d) / "spaced-repetition.json"
    p.write_text(json.dumps({"metadata": {}, "daily_limits": {"review_items_per_day": 30},
                             "items": items, "review_queue": queue},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def test_lag_detected():
    """Карточка созрела сегодня, но бакеты строились вчера."""
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, {"rule_7_1": {"due_date": TODAY}, "later": {"due_date": "2026-09-30"}},
                  dict(EMPTY, tomorrow=["rule_7_1"], later=["later"]))
        r = run(d, "--apply")
        assert r.returncode == 0, r.stderr
        assert json.loads(p.read_text())["review_queue"]["today"] == ["rule_7_1"]


def test_noop_when_fresh_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, {"a": {"due_date": TODAY}}, dict(EMPTY, today=["a"]))
        before = p.read_text()
        r = run(d, "--apply")
        assert "ничего не делаю" in r.stdout
        assert p.read_text() == before
        assert not (Path(d) / ".backups").exists()


def test_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, {"a": {"due_date": TODAY}}, dict(EMPTY, tomorrow=["a"]))
        before = p.read_text()
        r = run(d)
        assert "сухой прогон" in r.stdout
        assert p.read_text() == before
        assert not (Path(d) / ".backups").exists()


def test_apply_backs_up_first():
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, {"a": {"due_date": TODAY}}, dict(EMPTY, tomorrow=["a"]))
        before = p.read_text()
        assert run(d, "--apply").returncode == 0
        backups = list((Path(d) / ".backups").glob("pre-rebuild-*"))
        assert len(backups) == 1
        assert (backups[0] / p.name).read_text() == before


def test_apply_leaves_fsrs_untouched():
    items = {"a": {"due_date": TODAY, "stability": 8.3, "repetitions": 1,
                   "mastery_level": 2, "priority": "high"}}
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, items, dict(EMPTY, tomorrow=["a"]))
        assert run(d, "--apply").returncode == 0
        out = json.loads(p.read_text())
        assert out["items"] == items
        assert out["daily_limits"] == {"review_items_per_day": 30}


def test_missing_review_queue_key():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "spaced-repetition.json"
        p.write_text(json.dumps({"items": {"a": {"due_date": TODAY}}}), encoding="utf-8")
        assert run(d, "--apply").returncode == 0
        assert json.loads(p.read_text())["review_queue"]["today"] == ["a"]


def test_rejects_non_iso_date():
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, {"a": {"due_date": TODAY}})
        before = p.read_text()
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", d, "--date", "21-09-2026", "--apply"],
            capture_output=True, text=True)
        assert r.returncode == 2
        assert p.read_text() == before


def test_missing_file_exits_2():
    with tempfile.TemporaryDirectory() as d:
        assert run(d).returncode == 2


def regel(due, reviews=0, quality=3, prio="high", cat="grammatica_sk_kaders"):
    return {"type": "grammar_rule", "due_date": due, "total_reviews": reviews,
            "last_quality": quality, "mastery_level": 0, "priority": prio,
            "category": cat}


PRIO_ITEMS = {
    "gram_sk_1.1": regel(TODAY),
    "gram_sk_1.2": regel(TODAY),
    "gram_lp_7.1": regel(TODAY, 3, 4, "critical", "grammatica_lp_thema04"),
    "grammar_x": {"type": "error_pattern", "due_date": TODAY, "priority": "high"},
}


def test_prioriteit_on_apply():
    """Одно новое правило дня — critical, вечный critical снят, остальное не тронуто."""
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, PRIO_ITEMS)
        r = run(d, "--apply")
        assert r.returncode == 0, r.stderr
        out = json.loads(p.read_text())["items"]
        assert out["gram_sk_1.1"]["priority"] == "critical"
        assert out["gram_sk_1.2"]["priority"] == "high"
        assert out["gram_lp_7.1"]["priority"] == "high"
        assert out["grammar_x"]["priority"] == "high"
        assert "приоритеты правил" in r.stdout


def test_prioriteit_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        p = setup(d, PRIO_ITEMS)
        before = p.read_text()
        r = run(d)
        assert "gram_sk_1.1" in r.stdout and "сухой прогон" in r.stdout
        assert p.read_text() == before


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

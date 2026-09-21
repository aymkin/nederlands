#!/usr/bin/env python3
"""Проверки fluent_rebuild_queue.py.

Запуск: python3 scripts/test_fluent_rebuild_queue.py

Главная из них — test_lag_detected: воспроизводит тот самый однодневный
лаг, ради которого скрипт и написан (карточка с due=сегодня застряла в
бакете tomorrow, потому что бакеты строились вчера).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fluent_import as fi  # noqa: E402
import fluent_rebuild_queue as rq  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "fluent_rebuild_queue.py"
TODAY = "2026-09-21"


def _sr(items: dict, queue: dict | None = None) -> dict:
    return {
        "metadata": {"algorithm": "FSRS-6", "total_items_tracked": len(items)},
        "daily_limits": {"review_items_per_day": 30},
        "items": items,
        "review_queue": queue if queue is not None
        else {"today": [], "tomorrow": [], "this_week": [], "later": []},
    }


def _fresh(items: dict) -> dict:
    """sr с бакетами, уже построенными под TODAY."""
    sr = _sr(items)
    fi.rebuild_queue(sr, TODAY)
    return sr


def _write(d: Path, sr: dict) -> Path:
    p = d / "spaced-repetition.json"
    p.write_text(json.dumps(sr, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# --- plan() -----------------------------------------------------------


def test_noop_when_fresh():
    sr = _fresh({"a": {"due_date": TODAY}, "b": {"due_date": "2026-09-22"}})
    _, _, changed = rq.plan(sr, TODAY)
    assert changed is False


def test_lag_detected():
    """Карточка созрела сегодня, но бакеты строились вчера."""
    sr = _sr(
        {"rule_7_1": {"due_date": TODAY, "priority": "critical"},
         "other": {"due_date": "2026-09-30"}},
        # снимок, сделанный вчера: rule_7_1 тогда был «завтра»
        {"today": [], "tomorrow": ["rule_7_1"], "this_week": [],
         "later": ["other"]},
    )
    before, after, changed = rq.plan(sr, TODAY)
    assert changed is True
    assert after["today"] == ["rule_7_1"]
    assert after["tomorrow"] == []
    assert rq.moved_into_today(before, after) == ["rule_7_1"]


def test_plan_does_not_mutate_input():
    sr = _sr({"a": {"due_date": TODAY}},
             {"today": [], "tomorrow": ["a"], "this_week": [], "later": []})
    snapshot = json.dumps(sr, sort_keys=True)
    rq.plan(sr, TODAY)
    assert json.dumps(sr, sort_keys=True) == snapshot


def test_parity_with_importer():
    """Бакетинг обязан совпадать с fluent_import.rebuild_queue."""
    items = {
        "due_past": {"due_date": "2026-09-14"},
        "due_today": {"due_date": TODAY},
        "due_tom": {"due_date": "2026-09-22"},
        "due_week": {"due_date": "2026-09-28"},
        "due_later": {"due_date": "2026-09-29"},
    }
    _, after, _ = rq.plan(_sr(items), TODAY)
    ref = _sr(items)
    fi.rebuild_queue(ref, TODAY)
    assert after == {b: ref["review_queue"][b] for b in rq.BUCKETS}


def test_bucket_boundaries():
    items = {
        "past": {"due_date": "2026-09-14"},
        "today": {"due_date": TODAY},
        "tom": {"due_date": "2026-09-22"},
        "week_edge": {"due_date": "2026-09-28"},   # today + 7 → this_week
        "beyond": {"due_date": "2026-09-29"},      # today + 8 → later
    }
    _, after, _ = rq.plan(_sr(items), TODAY)
    assert set(after["today"]) == {"past", "today"}
    assert after["tomorrow"] == ["tom"]
    assert after["this_week"] == ["week_edge"]
    assert after["later"] == ["beyond"]


def test_missing_review_queue_key():
    sr = _sr({"a": {"due_date": TODAY}})
    del sr["review_queue"]
    before, after, changed = rq.plan(sr, TODAY)
    assert changed is True
    assert before["today"] == [] and after["today"] == ["a"]


def test_item_without_due_date_counts_as_today():
    """rebuild_queue подставляет today, если due_date нет — фиксируем."""
    _, after, _ = rq.plan(_sr({"naked": {}}), TODAY)
    assert after["today"] == ["naked"]


# --- apply_rebuild() и CLI --------------------------------------------


def test_apply_writes_and_backs_up():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        stale = _sr({"a": {"due_date": TODAY}},
                    {"today": [], "tomorrow": ["a"], "this_week": [],
                     "later": []})
        p = _write(root, stale)
        original = p.read_text(encoding="utf-8")

        sr = json.loads(p.read_text(encoding="utf-8"))
        bdir = rq.apply_rebuild(sr, p, TODAY)

        assert json.loads(p.read_text(encoding="utf-8"))["review_queue"]["today"] == ["a"]
        assert (bdir / p.name).read_text(encoding="utf-8") == original
        assert bdir.parent.name == ".backups"
        assert bdir.name.startswith("pre-rebuild-")


def test_apply_touches_only_queue_and_metadata():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        items = {"a": {"due_date": TODAY, "stability": 8.3, "repetitions": 1,
                       "mastery_level": 2, "priority": "high"}}
        p = _write(root, _sr(items, {"today": [], "tomorrow": ["a"],
                                     "this_week": [], "later": []}))
        sr = json.loads(p.read_text(encoding="utf-8"))
        rq.apply_rebuild(sr, p, TODAY)
        out = json.loads(p.read_text(encoding="utf-8"))
        assert out["items"] == items, "расписание FSRS должно остаться нетронутым"
        assert out["daily_limits"] == {"review_items_per_day": 30}


def test_cli_dry_run_does_not_write():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        p = _write(root, _sr({"a": {"due_date": TODAY}},
                             {"today": [], "tomorrow": ["a"],
                              "this_week": [], "later": []}))
        before = p.read_text(encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", str(root),
             "--date", TODAY],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "сухой прогон" in r.stdout
        assert p.read_text(encoding="utf-8") == before
        assert not (root / ".backups").exists()


def test_cli_noop_makes_no_backup():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        p = _write(root, _fresh({"a": {"due_date": TODAY}}))
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", str(root),
             "--date", TODAY, "--apply"],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "ничего не делаю" in r.stdout
        assert not (root / ".backups").exists()
        assert p.exists()


def test_cli_rejects_non_iso_date():
    """Бакетинг сравнивает даты как строки — кривая дата обязана падать."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        p = _write(root, _sr({"a": {"due_date": TODAY}}))
        before = p.read_text(encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", str(root),
             "--date", "21-09-2026", "--apply"],
            capture_output=True, text=True)
        assert r.returncode == 2
        assert p.read_text(encoding="utf-8") == before


def test_cli_missing_file_exits_2():
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", d, "--date", TODAY],
            capture_output=True, text=True)
        assert r.returncode == 2


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

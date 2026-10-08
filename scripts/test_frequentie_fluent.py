#!/usr/bin/env python3
"""Проверки frequentie_fluent.py --reset. Запуск: python3 scripts/test_frequentie_fluent.py

Сброс частотного плана оставлял только error_pattern и молча удалял карточки
правил `gram_lp_*` / `gram_sk_*` — вместе с review_history, единственным
знаменателем «ошибся N раз из скольких». Главный тест —
test_reset_keeps_rule_cards_untouched.

Каталога данных скрипт не принимает: путь к базе выводится из `~`. Поэтому
каждый прогон идёт подпроцессом с HOME во временном каталоге, а run() сперва
сверяет, что скрипт смотрит именно туда, — живая база ученика недостижима.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "frequentie_fluent.py"
HISTORY = [{"date": "2026-10-01", "quality": 2}, {"date": "2026-10-03", "quality": 4}]


def card(iid, kind, **extra):
    """Карточка с накопленной историей — сброс решает, что с ней будет."""
    return {"id": iid, "type": kind, "due_date": "2026-10-12", "stability": 3.2,
            "fsrs_difficulty": 5.1, "repetitions": 2, "total_reviews": 2,
            "mastery_level": 1, "review_history": HISTORY, **extra}


ITEMS = {c["id"]: c for c in (
    card("gram_lp_7.1", "grammar_rule", priority="critical"),  # правило Link+
    card("gram_sk_1.1", "grammar_rule", priority="high"),      # рамка подлежащего
    card("err_kun_kan", "error_pattern"),
    card("link_t12_gram_3_0", "grammar_rule"),                 # бэклог Link
    card("link_t12_voc_taak1_de-fiets", "vocabulary"),
    card("freq_zin_20261007_01", "grammar_rule"),              # вчерашняя фраза
)}


def store(home):
    return Path(home) / ".claude" / "fluent-data" / "spaced-repetition.json"


def setup(home):
    p = store(home)
    p.parent.mkdir(parents=True)
    queue = {"today": [], "tomorrow": [], "this_week": [], "later": []}
    p.write_text(json.dumps({"metadata": {}, "items": ITEMS, "review_queue": queue},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def run(home, *args):
    env = {**os.environ, "HOME": str(home)}
    probe = subprocess.run(
        [sys.executable, "-c", "import frequentie_fluent as f; print(f.SR_PATH)"],
        cwd=SCRIPT.parent, env=env, capture_output=True, text=True, check=True)
    assert Path(probe.stdout.strip()) == store(home), \
        f"скрипт смотрит не во временный HOME: {probe.stdout.strip()}"
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          env=env, capture_output=True, text=True)


def items_after_reset(home):
    r = run(home, "--reset")
    assert r.returncode == 0, r.stderr
    return json.loads(store(home).read_text(encoding="utf-8"))["items"]


def test_reset_keeps_rule_cards_untouched():
    """Карточки правил переживают сброс как есть: история, due_date, priority."""
    with tempfile.TemporaryDirectory() as d:
        setup(d)
        items = items_after_reset(d)
        for iid in ("gram_lp_7.1", "gram_sk_1.1"):
            assert items.get(iid) == ITEMS[iid], f"{iid}: {items.get(iid)}"


def test_reset_wipes_error_pattern_history():
    with tempfile.TemporaryDirectory() as d:
        setup(d)
        err = items_after_reset(d)["err_kun_kan"]
        assert err["review_history"] == [] and err["total_reviews"] == 0, err
        assert err["stability"] is None and err["mastery_level"] == 0, err


def test_reset_drops_other_grammar_rule():
    """Граница — префикс id, а не тип: бэклог Link и фразы дня тоже grammar_rule."""
    with tempfile.TemporaryDirectory() as d:
        setup(d)
        left = set(items_after_reset(d)) & {
            "link_t12_gram_3_0", "link_t12_voc_taak1_de-fiets", "freq_zin_20261007_01"}
        assert not left, f"пережили сброс: {sorted(left)}"


def test_dry_run_reports_untouched_and_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        p = setup(d)
        before = p.read_text(encoding="utf-8")
        r = run(d, "--reset", "--dry-run")
        assert r.returncode == 0, r.stderr
        assert "'untouched': 2" in r.stdout, r.stdout
        assert p.read_text(encoding="utf-8") == before
        assert not (p.parent / ".backups").exists()


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"OK    {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed} passed" + (f", {failed} failed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())

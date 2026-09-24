#!/usr/bin/env python3
"""Проверки twenty_rules из anki_utils.py. Запуск: python3 scripts/test_anki_utils.py

Главный тест — test_behoorlijk_nogal: воспроизводит коллизию партии 4, ради
которой проверка написана. Anki не нужен — функция чистая.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anki_utils import betekenissen, twenty_rules


def test_scheiding_en_haakjes():
    assert betekenissen("вдруг, внезапно; сразу") == ["вдруг", "внезапно", "сразу"]
    assert betekenissen("приличный, нормальный (о зарплате, поведении)") == [
        "приличный", "нормальный"]


def test_twee_betekenissen_mag():
    assert twenty_rules({"ineens": "вдруг, внезапно"}, {}) == []


def test_drie_betekenissen_niet():
    fouten = twenty_rules({"aangeven": "сообщать; указывать; передавать"}, {})
    assert len(fouten) == 1 and "правило 4" in fouten[0]


def test_behoorlijk_nogal():
    fouten = twenty_rules({"behoorlijk": "довольно, изрядно"},
                          {"nogal": "довольно, изрядно"})
    assert fouten == ["behoorlijk: ключ «довольно» уже у nogal (правило 10)"]


def test_botsing_binnen_partij():
    fouten = twenty_rules({"de beslissing": "решение", "het besluit": "решение"}, {})
    assert len(fouten) == 1 and "het besluit" in fouten[0]


def test_herimport_zelfde_woord():
    # Повторный импорт: слово уже в Anki с тем же ключом — не коллизия.
    assert twenty_rules({"de wens": "желание"}, {"de wens": "желание"}) == []


def test_hoofdletters():
    assert twenty_rules({"a": "Решение"}, {"b": "решение"}) != []


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

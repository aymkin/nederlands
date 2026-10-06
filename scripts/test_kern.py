#!/usr/bin/env python3
"""Проверки kern.py. Запуск: python3 scripts/test_kern.py

Anki и приватный список не нужны: sleutel и grens — чистые функции, laad идёт
против временной папки с теми же файлами.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kern

LIJST = ["zijn", "de", "hopen", "hoop", "kaart", "zijn#2", "Frankrijk", "aflopen", "jack"]
SLEUTELS = {k.lower(): k for k in LIJST}
VORMEN = {"kaart": ["kaart"], "hoop": ["hopen", "hoop"], "afgelopen": ["aflopen"],
          "zijn": ["zijn", "zijn#2"], "bevinden": ["bevinden"]}


def test_lidwoord_eraf():
    assert kern.sleutel("de kaart", SLEUTELS, VORMEN) == "kaart"


def test_woord_is_zelf_sleutel():
    # «de hoop» — существительное hoop, хотя главное прочтение формы — hopen.
    assert kern.sleutel("de hoop", SLEUTELS, VORMEN) == "hoop"


def test_tweede_lezing():
    assert kern.sleutel("zijn²", SLEUTELS, VORMEN) == "zijn#2"
    assert kern.sleutel("zijn", SLEUTELS, VORMEN) == "zijn"


def test_hoofdletters_uit_lijst():
    assert kern.sleutel("frankrijk", SLEUTELS, VORMEN) == "Frankrijk"


def test_vorm_via_vormen():
    assert kern.sleutel("afgelopen", SLEUTELS, VORMEN) == "aflopen"


def test_buiten_lijst():
    assert kern.sleutel("rekening houden met", SLEUTELS, VORMEN) is None
    assert kern.sleutel("de looncomponent", SLEUTELS, VORMEN) is None
    assert kern.sleutel("zich bevinden", SLEUTELS, VORMEN) is None  # bevinden нет в списке


def test_grens():
    assert kern.grens(LIJST, set(), {}) == 1
    assert kern.grens(LIJST, {"zijn", "hopen"}, {"de": "мусор"}) == 4
    assert kern.grens(["a"], {"a"}, {}) is None


def schrijf(d, tabellen=True, oud=False):
    pilot, frequentie = Path(d, "pilot"), Path(d, "frequentie")
    pilot.mkdir()
    frequentie.mkdir()
    paden = (Path(frequentie, "lijst_besluiten.tsv"), Path(pilot, "lijst_besluiten_prive.tsv"))
    for p in paden if tabellen else paden[:1]:   # сборка читает таблицы, потом пишет список
        p.write_text("actie\tvorm\twas\tnaar\twoord\treden\n")
        os.utime(p, (1, 1))
    Path(pilot, "lijst_v2.json").write_text(json.dumps({"consensus": LIJST, "uit": {"jack": "имя"}}))
    Path(pilot, "vormen.json").write_text(json.dumps(VORMEN))
    if oud:                                       # таблицу правили после сборки
        later = Path(pilot, "lijst_v2.json").stat().st_mtime + 60
        os.utime(paden[0], (later, later))
    return pilot, paden


def faalt(*args):
    try:
        with redirect_stderr(io.StringIO()):
            kern.laad(*args)
    except SystemExit as e:
        return str(e)
    return ""


def test_laad():
    with tempfile.TemporaryDirectory() as d:
        lijst, uit, vormen = kern.laad(*schrijf(d))
        assert lijst == LIJST and uit == {"jack": "имя"} and vormen == VORMEN


def test_zonder_prive_tabel():
    with tempfile.TemporaryDirectory() as d:
        assert "lijst_besluiten_prive.tsv" in faalt(*schrijf(d, tabellen=False))


def test_lijst_ouder_dan_tabel():
    with tempfile.TemporaryDirectory() as d:
        assert "пересобери" in faalt(*schrijf(d, oud=True))


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

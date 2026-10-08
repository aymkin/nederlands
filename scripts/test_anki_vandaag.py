#!/usr/bin/env python3
"""Проверки anki_vandaag.py. Запуск: python3 scripts/test_anki_vandaag.py

Anki не нужен: коллекция собирается в sqlite-файле с теми таблицами, которые
читает скрипт (revlog, cards, notes, notetypes, fields). Главный тест —
test_alleen_herhalingen: 2026-10-08 день без единого нового слова, но с 28
повторениями вернул «Geen nieuwe kaarten», и сессия Fluent началась с ложного
«Anki сегодня не было».
"""
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anki_vandaag as av

DAG = date(2026, 10, 8)
GISTEREN = date(2026, 10, 7)
NT = 100


def ms(day: date, uur: int, minuut: int = 0) -> int:
    return int(datetime(day.year, day.month, day.day, uur, minuut).timestamp() * 1000)


def collectie(tmp: str, woorden: dict[str, list[int]], extra_nt: dict[str, int] | None = None) -> Path:
    """woorden: {woord: [revlog-id, ...]}; één kaart per woord. extra_nt: woord → andere notetype."""
    col = Path(tmp) / "collection.anki2"
    con = sqlite3.connect(col)
    con.executescript(
        """
        CREATE TABLE revlog (id INTEGER, cid INTEGER);
        CREATE TABLE cards (id INTEGER, nid INTEGER);
        CREATE TABLE notes (id INTEGER, mid INTEGER, flds TEXT);
        CREATE TABLE notetypes (id INTEGER, name TEXT);
        CREATE TABLE fields (ntid INTEGER, ord INTEGER, name TEXT);
        """
    )
    con.execute("INSERT INTO notetypes VALUES (?, 'Frequentie NL')", (NT,))
    con.execute("INSERT INTO notetypes VALUES (?, 'Basic')", (NT + 1,))
    for ntid in (NT, NT + 1):
        for ord_, name in enumerate(("Word", "Rank", "Example", "Translation")):
            con.execute("INSERT INTO fields VALUES (?, ?, ?)", (ntid, ord_, name))
    for i, (woord, revs) in enumerate(woorden.items(), start=1):
        mid = (extra_nt or {}).get(woord, NT)
        con.execute("INSERT INTO notes VALUES (?, ?, ?)",
                    (i, mid, f"{woord}\x1f{i}\x1fvoorbeeld {woord}\x1fперевод {woord}"))
        con.execute("INSERT INTO cards VALUES (?, ?)", (i, i))
        for r in revs:
            con.execute("INSERT INTO revlog VALUES (?, ?)", (r, i))
    con.commit()
    con.close()
    return col


def woorden_van(notes) -> list[str]:
    return [dict(zip(f, v))["Word"] for _, f, v in notes]


def test_nieuw():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"de held": [ms(DAG, 7)], "de bron": [ms(DAG, 7, 5)]})
        dag = av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE])
    assert woorden_van(dag.nieuw) == ["de held", "de bron"]
    assert dag.herhaald == [] and dag.laatst == []


def test_alleen_herhalingen():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"de onzin": [ms(GISTEREN, 7), ms(DAG, 6, 40)],
                              "vallen": [ms(GISTEREN, 8), ms(DAG, 6, 41)]})
        dag = av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE])
        tekst = av.render(dag)
    assert dag.nieuw == []
    assert woorden_van(dag.herhaald) == ["de onzin", "vallen"]
    assert dag.reviews_op_dag == 2
    assert "## Повторены сегодня (2)" in tekst
    assert "**de onzin**" in tekst
    assert "Geen nieuwe" not in tekst


def test_nieuw_telt_niet_dubbel_als_herhaald():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"de held": [ms(DAG, 7), ms(DAG, 7, 9)],
                              "vallen": [ms(GISTEREN, 8), ms(DAG, 7, 1)]})
        dag = av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE])
    assert woorden_van(dag.nieuw) == ["de held"]
    assert woorden_van(dag.herhaald) == ["vallen"]


def test_lege_dag_geeft_laatste_met_datum():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"de bron": [ms(GISTEREN, 7)],
                              "het lied": [ms(date(2026, 10, 5), 9)],
                              "nogal": [ms(date(2026, 10, 6), 9)]})
        dag = av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE], laatst=2)
        tekst = av.render(dag)
    assert dag.reviews_op_dag == 0 and dag.nieuw == [] and dag.herhaald == []
    assert [woorden_van([n])[0] for _, n in dag.laatst] == ["de bron", "nogal"]
    assert "нет ни одного повторения" in tekst
    assert "синхронизироваться" in tekst
    assert "· 07.10" in tekst and "· 06.10" in tekst


def test_andere_notetype_telt_niet_maar_wordt_gemeld():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"cat": [ms(DAG, 7)], "de bron": [ms(GISTEREN, 7)]},
                        extra_nt={"cat": NT + 1})
        dag = av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE])
        tekst = av.render(dag)
    assert dag.nieuw == [] and dag.herhaald == []
    assert dag.reviews_op_dag == 1
    assert woorden_van([n for _, n in dag.laatst]) == ["de bron"]
    assert "не по заданному типу" in tekst


def test_laatst_uit():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"de bron": [ms(GISTEREN, 7)]})
        dag = av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE], laatst=0)
        tekst = av.render(dag)
    assert dag.laatst == []
    assert "нет ни одного повторения по этому типу" in tekst


def test_statusregel_noemt_versheid():
    with tempfile.TemporaryDirectory() as tmp:
        col = collectie(tmp, {"de bron": [ms(DAG, 6, 56)]})
        tekst = av.render(av.werkdag(col, DAG, [av.DEFAULT_NOTETYPE]))
    assert "последнее повторение в ней 08.10 06:56" in tekst
    assert "повторений за 2026-10-08: 1" in tekst


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

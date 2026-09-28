#!/usr/bin/env python3
"""Проверки anki_utils.py. Запуск: python3 scripts/test_anki_utils.py

Anki не нужен: twenty_rules — чистая функция, а import_tsv и lint идут против
nep_anki — фейкового AnkiConnect с тем же порядком проверок, что у createNote.
Главные тесты: test_behoorlijk_nogal (коллизия партии 4, ради неё написана
проверка Twenty Rules) и test_verkeerd_profiel (импорт 2026-09-28 при открытом
профиле Юли).
"""
import io
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anki_utils as au
from anki_utils import betekenissen, twenty_rules

TSV = (
    "#separator:tab\n#html:true\n#notetype:Frequentie NL\n#deck:Frequentie::Werk\n"
    "#columns:Word\tTranslation\tTags\n#tags column:3\n"
    "pas\tпропуск\tfrequentie::werk\n"
    "bepalen\tопределять\tfrequentie::werk\n"
)


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


@contextmanager
def nep_anki(profiel="alex", modellen=("Frequentie NL",), decks=("Frequentie::Werk",),
             bestaand=None):
    """AnkiConnect понарошку: журнал вызовов и порядок проверок createNote —
    note type, потом колода, потом дубль. bestaand — Word → Translation."""
    bestaand = bestaand or {}
    decks = list(decks)
    log = []

    def kan(n):
        if n["modelName"] not in modellen:
            return {"canAdd": False, "error": f"model was not found: {n['modelName']}"}
        if n["deckName"] not in decks:
            return {"canAdd": False, "error": f"deck was not found: {n['deckName']}"}
        if n["fields"]["Word"] in bestaand:
            return {"canAdd": False, "error": au.DUBBEL}
        return {"canAdd": True}

    def ankiconnect(action, **params):
        log.append((action, params))
        if action == "getActiveProfile":
            return profiel
        if action == "findNotes":
            return list(bestaand)
        if action == "notesInfo":
            return [{"fields": {"Word": {"value": w}, "Translation": {"value": t}}}
                    for w, t in bestaand.items()]
        if action == "deckNames":
            return list(decks)
        if action == "canAddNotesWithErrorDetail":
            return [kan(n) for n in params["notes"]]
        if action == "createDeck":
            decks.append(params["deck"])
            return 1
        if action == "addNotes":
            return list(range(len(params["notes"])))
        raise AssertionError(f"неожиданный вызов {action}")

    echt, au.ankiconnect = au.ankiconnect, ankiconnect
    try:
        yield log
    finally:
        au.ankiconnect = echt


def importeer(tsv=TSV):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "werk_dag_anki.txt"
        p.write_text(tsv, encoding="utf-8")
        return au.import_tsv(p)


def acties(log):
    return [a for a, _ in log]


def test_verkeerd_profiel():
    """2026-09-28: открыт профиль Юли — отказ раньше любого другого вызова."""
    with nep_anki(profiel="iuliia") as log:
        try:
            importeer()
            assert False, "expected AnkiFout"
        except au.AnkiFout as e:
            assert "iuliia" in str(e) and "alex" in str(e)
    assert acties(log) == ["getActiveProfile"]


def test_geen_profiel_open():
    with nep_anki(profiel=None) as log:
        try:
            importeer()
            assert False, "expected AnkiFout"
        except au.AnkiFout as e:
            assert "не открыт" in str(e)
    assert acties(log) == ["getActiveProfile"]


def test_geen_model_geen_dubbel():
    """«model was not found» — отказ с текстом Anki, а не «уже были»."""
    with nep_anki(modellen=()) as log:
        try:
            importeer()
            assert False, "expected AnkiFout"
        except au.AnkiFout as e:
            assert str(e) == "model was not found: Frequentie NL — pas, bepalen"
    assert not {"createDeck", "addNotes"} & set(acties(log))


def test_dubbel_overgeslagen():
    with nep_anki(bestaand={"pas": "пропуск"}) as log:
        assert importeer() == (1, ["pas"])
    toegevoegd = [p["notes"] for a, p in log if a == "addNotes"]
    assert [[n["fields"]["Word"] for n in ns] for ns in toegevoegd] == [["bepalen"]]


def test_dubbel_binnen_partij():
    """Word дважды в партии: canAdd пропустил бы оба — отказ до первого вызова."""
    herhaling = "pas\tшаг\tfrequentie::werk\nbepalen\tрешать\tfrequentie::werk\n"
    with nep_anki() as log:
        try:
            importeer(TSV + herhaling)
            assert False, "expected KaartFout"
        except au.KaartFout as e:
            assert str(e) == "Word повторяется в партии: pas, bepalen"
    assert log == []


def test_nieuwe_deck_na_controle():
    """Колоды ещё нет: canAdd — на существующей, createDeck — перед addNotes."""
    with nep_anki(decks=("Default",)) as log:
        assert importeer() == (2, [])
    a = acties(log)
    assert a.index("canAddNotesWithErrorDetail") < a.index("createDeck") < a.index("addNotes")
    proef = next(p for x, p in log if x == "canAddNotesWithErrorDetail")
    assert {n["deckName"] for n in proef["notes"]} == {"Default"}
    toegevoegd = next(p for x, p in log if x == "addNotes")
    assert {n["deckName"] for n in toegevoegd["notes"]} == {"Frequentie::Werk"}


def test_nieuwe_deck_alles_dubbel():
    """Добавлять нечего — пустую колоду не создаём."""
    with nep_anki(decks=("Default",),
                  bestaand={"pas": "пропуск", "bepalen": "определять"}) as log:
        assert importeer() == (0, ["pas", "bepalen"])
    assert not {"createDeck", "addNotes"} & set(acties(log))


def test_lint_verkeerd_profiel():
    with nep_anki(profiel="iuliia") as log:
        try:
            au.lint()
            assert False, "expected AnkiFout"
        except au.AnkiFout:
            pass
    assert acties(log) == ["getActiveProfile"]


def test_lint_leeg():
    """Ноль заметок — не «нарушений нет»: так выглядит и переименованный тип."""
    with nep_anki():
        try:
            au.lint()
            assert False, "expected AnkiFout"
        except au.AnkiFout as e:
            assert "нет заметок" in str(e)


@contextmanager
def anki_map(*profielen):
    """Временная папка Anki2 с профилями `profielen` вместо настоящей."""
    with tempfile.TemporaryDirectory() as d:
        for p in profielen:
            (Path(d) / p / "collection.media").mkdir(parents=True)
        echt, au.ANKI_BASE_PATHS = au.ANKI_BASE_PATHS, [Path(d)]
        try:
            yield Path(d)
        finally:
            au.ANKI_BASE_PATHS = echt


def test_media_vast_profiel():
    """Из двух профилей берётся alex, как бы iterdir() их ни упорядочил."""
    with anki_map("iuliia", "alex") as d:
        assert au.find_anki_media_folder() == d / "alex" / "collection.media"
        assert au.find_anki_media_folder("iuliia") == d / "iuliia" / "collection.media"


def test_media_alleen_iuliia():
    """Профиль один, но чужой — None; старый код отдал бы папку Юли."""
    with anki_map("iuliia"), redirect_stdout(io.StringIO()) as out:
        assert au.find_anki_media_folder() is None
    assert "есть: iuliia" in out.getvalue()


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

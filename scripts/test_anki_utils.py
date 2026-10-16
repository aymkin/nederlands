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
import kern
from anki_utils import betekenissen, synoniemen, twenty_rules

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


NOGAL = {"nogal": ("довольно-таки, изрядно", "Het is vandaag nogal koud.")}


def test_synoniemen_zelfde_situatie():
    # D6: у синонимов своя ситуация. Общее значение «изрядно», в примерах — koud.
    fouten = synoniemen({"behoorlijk": ("порядочно, изрядно", "Het is behoorlijk koud buiten.")},
                        NOGAL)
    assert fouten == ["behoorlijk / nogal: синонимы («изрядно»), в примерах общее koud "
                      "(правило 10: у синонимов своя ситуация)"]


def test_synoniemen_geen_gemeen_betekenis():
    # ineens делит с nogal «koud», но не значение — не синонимы.
    assert synoniemen({"ineens": ("вдруг, внезапно", "Het is ineens koud.")}, NOGAL) == []


def test_synoniemen_lidwoord_en_is_tellen_niet():
    assert synoniemen({"behoorlijk": ("порядочно, изрядно", "Het is behoorlijk warm.")},
                      NOGAL) == []


def test_synoniemen_doelen_tellen_niet():
    assert synoniemen({"behoorlijk": ("изрядно", "Behoorlijk of nogal?")},
                      {"nogal": ("изрядно", "Nogal of behoorlijk?")}) == []


def test_synoniemen_alleen_paren_met_nieuw():
    # Импорт другой партии не падает на паре, которая уже лежит в Anki.
    bestaand = {**NOGAL, "behoorlijk": ("порядочно, изрядно", "Het is behoorlijk koud.")}
    assert synoniemen({"de wens": ("желание", "Mijn wens is een fiets.")}, bestaand) == []
    assert len(synoniemen(bestaand, {})) == 1                     # lint видит её


def kaart(cid, word, rank, due, deck=au.KERN):
    """Новая карточка Kern так, как её отдаёт cardsInfo."""
    return {"cardId": cid, "deckName": deck, "due": due,
            "fields": {"Word": {"value": word}, "Rank": {"value": str(rank)}}}


@contextmanager
def nep_anki(profiel="alex", modellen=("Frequentie NL",), decks=("Frequentie::Werk",),
             bestaand=None, kaarten=(), weiger=False, voorbeelden=None, velden=None,
             blind=False):
    """AnkiConnect понарошку: журнал вызовов и порядок проверок createNote —
    note type, потом колода, потом дубль. bestaand — Word → Translation,
    voorbeelden — Word → Example, velden — Word → прочие поля (notesInfo, как
    настоящий, отдаёт все поля; noteId здесь — сам Word). kaarten — новые
    карточки для herorden; weiger — setSpecificValueOfCard отвечает False, как
    настоящий при отказе; blind — updateNoteFields не пишет, как настоящий, когда
    заметка открыта в браузере Anki."""
    bestaand = bestaand or {}
    notities = {w: {"Word": w, "Translation": t, "Example": (voorbeelden or {}).get(w, ""),
                    **(velden or {}).get(w, {})} for w, t in bestaand.items()}
    decks = list(decks)
    kaarten = {k["cardId"]: dict(k) for k in kaarten}  # RIJ общий для тестов
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
            return list(notities)
        if action == "notesInfo":
            return [{"noteId": w, "fields": {f: {"value": v} for f, v in notities[w].items()}}
                    for w in params["notes"]]
        if action == "updateNoteFields":
            if not blind:
                notities[params["note"]["id"]].update(params["note"]["fields"])
            return None
        if action == "deckNames":
            return list(decks)
        if action == "canAddNotesWithErrorDetail":
            return [kan(n) for n in params["notes"]]
        if action == "createDeck":
            decks.append(params["deck"])
            return 1
        if action == "addNotes":
            return list(range(len(params["notes"])))
        if action == "findCards":
            return list(kaarten)
        if action == "cardsInfo":
            return [dict(kaarten[c]) for c in params["cards"]]
        if action == "setSpecificValueOfCard":
            if weiger:
                return False
            assert params["keys"] == ["due"] and type(params["newValues"][0]) is int
            kaarten[params["card"]]["due"] = params["newValues"][0]
            return [True]
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


def test_anki_niet_gestart():
    """2026-09-29: Anki закрыт — AnkiFout с подсказкой, а не traceback URLError."""
    echt, au.ANKICONNECT = au.ANKICONNECT, "http://127.0.0.1:9"
    try:
        au.ankiconnect("getActiveProfile")
        assert False, "expected AnkiFout"
    except au.AnkiFout as e:
        assert "запусти Anki" in str(e)
    finally:
        au.ANKICONNECT = echt


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


SYNONIEM_TSV = (
    "#separator:tab\n#html:true\n#notetype:Frequentie NL\n#deck:Frequentie::Werk\n"
    "#columns:Word\tExample\tTranslation\tTags\n#tags column:4\n"
    "behoorlijk\tHet is behoorlijk koud buiten.\tпорядочно, изрядно\tfrequentie\n"
)


def test_import_weigert_synoniem_zelfde_situatie():
    with nep_anki(bestaand={"nogal": NOGAL["nogal"][0]},
                  voorbeelden={"nogal": NOGAL["nogal"][1]}) as log:
        try:
            importeer(SYNONIEM_TSV)
        except au.KaartFout as e:
            assert "behoorlijk / nogal" in str(e) and "koud" in str(e)
        else:
            raise AssertionError("синоним с той же ситуацией прошёл")
    assert "addNotes" not in acties(log)


def test_lint_noemt_synoniemen():
    with nep_anki(bestaand={"nogal": NOGAL["nogal"][0], "behoorlijk": "порядочно, изрядно"},
                  voorbeelden={"nogal": NOGAL["nogal"][1],
                               "behoorlijk": "Het is behoorlijk koud buiten."}):
        assert au.lint() == ["behoorlijk / nogal: синонимы («изрядно»), в примерах общее "
                             "koud (правило 10: у синонимов своя ситуация)"]


# i+1 понарошку (kern.laad): thuis и ziek — за блоком 1–150, omdat — в нём.
I1 = (["ik", "blijven", "omdat", "zijn"] + [f"vul{i}" for i in range(200)] + ["thuis", "ziek"],
      {}, {"ik": ["ik"], "blijf": ["blijven"], "thuis": ["thuis"], "omdat": ["omdat"],
           "ziek": ["ziek"], "ben": ["zijn"]})
OMDAT = "Ik blijf thuis omdat ik ziek ben."


@contextmanager
def lijst(laad=lambda: I1):
    echt, kern.laad = kern.laad, laad
    try:
        yield
    finally:
        kern.laad = echt


def partij(deck, rank="3", example=OMDAT):
    return ("#separator:tab\n#html:true\n#notetype:Frequentie NL\n"
            f"#deck:{deck}\n#columns:Word\tRank\tExample\tTranslation\tTags\n#tags column:5\n"
            f"omdat\t{rank}\t{example}\tпотому что\tfrequentie\n")


def test_import_kern_i1():
    with nep_anki(decks=(au.KERN,)) as log, lijst():
        try:
            importeer(partij(au.KERN))
        except au.KaartFout as e:
            assert "thuis 205" in str(e) and "ziek 206" in str(e)
        else:
            raise AssertionError("пример против i+1 прошёл")
    assert "addNotes" not in acties(log)


def test_import_werk_zonder_i1():
    # У Werk нет ранга в списке: i+1 только для Kern, список даже не читается.
    def nee():
        raise AssertionError("i+1 для Werk")
    with nep_anki(), lijst(nee):
        assert importeer(partij("Frequentie::Werk")) == (1, [])


def bijwerken(tsv, droog=False):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "kern_a_anki.txt"
        p.write_text(tsv, encoding="utf-8")
        return au.update(p, droog=droog)


IN_ANKI = dict(decks=(au.KERN,), bestaand={"omdat": "потому что"}, voorbeelden={"omdat": OMDAT},
               velden={"omdat": {"Rank": "116"}})


def geschreven(log):
    return [p["note"] for a, p in log if a == "updateNoteFields"]


def test_update_alleen_verschil():
    # Пример против i+1 не менялся — меняется только Rank, ворота его не держат.
    with nep_anki(**IN_ANKI) as log, lijst():
        assert bijwerken(partij(au.KERN)) == {"Rank": ["omdat"]}
    assert geschreven(log) == [{"id": "omdat", "fields": {"Rank": "3"}}]


def test_update_droog():
    with nep_anki(**IN_ANKI) as log, lijst():
        assert bijwerken(partij(au.KERN), droog=True) == {"Rank": ["omdat"]}
    assert geschreven(log) == []


def test_update_nieuw_voorbeeld_door_poort():
    anki = {**IN_ANKI, "voorbeelden": {"omdat": "Ik blijf omdat ik ben."}}
    with nep_anki(**anki) as log, lijst():
        try:
            bijwerken(partij(au.KERN, rank="116"))
        except au.KaartFout as e:
            assert "thuis 205" in str(e)
        else:
            raise AssertionError("новый пример против i+1 записан")
    assert geschreven(log) == []


def test_update_niet_in_anki():
    with nep_anki(decks=(au.KERN,)) as log:
        try:
            bijwerken(partij(au.KERN))
        except au.AnkiFout as e:
            assert "omdat" in str(e) and "import" in str(e)
        else:
            raise AssertionError("заметки нет, а update прошёл")
    assert geschreven(log) == []


def test_update_blind():
    """Заметка открыта в браузере Anki: запись молча не легла — ловим перечтением."""
    with nep_anki(**IN_ANKI, blind=True), lijst():
        try:
            bijwerken(partij(au.KERN))
        except au.AnkiFout as e:
            assert "omdat" in str(e) and "браузер" in str(e)
        else:
            raise AssertionError("незаписанное поле прошло")


def test_update_verkeerd_profiel():
    with nep_anki(profiel="iuliia", **IN_ANKI) as log:
        try:
            bijwerken(partij(au.KERN))
        except au.AnkiFout:
            pass
        else:
            raise AssertionError("чужой профиль прошёл")
    assert acties(log) == ["getActiveProfile"]


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


RIJ = (kaart(1, "de serie", 1230, 6828), kaart(2, "de kaart", 740, 6829),
       kaart(3, "het verzoek", 1275, 1275))


def gezet(log):
    return [(p["card"], p["newValues"]) for a, p in log if a == "setSpecificValueOfCard"]


def test_herorden_rank_wordt_due():
    """2026-10-06: позиции шли в порядке файла — 48 % пар против ранга."""
    with nep_anki(kaarten=RIJ) as log:
        assert au.herorden() == (3, 2)
    assert gezet(log) == [(1, [1230]), (2, [740])]
    zoek = next(p for a, p in log if a == "findCards")
    assert zoek["query"] == '"deck:Frequentie::Kern" is:new'


def test_herorden_tweede_keer_niets():
    with nep_anki(kaarten=RIJ) as log:
        au.herorden()
        log.clear()
        assert au.herorden() == (3, 0)
    assert gezet(log) == []


def test_herorden_droog():
    with nep_anki(kaarten=RIJ) as log:
        assert au.herorden(droog=True) == (3, 2)
    assert gezet(log) == []


def test_herorden_weigering():
    """Отказ приходит как False без error — его надо поймать самим."""
    with nep_anki(kaarten=RIJ, weiger=True):
        try:
            au.herorden()
            assert False, "expected AnkiFout"
        except au.AnkiFout as e:
            assert "de serie" in str(e)


def test_herorden_gefilterd_overgeslagen():
    """В фильтрованной колоде due — место в ней, не позиция: не трогаем."""
    rij = RIJ + (kaart(4, "de regio", 1248, 3, deck="Filtered Deck 1"),)
    with nep_anki(kaarten=rij) as log:
        assert au.herorden() == (3, 2)
    assert 4 not in [c for c, _ in gezet(log)]


def test_herorden_rank_geen_getal():
    with nep_anki(kaarten=RIJ + (kaart(5, "de jeugd", "", 7),)) as log:
        try:
            au.herorden()
            assert False, "expected AnkiFout"
        except au.AnkiFout as e:
            assert "de jeugd" in str(e)
    assert gezet(log) == []


def test_herorden_verkeerd_profiel():
    with nep_anki(profiel="iuliia", kaarten=RIJ) as log:
        try:
            au.herorden()
            assert False, "expected AnkiFout"
        except au.AnkiFout:
            pass
    assert acties(log) == ["getActiveProfile"]


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


OUD = b"ID3 werkend mp3 " * 1400          # ~22 КБ, как настоящий werk_*.mp3
NIEUW = b"ID3 nieuw mp3 " * 1000          # ~14 КБ


@contextmanager
def vervang(mod, **nieuw):
    echt = {k: getattr(mod, k) for k in nieuw}
    for k, v in nieuw.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in echt.items():
            setattr(mod, k, v)


@contextmanager
def media_met(bestaand):
    with tempfile.TemporaryDirectory() as d:
        media = Path(d) / "collection.media"
        media.mkdir()
        for naam, inhoud in bestaand.items():
            (media / naam).write_bytes(inhoud)
        yield media


def inhoud(media):
    return {p.name: p.read_bytes() for p in media.iterdir()}


async def edge_403(text, path):
    """Как edge-tts 7.2.7 2026-10-16: save() открывает файл, потом 403."""
    path.write_bytes(b"")
    raise RuntimeError("403, message='Invalid response status'")


async def spreekt_goed(text, path):
    path.write_bytes(NIEUW)


def test_mp3_synthese_faalt_media_heel():
    """2026-10-16: 403 при синтезе оставил пустой werk_stemmen.mp3 поверх рабочего."""
    with media_met({"werk_stemmen.mp3": OUD}) as media:
        try:
            au.mp3_naar_media([("Stemmen kan tot 21 uur.", media / "werk_stemmen.mp3")],
                              edge_403)
            assert False, "expected AudioFout"
        except au.AudioFout as e:
            assert "werk_stemmen.mp3" in str(e) and "403" in str(e)
        assert inhoud(media) == {"werk_stemmen.mp3": OUD}


def test_mp3_tweede_faalt_eerste_blijft():
    """Партия целиком: упал второй — первый, уже озвученный, в media не попал."""
    async def tweede_faalt(text, path):
        await (edge_403 if text == "b" else spreekt_goed)(text, path)

    with media_met({"werk_a.mp3": OUD}) as media, vervang(au, duur=lambda p: 2.0):
        try:
            au.mp3_naar_media([("a", media / "werk_a.mp3"), ("b", media / "werk_b.mp3")],
                              tweede_faalt)
            assert False, "expected AudioFout"
        except au.AudioFout as e:
            assert str(e).startswith("werk_b.mp3: синтез упал")
        assert inhoud(media) == {"werk_a.mp3": OUD}


def test_mp3_te_klein():
    async def stomp(text, path):
        path.write_bytes(b"ID3" * 30)

    with media_met({"werk_x.mp3": OUD}) as media:
        try:
            au.mp3_naar_media([("x", media / "werk_x.mp3")], stomp)
            assert False, "expected AudioFout"
        except au.AudioFout as e:
            assert str(e) == "werk_x.mp3: 90 байт — нужно больше 5120"
        assert inhoud(media) == {"werk_x.mp3": OUD}


def test_mp3_niets_geschreven():
    """spreek вернулся без ошибки, а файла нет — брак, не FileNotFoundError."""
    async def stil(text, path):
        pass

    with media_met({}) as media:
        try:
            au.mp3_naar_media([("x", media / "werk_x.mp3")], stil)
            assert False, "expected AudioFout"
        except au.AudioFout as e:
            assert "0 байт" in str(e)
        assert inhoud(media) == {}


def test_mp3_te_kort():
    with media_met({"werk_x.mp3": OUD}) as media, vervang(au, duur=lambda p: 0.4):
        try:
            au.mp3_naar_media([("x", media / "werk_x.mp3")], spreekt_goed)
            assert False, "expected AudioFout"
        except au.AudioFout as e:
            assert "0.40 с" in str(e)
        assert inhoud(media) == {"werk_x.mp3": OUD}


def test_mp3_goed_vervangt_zonder_resten():
    with media_met({"werk_x.mp3": OUD}) as media, vervang(au, duur=lambda p: 2.0):
        au.mp3_naar_media([("x", media / "werk_x.mp3"), ("y", media / "werk_y.mp3")],
                          spreekt_goed)
        assert inhoud(media) == {"werk_x.mp3": NIEUW, "werk_y.mp3": NIEUW}


def test_duur_ffprobe():
    """Настоящий ffprobe: 2 с тишины — около 2.0, мусор — 0.0. Без ffmpeg — пропуск."""
    if not (au.shutil.which("ffmpeg") and au.shutil.which("ffprobe")):
        print("    (нет ffmpeg/ffprobe — test_duur_ffprobe пропущен)")
        return
    with tempfile.TemporaryDirectory() as d:
        stil, rommel = Path(d) / "stil.mp3", Path(d) / "rommel.mp3"
        au.subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                           "anullsrc=r=24000:cl=mono", "-t", "2", "-b:a", "48k", str(stil)],
                          check=True)
        rommel.write_bytes(NIEUW)
        assert 1.9 < au.duur(stil) < 2.1
        assert au.duur(rommel) == 0.0
        assert au.keur_mp3(rommel).endswith("нужно длиннее 1 с")


def test_werk_kaarten_audio_faalt():
    """kaarten --audio --anki при 403: код 1, сообщение, media как была, импорта нет."""
    import argparse
    import json

    import werk_woorden as ww

    def import_tsv(path):
        raise AssertionError("импорт после упавшего аудио")

    with tempfile.TemporaryDirectory() as d, media_met({"werk_stemmen.mp3": OUD}) as media:
        root = Path(d)
        (root / "werk").mkdir()
        index = root / "werk" / "lemmas.json"
        index.write_text(json.dumps({"laatste_run": None, "verwerkt": [], "lemmas": {
            "stemmen": {"count": 3, "vormen": [], "zinnen": [], "status": "nieuw"}}}),
            encoding="utf-8")
        kaarten = root / "kaarten.json"
        kaarten.write_text(json.dumps([{
            "lemma": "stemmen", "word": "stemmen", "zin": "Je kunt tot 21 uur stemmen.",
            "vertaling": "голосовать", "zin_vertaling": "Голосовать можно до 21 часа."}]),
            encoding="utf-8")
        args = argparse.Namespace(file=str(kaarten), audio=True, anki=True)
        with vervang(ww, ROOT=root, WERK=root / "werk", INDEX=index, synth=edge_403), \
                vervang(au, find_anki_media_folder=lambda: media, import_tsv=import_tsv), \
                redirect_stdout(io.StringIO()) as out:
            rc = ww.cmd_kaarten(args)
        assert rc == 1
        assert "media не тронута, импорт не начат" in out.getvalue()
        assert "werk_stemmen.mp3: синтез упал — RuntimeError: 403" in out.getvalue()
        assert inhoud(media) == {"werk_stemmen.mp3": OUD}


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

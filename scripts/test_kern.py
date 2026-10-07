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
SLEUTELS = kern.Sleutels(LIJST)
VORMEN = {"kaart": ["kaart"], "hoop": ["hopen", "hoop"], "afgelopen": ["aflopen"],
          "zijn": ["zijn", "zijn#2"], "bevinden": ["bevinden"]}


def test_lidwoord_eraf():
    assert kern.sleutel("de kaart", SLEUTELS, VORMEN) == "kaart"


def test_alleen_lidwoord():
    # Карточка блока 1–150 «de»: снимать нечего, Word — сам ключ.
    assert kern.sleutel("de", SLEUTELS, VORMEN) == "de"


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


# Ключи, равные без регистра: имя Val (uit) и слово val, язык Engels и разорванный
# simplemma engels. Карточка должна сесть на лучший ранг, а не на последний в списке.
TWEELING = ["val", "Engels", "kaart", "Turks", "engels", "Val", "turks", "Frank"]


def test_hoofdletters_beste_rang():
    s = kern.Sleutels(TWEELING)
    assert kern.sleutel("de val", s, {}) == "val"
    assert kern.sleutel("het Engels", s, {}) == "Engels"
    assert kern.sleutel("engels", s, {}) == "Engels"


def test_vorm_houdt_exacte_sleutel():
    # главное прочтение из vormen.json — уже ключ списка, близнец его не подменяет;
    # чего в списке нет, ищется без регистра
    s = kern.Sleutels(TWEELING)
    assert kern.sleutel("franken", s, {"franken": ["Frank"]}) == "Frank"
    assert kern.sleutel("turkse", s, {"turkse": ["turks"]}) == "turks"
    assert kern.sleutel("britse", s, {"britse": ["brits"]}) is None
    assert kern.sleutel("Engelse", kern.Sleutels(["Engels"]), {"engelse": ["engels"]}) == "Engels"


def test_lijst_rapport_hoofdletters():
    notes = [("Frequentie::Kern", "de val", "1")]
    out, fout = kern.lijst_rapport(["val", "Val", "kaart"], {"Val": "имя"}, {}, notes)
    tekst = "\n".join(out)
    assert "граница: ранг 3 (kaart)" in tekst, tekst
    assert "Kern на ключе uit: 0" in tekst, tekst


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


# check: ключ → ранг; остальные места списка — заполнитель.
RANGEN = {"zijn": 1, "de": 2, "ik": 3, "een": 4, "en": 5, "je": 6, "het": 7, "in": 8,
          "hebben": 9, "op": 10, "van": 11, "hij": 12, "dat": 13, "maar": 15, "willen": 50,
          "hun": 40, "mijn": 36, "laten": 67, "zijn#2": 71, "weten": 80, "woord": 120,
          "omdat": 125, "mooi": 130, "blijven": 140, "wonen": 150, "wachten": 158,
          "zitten": 160, "stoel": 170, "vergeten": 180, "plaats": 190, "laat": 198,
          "thuis": 267, "zoon": 272, "telefoon": 300, "bellen": 110, "avond": 361,
          "taxi": 450, "fiets": 500, "opnemen": 600, "ziek": 614, "nemen": 700,
          "plaatsen": 743, "nacht": 90, "Jan": 960, "vannacht": 970,
          "stappen": 400, "pen": 800}
CHECK_LIJST = [f"vul{i}" for i in range(1, 1001)]
for _k, _r in RANGEN.items():
    CHECK_LIJST[_r - 1] = _k
CHECK_VORMEN = {
    "ik": ["ik"], "blijf": ["blijven"], "blijft": ["blijven"], "thuis": ["thuis"], "omdat": ["omdat"], "ziek": ["ziek"],
    "ben": ["zijn"], "zit": ["zitten"], "op": ["op"], "de": ["de"], "stoel": ["stoel"],
    "hij": ["hij"], "heeft": ["hebben"], "s": ["s"], "avonds": ["avond"], "z'n": ["zijn#2"],
    "fiets": ["fiets"], "en": ["en"], "n": ["n"], "taxi": ["taxi"], "hun": ["hun"],
    "zoon": ["zoon"], "woont": ["wonen"], "in": ["in"], "utrecht": ["utrecht"], "is": ["zijn"],
    "mooi": ["mooi"], "neem": ["nemen"], "je": ["je"], "telefoon": ["telefoon"],
    "vergeet": ["vergeten"], "het": ["het"], "laat": ["laten", "laat"], "maar": ["maar"],
    "wachtwoord": ["wachtwoord"], "wacht": ["wachten"], "woord": ["woord"], "van": ["van"],
    "mijn": ["mijn"], "bel": ["bellen"], "opdat": ["opdat"], "weet": ["weten"], "dat": ["dat"],
    "wil": ["willen"], "plaatsen": ["plaats"], "jan": ["Jan"], "nacht": ["nacht"],
    "vannacht": ["vannacht"], "stap": ["stappen", "stap"], "pen": ["pen"],
}


def oordeel(word, example):
    return kern.voorbeeld(word, example, {k: i for i, k in enumerate(CHECK_LIJST, 1)},
                          {k.lower(): k for k in CHECK_LIJST}, {"Jan": "имя"}, CHECK_VORMEN)


def test_omdat_vangt_thuis_en_ziek():
    # blijven (140) позже omdat (125), но в блоке 1–150 известно всё ≤ 150.
    o = oordeel("omdat", "Ik blijf thuis omdat ik ziek ben.")
    assert (o.rang, o.fout, o.doel) == (125, ["thuis", "ziek"], True)


def test_na_blok_alleen_eerder():
    assert oordeel("zitten", "Ik zit op de stoel.").fout == ["stoel"]   # 170 > 160


def test_klitieken():
    # vormen.json даёт «n» и «s» ключи-обрывки, в примере это 'n (een) и 's (des).
    o = oordeel("de fiets", "Hij heeft 's avonds z'n fiets en 'n taxi.")
    assert (o.fout, o.let_op, o.onbekend) == ([], [], [])


def test_naam_alleen_midden_in_zin():
    assert oordeel("de zoon", "Hun zoon woont in Utrecht.").fout == []
    assert oordeel("de zoon", "Utrecht is mooi, zegt mijn zoon.").fout == ["utrecht"]


def test_uit_telt_als_bekend():
    # В начале предложения заглавная ничего не говорит, но Jan помечен uit.
    assert oordeel("thuis", "Jan blijft thuis.").fout == []


def test_gescheiden_scheidbaar_werkwoord():
    # nemen (700) позже opnemen (600), но «neem … op» — сама цель.
    o = oordeel("opnemen", "Neem je de telefoon op?")
    assert (o.fout, o.doel) == ([], True)


def test_stam_van_doel_is_geen_deeltje():
    # «stap» + «pen»: основа самой цели — не частица, pen (800) не освобождается.
    assert oordeel("stappen", "Ik stap op de pen.").fout == ["pen"]


def test_lezing_vooruit_is_waarschuwing():
    o = oordeel("vergeten", "Ik vergeet het, laat maar.")
    assert (o.fout, o.let_op) == ([], [("laat", ["laat"])])   # laten 67 ✓, laat 198 > 180


def test_samengesteld_woord():
    # wachtwoord нет в списке — судят части.
    o = oordeel("de telefoon", "Het wachtwoord van mijn telefoon.")
    assert (o.fout, o.samengesteld) == ([], [("wachtwoord", "wacht", "woord")])
    # vannacht — слово списка (970): свой ранг, хоть van и nacht известны.
    assert oordeel("de telefoon", "Mijn telefoon is vannacht mooi.").fout == ["vannacht"]


def test_samengesteld_delen_van_drie_letters():
    # opdat вне списка, но «op» + «dat»: часть короче трёх букв — не составное.
    assert oordeel("de telefoon", "Ik bel, opdat je het weet.").fout == ["opdat"]


def test_vorm_buiten_vormen():
    assert oordeel("de fiets", "Mijn fiets xyzzy.").onbekend == ["xyzzy"]


def test_doel_niet_gevonden():
    # Форма «plaatsen» в vormen.json кормит только plaats: пример цель не показывает.
    assert oordeel("plaatsen", "Ik wil het plaatsen.").doel is False


def test_check_rapport():
    notes = [("kern_a.txt", "omdat", "Ik blijf thuis omdat ik ziek ben."),
             ("kern_a.txt", "de fiets", "Hij heeft z'n fiets.")]
    out, fout = kern.check_rapport(CHECK_LIJST, {}, CHECK_VORMEN, notes)
    assert fout and "нарушают 1" in out[0]
    assert any("thuis 267" in line and "ziek 614" in line for line in out)
    assert kern.check_rapport(CHECK_LIJST, {}, CHECK_VORMEN, notes[1:])[1] is False


def test_alleen_kern():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d, "werk.txt")
        p.write_text("#separator:tab\n#html:true\n#notetype:Frequentie NL\n"
                     "#deck:Frequentie::Werk\n#columns:Word\tRank\tExample\tTags\n#tags column:4\n"
                     "pas\t\tIk kom pas morgen.\t\n", encoding="utf-8")
        for stap in (lambda: kern.kern_voorbeelden([p]), lambda: kern.herrang([p], LIJST, VORMEN)):
            try:
                stap()
            except SystemExit as e:
                assert "Frequentie::Kern" in str(e)
            else:
                raise AssertionError("файл Werk прошёл")


KOP = ("#separator:tab\n#html:true\n#notetype:Frequentie NL\n#deck:Frequentie::Kern\n"
       "#columns:Word\tRank\tExample\tTags\n#tags column:4\n")


def test_rank_uit_lijst():
    # D2: позиция = ранг. de kaart — ранг 5, zijn² (zijn#2) уже 6 — строка не меняется.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d, "kern_a.txt")
        p.write_text(KOP + "de kaart\t740\tDe kaart.\tk\nzijn²\t6\tZ'n kaart.\tk", encoding="utf-8")
        assert kern.herrang([p], LIJST, VORMEN) == ([("kern_a.txt", "de kaart", "740", 5)], 2)
        assert p.read_text(encoding="utf-8") == KOP + "de kaart\t5\tDe kaart.\tk\nzijn²\t6\tZ'n kaart.\tk"


def test_rank_buiten_lijst_raakt_niets():
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d, "kern_a.txt"), Path(d, "kern_b.txt")
        a.write_text(KOP + "de kaart\t740\tDe kaart.\tk\n", encoding="utf-8")
        b.write_text(KOP + "rekening houden met\t1\tIk houd er rekening mee.\tk\n", encoding="utf-8")
        try:
            kern.herrang([a, b], LIJST, VORMEN)
        except SystemExit as e:
            assert "rekening houden met" in str(e)
        else:
            raise AssertionError("Word вне списка прошёл")
        assert "740" in a.read_text(encoding="utf-8")       # ни один файл не тронут


KOP_A = ("#separator:tab\n#html:true\n#notetype:Frequentie NL\n#deck:Frequentie::Kern\n"
         "#columns:Word\tRank\tExample\tAudio\tTags\n#tags column:5\n")


def test_audio_naam():
    # Имя — от ключа и примера: переписанный пример получает новый файл; zijn² ≠ zijn.
    a = kern.audio_naam("zijn#2", "Z'n kaart.")
    assert a.startswith("freq_zijn-2_") and a.endswith(".mp3")
    assert a != kern.audio_naam("zijn#2", "Z'n hoop.") and a != kern.audio_naam("zijn", "Z'n kaart.")


def audio_partij(d):
    p, media = Path(d, "kern_a.txt"), Path(d, "media")
    media.mkdir()
    z = kern.audio_naam("zijn#2", "Z'n kaart.")
    (media / z).write_bytes(b"mp3")
    p.write_text(KOP_A + "de kaart\t5\tDe kaart.\t[sound:freq_kaart.mp3]\tk\n"
                 f"zijn²\t6\tZ'n kaart.\t[sound:{z}]\tk\n", encoding="utf-8")
    return p, media, kern.audio_naam("kaart", "De kaart.")


def test_audio_vult_kolom_en_spreekt_wat_ontbreekt():
    with tempfile.TemporaryDirectory() as d:
        p, media, naam = audio_partij(d)
        gesproken = []
        anders, n, ontbreekt = kern.audio([p], LIJST, VORMEN, media, spreek=gesproken.extend)
        assert (anders, n) == ([("kern_a.txt", "de kaart", "[sound:freq_kaart.mp3]",
                                 f"[sound:{naam}]")], 2)
        assert ontbreekt == gesproken == [("De kaart.", media / naam)]
        assert f"de kaart\t5\tDe kaart.\t[sound:{naam}]\tk\n" in p.read_text(encoding="utf-8")


def test_audio_droog():
    with tempfile.TemporaryDirectory() as d:
        p, media, naam = audio_partij(d)
        voor = p.read_text(encoding="utf-8")
        gesproken = []
        anders, n, ontbreekt = kern.audio([p], LIJST, VORMEN, media, droog=True,
                                          spreek=gesproken.extend)
        assert len(anders) == 1 and ontbreekt == [("De kaart.", media / naam)]
        assert gesproken == [] and p.read_text(encoding="utf-8") == voor


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()

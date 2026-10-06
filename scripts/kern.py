#!/usr/bin/env python3
"""kern.py — колода Frequentie::Kern по списку: какие ранги уже с карточкой и где граница.

    python3 scripts/kern.py lijst                           # Word → ключ списка, дубли, граница
    python3 scripts/kern.py check frequentie/kern_*_anki.txt  # примеры по i+1
    python3 scripts/kern.py rank frequentie/kern_*_anki.txt   # колонка Rank := ранг списка

Список (lijst_v2.json) и карту форм (vormen.json) собирает
private/frequentie_pilot/consensus_rank.py с обеими таблицами решений; kern.py их
только читает. Коллекцию Anki — с копии (anki_vandaag.kopie), без записи; в Anki
Rank переносит anki_utils.py update.

Карточка у ключа есть, если его даёт Word любой заметки «Frequentie NL» (Kern,
Werk, Reading). Граница — первый ранг без карточки и без пометки uit.

i+1: каждое слово примера, кроме цели, известно — все его прочтения раньше цели в
списке (в блоке 1–150 — любые ≤ 150) или помечены uit.
"""
import json
import sys
from collections import Counter, namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anki_utils import ANKI_PROFILE, FREQUENTIE, KERN, TOKEN, lees_tsv, tekst  # same dir
from anki_vandaag import clean, collection_path, kopie

REPO = Path(__file__).resolve().parent.parent
PILOT = REPO / "private" / "frequentie_pilot"
TABELLEN = (REPO / "frequentie" / "lijst_besluiten.tsv", PILOT / "lijst_besluiten_prive.tsv")
WEG = {"de", "het", "zich"}            # снимаются с Word до сопоставления
HORIZON = 2500                         # горизонт таблицы решений
BLOK = 150                             # ранги 1–150 — один блок разгона
# words() пишет 'n/'m/'k/'s как n/m/k/s. В примере это клитики, а в vormen.json —
# обрывки субтитров со своими ключами.
KLITIEK = {"n": ["een"], "m": ["hem"], "k": ["ik"], "s": ["de"], "da's": ["dat", "zijn"]}
OPEN = " \"'«»„“”‘’()—–-"                  # между концом предложения и его первым словом
Oordeel = namedtuple("Oordeel", "rang fout let_op samengesteld onbekend doel")


def laad(pilot=PILOT, tabellen=TABELLEN):
    """(ключи по рангу, {ключ uit: причина}, {форма: [ключи]}).

    Без приватной таблицы граница встала бы на слове, которое исключает правило
    контента, — поэтому её отсутствие останавливает работу. Таблица новее списка —
    тоже: список собран без её последних строк."""
    lijst = pilot / "lijst_v2.json"
    for t in tabellen:
        if not t.exists():
            sys.exit(f"нет {t} — без неё список неполон")
        if t.stat().st_mtime > lijst.stat().st_mtime:
            sys.exit(f"{t.name} новее {lijst.name} — пересобери список: "
                     f"{pilot.relative_to(pilot.parent.parent)}/consensus_rank.py")
    data = json.loads(lijst.read_text(encoding="utf-8"))
    vormen = json.loads((pilot / "vormen.json").read_text(encoding="utf-8"))
    return data["consensus"], data["uit"], vormen


def sleutel(word, sleutels, vormen):
    """Ключ списка для Word или None (оборот, слова нет в списке).

    sleutels — {ключ в нижнем регистре: ключ}. «²» в Word — второе прочтение (zijn²
    → zijn#2). Если Word без артикля сам — ключ списка, берётся он: «de hoop» —
    существительное hoop, хотя главное прочтение формы «hoop» — hopen. Иначе —
    главное прочтение формы по vormen.json (afgelopen → aflopen)."""
    toks = [t for t in clean(word).lower().split() if t not in WEG]
    if len(toks) != 1:
        return None
    head = toks[0].replace("²", "#2")
    if head in sleutels:
        return sleutels[head]
    main = (vormen.get(head) or [None])[0]
    return sleutels.get(main.lower()) if main and "#" not in head else None


def grens(lijst, gedekt, uit):
    """Ранг (с 1) первого ключа без карточки и без uit; None — покрыто всё."""
    return next((i for i, k in enumerate(lijst, 1) if k not in gedekt and k not in uit), None)


def notities(profile=ANKI_PROFILE):
    """[(колода, Word, Rank)] каждой заметки «Frequentie NL». Колода — по карточке;
    карточка в фильтрованной колоде считается в своей исходной (odid)."""
    with kopie(collection_path(profile)) as con:
        velden = [n for (n,) in con.execute(
            "SELECT f.name FROM fields f JOIN notetypes nt ON nt.id = f.ntid "
            "WHERE nt.name = ? ORDER BY f.ord", (FREQUENTIE,))]
        rows = con.execute(
            "SELECT n.flds, MIN(d.name) FROM notes n "
            "JOIN notetypes nt ON nt.id = n.mid JOIN cards c ON c.nid = n.id "
            "JOIN decks d ON d.id = CASE WHEN c.odid THEN c.odid ELSE c.did END "
            "WHERE nt.name = ? GROUP BY n.id", (FREQUENTIE,)).fetchall()
    if not rows:
        sys.exit(f"в профиле {profile} нет заметок «{FREQUENTIE}»")
    w, r = velden.index("Word"), velden.index("Rank")
    return [(deck.replace("\x1f", "::"), clean(f[w]), clean(f[r]))
            for flds, deck in rows for f in [flds.split("\x1f")]]


def lijst_rapport(lijst, uit, vormen, notes):
    """Отчёт `lijst`: (строки, есть ли нарушения)."""
    sleutels = {k.lower(): k for k in lijst}
    rang = {k: i for i, k in enumerate(lijst, 1)}
    per_sleutel, buiten = {}, []
    for deck, word, rank in notes:
        k = sleutel(word, sleutels, vormen)
        if k is None:
            buiten.append((deck, word))
        else:
            per_sleutel.setdefault(k, []).append((deck, word, rank))
    kern = [(word, rank, k) for k, v in per_sleutel.items() for deck, word, rank in v if deck == KERN]
    n_kern = sum(deck == KERN for deck, _, _ in notes)
    dubbel = {k: v for k, v in per_sleutel.items() if len(v) > 1}
    kern_uit = [(word, k) for word, _, k in kern if k in uit]
    kern_buiten = [word for deck, word in buiten if deck == KERN]
    anders = sorted(((word, rank, k) for word, rank, k in kern if rank != str(rang[k])),
                    key=lambda t: -abs(int(t[1]) - rang[t[2]] if t[1].isdigit() else 10**9))
    werk = sorted((rang[k], k, word) for k, v in per_sleutel.items()
                  for deck, word, _ in v if deck != KERN and rang[k] <= HORIZON)
    g = grens(lijst, per_sleutel, uit)
    vrij = [k for k in lijst[g - 1:] if k not in per_sleutel and k not in uit][:10] if g else []
    out = [
        f"«{FREQUENTIE}»: {len(notes)} заметок — " + ", ".join(
            f"{d.split('::')[-1]} {n}" for d, n in sorted(Counter(d for d, _, _ in notes).items())),
        f"Kern сопоставлен: {n_kern - len(kern_buiten)}/{n_kern}"
        + (f" — вне списка: {', '.join(kern_buiten)}" if kern_buiten else ""),
        f"Werk/Reading вне списка: {len(buiten) - len(kern_buiten)} — "
        + ", ".join(word for deck, word in buiten if deck != KERN),
        f"Werk/Reading в топ-{HORIZON}: {len(werk)} — "
        + ", ".join(f"{word} {r}" + (f" ({k})" if k != word.split()[-1] else "") for r, k, word in werk),
        f"дублей (несколько Word на ключ): {len(dubbel)}" + "".join(
            f"\n  {k}: " + ", ".join(f"{word} ({deck.split('::')[-1]})" for deck, word, _ in v)
            for k, v in dubbel.items()),
        f"Kern на ключе uit: {len(kern_uit)}"
        + "".join(f"\n  {word} → {k}: {uit[k]}" for word, k in kern_uit),
        f"uit в топ-{HORIZON}: {sum(rang.get(k, HORIZON + 1) <= HORIZON for k in uit)}, "
        f"у каждой строки причина (проверяет сборка)",
        f"Rank ≠ ранг списка: {len(anders)} из {len(kern)} Kern; сильнее всего: "
        + ", ".join(f"{word} {rank}→{rang[k]}" for word, rank, k in anders[:12]),
        f"граница: ранг {g} ({lijst[g - 1]}); дальше без карточки: {' '.join(vrij)}"
        if g else "граница: покрыт весь список",
    ]
    return out, bool(dubbel or kern_uit or kern_buiten)


def tokens(example):
    """[(форма, имя ли)] — формы consensus_rank.words(). Имя — с заглавной не в начале
    предложения."""
    s = tekst(example)
    out = []
    for m in TOKEN.finditer(s.lower()):
        voor = s[:m.start()].rstrip(OPEN)
        out.append((m.group(), s[m.start()].isupper() and bool(voor) and voor[-1] not in ".!?…:"))
    return out


def splits(w, bekend):
    """(a, b), если w — составное из двух известных слов (стык s/e/en), каждое ≥ 3 букв.
    Делится только форма, которой нет в списке: у слова списка свой ранг (winter — не
    win + ter, vrijdag — не vrij + dag)."""
    for i in range(3, len(w) - 2):
        for voeg in ("", "s", "e", "en"):
            b = w[i + len(voeg):]
            if w[i:].startswith(voeg) and len(b) >= 3 and bekend(w[:i]) and bekend(b):
                return w[:i], b
    return None


def voorbeeld(word, example, rang, sleutels, uit, vormen):
    """Oordeel i+1 для примера карточки Word: fout — слова без единого известного
    прочтения, let_op — (слово, прочтения впереди), samengesteld — (слово, a, b),
    onbekend — форм нет в vormen.json, doel — цель в примере найдена."""
    k = sleutel(word, sleutels, vormen)
    r = rang.get(k)
    if r is None:
        return Oordeel(None, [], [], [], [], False)
    tot = BLOK if r <= BLOK else r - 1
    bekend = lambda key: key in uit or rang.get(key, tot + 1) <= tot
    toks = tokens(example)
    lezingen = lambda w: KLITIEK.get(w) or vormen.get(w)
    # Разорванный отделяемый глагол («neem … op»): частица и формы основы — тоже цель.
    # Частица — начало цели, но не её форма: «stap» у stappen — не «stap» + «pen».
    deeltje = next((w for w, _ in toks if k.startswith(w) and k[len(w):] in rang
                    and k not in (lezingen(w) or [])), None)
    basis = deeltje and k[len(deeltje):]
    is_doel = lambda w, ks: k in ks or deeltje is not None and (w == deeltje or basis in ks)
    vorm_bekend = lambda w: bool(ks := lezingen(w)) and (is_doel(w, ks) or all(map(bekend, ks)))
    fout, let_op, samengesteld, onbekend, doel = [], [], [], [], False
    for w, naam in toks:
        if naam:
            continue
        ks = lezingen(w)
        if ks is None:
            onbekend.append(w)
        elif is_doel(w, ks):
            doel = True
        elif nog := [x for x in ks if not bekend(x)]:
            if len(nog) < len(ks):
                let_op.append((w, nog))
            elif not any(x in rang for x in ks) and (delen := splits(w, vorm_bekend)):
                samengesteld.append((w, *delen))
            else:
                fout.append(w)
    return Oordeel(r, fout, let_op, samengesteld, onbekend, doel)


def kern_tsv(p):
    """lees_tsv партии Kern. Файл другой колоды — стоп: у Werk и Reading нет ранга в списке."""
    head, notes = lees_tsv(p)
    if head.get("deck") != KERN:
        sys.exit(f"{p}: колода {head.get('deck')} — kern.py только для {KERN}")
    return head, notes


def kern_voorbeelden(paden):
    """[(файл, Word, Example)] партий Kern."""
    return [(p.name, n["fields"]["Word"], n["fields"]["Example"])
            for p in map(Path, paden) for n in kern_tsv(p)[1]]


def herrang(paden, lijst, vormen):
    """Колонка Rank партий Kern := ранг Word в списке (D2: позиция в Anki = ранг).
    Word вне списка — стоп до записи, ни один файл не тронут. Остальные байты файла
    не меняются. ([(файл, Word, было, стало)], строк всего)."""
    rang = {k: i for i, k in enumerate(lijst, 1)}
    sleutels = {k.lower(): k for k in lijst}
    teksten, anders, buiten, n = {}, [], [], 0
    for p in map(Path, paden):
        kolommen = kern_tsv(p)[0]["columns"].split("\t")
        w, r = kolommen.index("Word"), kolommen.index("Rank")
        regels = p.read_text(encoding="utf-8").splitlines(keepends=True)
        for i, regel in enumerate(regels):
            kaal = regel.rstrip("\r\n")
            if regel.startswith("#") or not kaal.strip():
                continue
            n += 1
            velden = kaal.split("\t")
            k = sleutel(velden[w], sleutels, vormen)
            if k is None:
                buiten.append(f"{p.name}: {velden[w]}")
            elif velden[r] != str(rang[k]):
                anders.append((p.name, velden[w], velden[r], rang[k]))
                velden[r] = str(rang[k])
                regels[i] = "\t".join(velden) + regel[len(kaal):]
        teksten[p] = "".join(regels)
    if buiten:
        sys.exit("Word не сопоставлен со списком, файлы не тронуты: " + ", ".join(buiten))
    for p, inhoud in teksten.items():
        p.write_text(inhoud, encoding="utf-8")
    return anders, n


def check_rapport(lijst, uit, vormen, notes):
    """Отчёт `check`: (строки, есть ли нарушения)."""
    rang = {k: i for i, k in enumerate(lijst, 1)}
    sleutels = {k.lower(): k for k in lijst}
    oordelen = [(bron, word, example, voorbeeld(word, example, rang, sleutels, uit, vormen))
                for bron, word, example in notes]

    def toon(w):
        ks = KLITIEK.get(w) or vormen[w]
        return w + " " + "/".join(("" if k == w else k.replace("#2", "²") + " ")
                                  + str(rang.get(k, "—")) for k in ks)

    fout = [(b, w, e, o) for b, w, e, o in oordelen if o.fout or o.rang is None]
    let_op = Counter((w, tuple(nog)) for *_, o in oordelen for w, nog in o.let_op)
    samen = [(word, o) for _, word, _, o in oordelen if o.samengesteld]
    zonder_doel = [(word, e) for _, word, e, o in oordelen if o.rang and not o.doel]
    onbekend = sorted({w for *_, o in oordelen for w in o.onbekend})
    out = [f"i+1: {len(notes)} примеров, нарушают {len(fout)}; часть прочтений впереди — "
           f"{sum(let_op.values())}, составных — {sum(len(o.samengesteld) for _, o in samen)}, "
           f"цель не найдена — {len(zonder_doel)}"]
    for bron in dict.fromkeys(b for b, *_ in fout):
        out.append(f"{bron}:")
        out += [f"  {w} ({o.rang}): {e} — " + ", ".join(map(toon, o.fout)) if o.rang
                else f"  {w}: Word не сопоставлен со списком" for b, w, e, o in fout if b == bron]
    if let_op:
        out.append("часть прочтений впереди (какое в примере?): " + "; ".join(
            f"{w} → " + "/".join(k.replace("#2", "²") for k in nog) + f" ×{n}"
            for (w, nog), n in let_op.most_common()))
    if samen:
        out.append("составные — проходят, прочти: " + "; ".join(
            f"{w} = {a} + {b} ({word})" for word, o in samen for w, a, b in o.samengesteld))
    if zonder_doel:
        out.append("цель не найдена — прочти: " + "; ".join(f"{w}: {e}" for w, e in zonder_doel))
    if onbekend:
        out.append(f"нет в vormen.json: {', '.join(onbekend)} — пересобери список "
                   f"(consensus_rank.py берёт формы из frequentie/kern_*_anki.txt)")
    return out, bool(fout or onbekend)


def main():
    cmd, *paden = sys.argv[1:] or [""]
    if cmd == "lijst" and not paden:
        out, fout = lijst_rapport(*laad(), notities())
    elif cmd == "check" and paden:
        out, fout = check_rapport(*laad(), kern_voorbeelden(paden))
    elif cmd == "rank" and paden:
        lijst, _, vormen = laad()
        anders, n = herrang(paden, lijst, vormen)
        anders.sort(key=lambda t: -abs(int(t[2]) - t[3]) if t[2].isdigit() else -10**9)
        out, fout = [f"Rank: изменён у {len(anders)} из {n} строк; сильнее всего: " + ", ".join(
            f"{word} {was}→{nu}" for _, word, was, nu in anders[:12])], False
    else:
        sys.exit("usage: kern.py lijst | kern.py check FILE... | kern.py rank FILE...")
    print("\n".join(out))
    sys.exit(1 if fout else 0)


if __name__ == "__main__":
    main()

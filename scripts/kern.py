#!/usr/bin/env python3
"""kern.py — колода Frequentie::Kern по списку: какие ранги уже с карточкой и где граница.

    python3 scripts/kern.py lijst    # Word → ключ списка, дубли, граница

Список (lijst_v2.json) и карту форм (vormen.json) собирает
private/frequentie_pilot/consensus_rank.py с обеими таблицами решений; kern.py их
только читает. Коллекцию Anki — с копии (anki_vandaag.kopie), без записи.

Карточка у ключа есть, если его даёт Word любой заметки «Frequentie NL» (Kern,
Werk, Reading). Граница — первый ранг без карточки и без пометки uit.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anki_utils import ANKI_PROFILE, FREQUENTIE, KERN  # same dir
from anki_vandaag import clean, collection_path, kopie

REPO = Path(__file__).resolve().parent.parent
PILOT = REPO / "private" / "frequentie_pilot"
TABELLEN = (REPO / "frequentie" / "lijst_besluiten.tsv", PILOT / "lijst_besluiten_prive.tsv")
WEG = {"de", "het", "zich"}            # снимаются с Word до сопоставления
HORIZON = 2500                         # горизонт таблицы решений


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


def main():
    if sys.argv[1:] != ["lijst"]:
        sys.exit("usage: kern.py lijst")
    out, fout = lijst_rapport(*laad(), notities())
    print("\n".join(out))
    sys.exit(1 if fout else 0)


if __name__ == "__main__":
    main()

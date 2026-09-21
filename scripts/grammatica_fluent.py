#!/usr/bin/env python3
"""grammatica_fluent.py — grammar rules from the Link+ extracts into Fluent SR.

The grammar track is the spine: one SR item per RULE (not per example), so
every rule accumulates its own review_history. That history is the denominator
the error-pattern database never had — "failed 7 times" means nothing without
"attempted N times", and per-rule items give us N for free.

Rules are staged `--per-dag` per working day (Sunday off, like the frequency
deck). Fluent needs no configuration for this: read-db.py buckets by due_date
and caps by daily_limits, so the schedule lives in the data.

Only Python 3 stdlib. Reuses the backup/queue helpers of frequentie_fluent.py.

    python3 scripts/grammatica_fluent.py --regels grammatica/regels --dry-run
    python3 scripts/grammatica_fluent.py --regels grammatica/regels --per-dag 2
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frequentie_fluent import load, save, rebuild_queue  # noqa: E402

# Title and Russian gloss are split by hand, not by the regex: some headings
# carry two bracketed groups ("… als subject (herhaling) (повторение)"), which
# a single optional trailing group cannot match.
KOP_RE = re.compile(r"^### (?P<id>\d+\.\d+) · (?P<rest>.+?)\s*$", re.M)
# A labelled field runs to the NEXT label, block element or blank line — never
# to end of line. The extracts are prose, so a label lands mid-line and a rule
# spans two lines as soon as anything rewraps them (Prettier's proseWrap does,
# and did: 58 fields truncated across 34 rules, 2026-09-21). A `^…$` capture
# fails silently there — the parser still succeeds and writes half a rule into
# the learner's deck. Reading to the next label makes layout irrelevant.
LABELS = "Regel|По-русски|Частая ошибка"
VELD_RE = re.compile(
    rf"\*\*(?P<label>{LABELS}):\*\*\s*(?P<txt>.+?)"
    rf"(?=\*\*(?:{LABELS}|Voorbeelden|Подсказка|⚠)|\n\s*\n|\n\s*[-|#>]|\Z)",
    re.S,
)
# Same reason, without the `$`: the heading shares a line with its first
# example in some blocks, and gains a line of its own when rewrapped.
VOORBEELD_KOP_RE = re.compile(r"\*\*Voorbeelden[^*]*\*\*", re.M)
VOORBEELD_RE = re.compile(r"^-\s*`(?P<nl>[^`]+)`", re.M)
BACKTICK_RE = re.compile(r"`([^`]+)`")
THEMA_RE = re.compile(r"thema_(\d+)")
# de/het and adjective endings are A2 material even in a 0->A2 book; the rest
# of themes 1-4 is A1. Only used to stamp `difficulty` (a CEFR STRING — never
# a number, that key collides with FSRS; see nederlands-change-control).
A2_REGELS = {"5.1", "5.2", "1.14", "1.15", "2.5", "3.1", "3.2", "7.1", "7.2"}


def strip_md(text: str) -> str:
    """Card text: markdown emphasis dropped, whitespace collapsed to one line.

    Collapsing belongs here rather than at each call site — it is what makes
    every extracted field wrap-invariant, and a card that keeps a newline from
    the source layout renders as a broken line for the learner.
    """
    # Collapse BEFORE stripping emphasis: `.` does not cross a newline, so a
    # `**bold**` span broken by a line wrap survives the emphasis regex and
    # the asterisks land on the card.
    text = re.sub(r"\s+", " ", text.replace("`", "")).strip()
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def velden(blok: str) -> dict[str, str]:
    """Labelled fields of one rule block, keyed by label, whitespace collapsed.

    Collapsing is what makes the result wrap-invariant: the same rule yields
    the same string whether it sits on one line or five.
    """
    uit = {}
    for m in VELD_RE.finditer(blok):
        uit.setdefault(m.group("label"), strip_md(m.group("txt")))
    return uit


def haal_voorbeelden(blok: str) -> list[str]:
    """Key forms for the item's `answer` field.

    Preferred source is the block's "Voorbeelden / Примеры" list. A third of the
    rules present their material as a table instead (pronoun paradigms, the
    spelling pairs), so those fall back to the block's backticked fragments.
    Either way this is a reference cue for the tutor, not a graded answer — the
    exercise itself is generated from the rule plus the day's words.
    """
    kop = VOORBEELD_KOP_RE.search(blok)
    if kop:
        uit = [strip_md(m.group("nl")) for m in VOORBEELD_RE.finditer(blok[kop.end():])]
        if uit:
            return uit[:3]
    gezien, uit = set(), []
    for m in BACKTICK_RE.finditer(blok):
        frag = strip_md(m.group(1))
        if frag and frag not in gezien:
            gezien.add(frag)
            uit.append(frag)
    return uit[:4]


def parse_regels(path: Path) -> list[dict]:
    md = path.read_text(encoding="utf-8")
    thema = (THEMA_RE.search(path.name) or [None, "00"])[1]
    koppen = list(KOP_RE.finditer(md))
    rules = []
    for i, kop in enumerate(koppen):
        blok = md[kop.end(): koppen[i + 1].start() if i + 1 < len(koppen) else len(md)]
        veld = velden(blok)
        voorbeelden = haal_voorbeelden(blok)
        rest = kop.group("rest")
        # The LAST bracketed group is the Russian gloss; earlier ones
        # ("(herhaling)") belong to the Dutch title.
        snede = rest.rfind(" (")
        title = (rest[:snede] if snede != -1 else rest).strip()
        gloss = rest[snede:].strip(" ()") if snede != -1 else ""
        rules.append({
            "id": kop.group("id"),
            "thema": thema,
            "title": title,
            "gloss": gloss,
            "regel": veld.get("Regel", ""),
            "russisch": veld.get("По-русски", ""),
            "voorbeelden": voorbeelden,
            "valkuil": veld.get("Частая ошибка", ""),
            "bron": f"{path.parent.name}/{path.name}#{kop.group('id')}",
        })
    return rules


def werkdagen(start: date, aantal: int) -> list[date]:
    """`aantal` dates from `start`, Sundays skipped (weekday 6)."""
    out, d = [], start
    while len(out) < aantal:
        if d.weekday() != 6:
            out.append(d)
        d += timedelta(days=1)
    return out


# The book's order contains a measured dependency inversion: rule 1.1 (verb
# stem = infinitive minus -en) cites 7.1 and 7.2 for `wonen -> woon` and
# `spellen -> spel`, and 4.1 (plurals) cites 7.1 for `naam -> namen` — yet 7.1
# and 7.2 are the last two rules of themes 1-4. Teaching the syllable boundary
# first removes three forward references at once, and it is also Alex's most
# frequent spelling error (spelling_vowel_doubling, 6 occurrences).
VOORRANG = ["7.1", "7.2"]


def sorteer(rules: list[dict], voorrang: list[str] = VOORRANG) -> list[dict]:
    """Course order: `voorrang` rules first, then by thema and rule number."""
    def key(r):
        groep, nr = r["id"].split(".")
        vroeg = voorrang.index(r["id"]) if r["id"] in voorrang else len(voorrang)
        return (vroeg, r["thema"], int(groep), int(nr))
    return sorted(rules, key=key)


def do_regels(sr: dict, rules: list[dict], today: str, per_dag: int) -> dict:
    items = sr.setdefault("items", {})
    rules = sorteer(rules)
    nieuw = [r for r in rules if f"gram_lp_{r['id']}" not in items]
    dagen = werkdagen(date.fromisoformat(today), -(-len(nieuw) // per_dag))
    plan, added = [], 0
    for n, r in enumerate(nieuw):
        due = dagen[n // per_dag].isoformat()
        iid = f"gram_lp_{r['id']}"
        inhoud = f"{r['id']} · {r['title']}"
        if r["regel"]:
            inhoud += f" — {r['regel']}"
        if r["russisch"]:
            inhoud += f" | RU: {r['russisch']}"
        if r["valkuil"]:
            inhoud += f" | Частая ошибка: {r['valkuil']}"
        items[iid] = {
            "id": iid,
            "type": "grammar_rule",
            "content": inhoud,
            "answer": " · ".join(r["voorbeelden"]) or r["regel"],
            "category": f"grammatica_lp_thema{r['thema']}",
            "difficulty": "A2" if r["id"] in A2_REGELS else "A1",
            "bron": r["bron"],
            "created_date": today,
            "due_date": due,
            "interval_days": 1,
            "repetitions": 0,
            "easiness_factor": 2.5,
            "stability": None,
            "fsrs_difficulty": None,
            "consecutive_correct": 0,
            "consecutive_incorrect": 0,
            "last_reviewed": today,
            "last_quality": 3,
            "mastery_level": 0,
            "total_reviews": 0,
            # Same reason as the daily sentences: read-db sorts by priority and
            # then cuts at daily_limits, so a rule below the cut is never
            # served. Only the rules actually due today get "critical".
            "priority": "critical" if due <= today else "high",
        }
        plan.append((due, r["id"], r["title"]))
        added += 1
    return {"added": added, "skipped": len(rules) - len(nieuw), "plan": plan}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--regels", type=Path, required=True,
                    help="directory with thema_NN_*.md rule extracts")
    ap.add_argument("--per-dag", type=int, default=2,
                    help="new rules per working day (default: 2)")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    bestanden = sorted(args.regels.glob("thema_*.md"))
    if not bestanden:
        sys.exit(f"no thema_*.md in {args.regels}")
    rules = [r for f in bestanden for r in parse_regels(f)]
    if not rules:
        sys.exit("no rules parsed — check the '### N.M · Title' heading format")

    today = date.today().isoformat()
    sr = load()
    res = do_regels(sr, rules, today, args.per_dag)

    print(f"файлов: {len(bestanden)}  правил разобрано: {len(rules)}")
    print(f"новых: {res['added']}  уже в базе: {res['skipped']}")
    if res["plan"]:
        print(f"\nграфик ({args.per_dag}/рабочий день, воскресенье пропускается):")
        huidige = None
        for due, rid, title in res["plan"]:
            kop = due if due != huidige else " " * len(due)
            huidige = due
            print(f"  {kop}  {rid:5} {title}")
    if args.dry_run:
        print("\n--dry-run: ничего не записано")
        return 0
    rebuild_queue(sr, today)
    backup = save(sr, "grammatica")
    print(f"\nзаписано. бэкап: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

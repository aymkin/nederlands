#!/usr/bin/env python3
"""Lint a *_anki.txt Anki import file against this repo's conventions.

Read-only. Stdlib only. Checks:
  1. Header directives present (#separator:tab is mandatory).
  2. Every data row uses literal TAB separators and has the expected
     column count (from #columns, else #tags column:N, else the modal
     count of the file itself).
  3. #html:true is set whenever any field contains [sound:...] (commit
     8cd356c: sound tags without html:true render as literal text).
  4. Tag taxonomy shape: each tag in the tags column is `::`-separated,
     no spaces inside a tag, known top-level namespaces get a nod.
  5. Voldemort rule: the strings Rusland / Росси* must never appear in
     content (commit 5be6931).
  6. HEURISTIC: Dutch noun-suffix words in the Word column (first
     column of the 5-col format) missing a de/het/een article.
     Suffix-based — expect false negatives (most nouns have no marker
     suffix) and occasional false positives. Advisory only.

Usage:
    python3 anki_lint.py path/to/file_anki.txt [--strict]

Exit codes: 0 clean, 1 findings (with --strict, heuristics count too),
2 file/usage error.
"""
import argparse
import re
import sys
from pathlib import Path

VOLDEMORT_RE = re.compile(r"rusland|росси", re.IGNORECASE)
SOUND_RE = re.compile(r"\[sound:[^\]]+\]")
TAG_OK_RE = re.compile(r"^[A-Za-z0-9_+:.-]+$")
ARTICLE_RE = re.compile(r"^(de|het|een)\s", re.IGNORECASE)
# Common Dutch noun suffixes (derivational, fairly reliably nouns)
NOUN_SUFFIXES = ("heid", "teit", "isme", "schap", "atie", "ing",
                 "sel", "ment", "tje")
KNOWN_NAMESPACES = ("link", "sententiae", "constructies", "de_opmaat")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file")
    ap.add_argument("--strict", action="store_true",
                    help="heuristic findings also set exit code 1")
    args = ap.parse_args()

    path = Path(args.file)
    try:
        text = path.read_text("utf-8")
    except OSError as e:
        print(f"cannot read {path}: {e}")
        sys.exit(2)

    lines = text.splitlines()
    directives = {}
    data = []  # (lineno, raw)
    for n, line in enumerate(lines, 1):
        if line.startswith("#"):
            m = re.match(r"#([a-z ]+):(.*)", line)
            if m:
                directives[m.group(1)] = m.group(2)
        elif line.strip():
            data.append((n, line))

    errors, warns, heur = [], [], []

    # 1. headers
    if directives.get("separator") != "tab":
        errors.append("missing/incorrect '#separator:tab' directive")
    html_true = directives.get("html") == "true"

    # expected column count
    expected = None
    source = None
    if "columns" in directives:
        expected = len(directives["columns"].split("\t"))
        source = "#columns"
        if expected == 1:
            errors.append("#columns has no literal TABs — the column "
                          "list itself must be tab-separated")
            expected = None
    if expected is None and "tags column" in directives:
        try:
            expected = int(directives["tags column"])
            source = "#tags column"
        except ValueError:
            pass
    counts = [len(raw.split("\t")) for _, raw in data]
    if expected is None and counts:
        expected = max(set(counts), key=counts.count)
        source = "modal row count (no #columns / #tags column header)"

    tags_col = None
    if "tags column" in directives:
        try:
            tags_col = int(directives["tags column"])
        except ValueError:
            errors.append(f"unparseable '#tags column:"
                          f"{directives['tags column']}'")

    # 2-5. row checks
    any_sound = False
    for (n, raw) in data:
        cols = raw.split("\t")
        if "\t" not in raw and expected and expected > 1:
            errors.append(f"line {n}: no literal TAB — row will import "
                          "as a single field (silent corruption)")
            continue
        if expected and len(cols) != expected:
            errors.append(f"line {n}: {len(cols)} columns, expected "
                          f"{expected} (from {source})")
        if SOUND_RE.search(raw):
            any_sound = True
        m = VOLDEMORT_RE.search(raw)
        if m:
            errors.append(f"line {n}: VOLDEMORT violation "
                          f"({m.group(0)!r}) — Rusland/Россия must never "
                          "appear in content")
        if tags_col and len(cols) >= tags_col:
            for tag in cols[tags_col - 1].split():
                if not TAG_OK_RE.match(tag):
                    warns.append(f"line {n}: tag {tag!r} has unexpected "
                                 "characters")
                elif "::" not in tag:
                    warns.append(f"line {n}: tag {tag!r} is flat — repo "
                                 "taxonomy is hierarchical (a::b::c)")
                elif tag.split("::")[0] not in KNOWN_NAMESPACES:
                    warns.append(f"line {n}: tag namespace "
                                 f"{tag.split('::')[0]!r} not in "
                                 f"{KNOWN_NAMESPACES} (fine if deliberate)")
        # 6. noun-article heuristic on Word column (5-col Word format)
        if source == "#columns" and \
                directives.get("columns", "").startswith("Word\t"):
            word = cols[0].strip()
            if word and " " not in word and word.islower() \
                    and word.endswith(NOUN_SUFFIXES) \
                    and not ARTICLE_RE.match(word):
                heur.append(f"line {n}: {word!r} looks like a noun "
                            "(suffix) but has no de/het/een article")

    if any_sound and not html_true:
        errors.append("[sound:...] present but '#html:true' missing — "
                      "audio will render as literal text (8cd356c)")

    # report
    print(f"=== anki_lint: {path.name} ===")
    print(f"directives: {directives}")
    print(f"data rows: {len(data)}, expected columns: {expected} "
          f"({source})")
    for e in errors:
        print(f"ERROR  {e}")
    for w in warns:
        print(f"WARN   {w}")
    for h in heur:
        print(f"HEUR   {h}  [heuristic — verify by hand]")
    n_bad = len(errors) + (len(heur) if args.strict else 0)
    print(f"\n{len(errors)} errors, {len(warns)} warnings, "
          f"{len(heur)} heuristic flags")
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()

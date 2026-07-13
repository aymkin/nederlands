#!/usr/bin/env python3
"""Mastery-gate report for every curriculum unit of a course.

Read-only. Stdlib only. Reuses the REAL gate logic by importing
`check()` from scripts/fluent_import.py (same repo), so this report can
never drift from what `--check`/`--advance` actually enforce:

    ready = total > 0
            AND mastered/total >= 0.80   (mastery_level >= 3)
            AND red == 0                 (consecutive_incorrect >= 2)

Usage:
    python3 gate_report.py [--course link] [--data-dir DIR]

Exit code: 0 on success, 1 if scripts/fluent_import.py cannot be
imported (wrong repo layout).
"""
import argparse
import json
import sys
from pathlib import Path

# repo/.claude/skills/nederlands-diagnostics-and-tooling/scripts/<this file>
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    import fluent_import as fi
except ImportError as e:
    print(f"cannot import scripts/fluent_import.py from {REPO_ROOT}: {e}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--course", default="link")
    ap.add_argument("--data-dir",
                    default=str(Path.home() / ".claude" / "fluent-data"))
    args = ap.parse_args()

    sr_path = Path(args.data_dir) / "spaced-repetition.json"
    manifest = fi.load_manifest(REPO_ROOT / args.course)
    sr = json.loads(sr_path.read_text("utf-8"))
    all_ids = list(sr.get("items", {}))

    print(f"=== Mastery-gate report — course '{args.course}' ===")
    print(f"gate: total>0 AND mastery>=3 on >={fi.MASTERY_THRESHOLD:.0%} "
          "AND zero red cards (consecutive_incorrect>=2)\n")
    hdr = f"{'unit':<10} {'status':<8} {'cards':>5} {'m>=3':>5} " \
          f"{'pct':>7} {'red':>4}  gate"
    print(hdr)
    print("-" * len(hdr))

    covered = set()
    for unit in manifest["units"]:
        uid = unit["id"]
        r = fi.check(args.course, REPO_ROOT, sr_path, unit_id=uid)
        prefix = fi.unit_prefix(args.course, uid)
        covered.update(i for i in all_ids if i.startswith(prefix))
        if r["total"] == 0:
            gate = "-- (no cards imported)"
        elif r["ready"]:
            gate = "READY -> --advance"
        else:
            need = int(fi.MASTERY_THRESHOLD * r["total"] + 0.999)
            gate = f"not ready (need {need} mastered" \
                   + (f", {r['red']} red)" if r["red"] else ")")
        pct = (r["mastered"] / r["total"]) if r["total"] else 0.0
        print(f"{uid:<10} {unit.get('status', '?'):<8} {r['total']:>5} "
              f"{r['mastered']:>5} {pct:>6.1%} {r['red']:>4}  {gate}")

    outside = [i for i in all_ids if i not in covered]
    print(f"\n{len(outside)} items outside this course's prefixes "
          "(legacy vocab_*, error patterns, other courses)")
    active = [u["id"] for u in manifest["units"]
              if u.get("status") == "active"]
    print(f"active unit per curriculum.json: {active} "
          "(exactly one is the invariant)")


if __name__ == "__main__":
    main()

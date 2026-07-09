"""Generate random centos matching only the TOTAL morae (sum, not exact
sequence) of each real cento segment, still respecting real word boundaries
at the segment cut.

Reuses scheme.json's row structure (via pycento.scheme.iter_scheme_rows) to
know how many output lines to generate and how many segments each has --
same per-segment is_start-driven line accumulation as step-04 (a segment
starts a new line unless the previous one is still open) -- but looks each
line's segments up by TOTAL morae in data/segment_table_by_total.json instead
of by exact sequence, and never requires two segments to come from
genuinely adjacent Virgil verses (unlike step-04): every multi-segment line
is filled by independently drawing a start-entry and an end-entry and
re-scanning the joint (see pycento/generate.py's rescan_joint, which needs a
locally-built latin_scansion grammar archive -- see
scripts/fetch_latin_scansion.sh; pass --allow-unchecked-merges to skip
re-validation, e.g. if that isn't set up). Continuation
rows from scheme.json are NOT specially preserved here: a line that
originated from a `type=` continuation is treated exactly like any other
multi-segment line.

data/segment_table_by_total.json only covers a fixed, curated set of 8
(start_total, end_total) splits (see step-03-Build-Segment-Table-Canon-Caesura.py)
and has no single-segment (whole-line) entries at all -- lines whose required
split isn't covered are skipped and logged rather than expanding step-03's
scope here.

Usage:
    python step-05-Generate-Centos-Metric-Close.py [--count N] [--works Aeneid ...]
    python step-05-Generate-Centos-Metric-Close.py --count 100 --allow-unchecked-merges

Output: data/generated-compact/loose/cento_{n:04d}.xml
"""

import argparse
import json
import os.path as op
import random

from pycento.generate import MergeStats, ResolvedSegment, assemble_lines, resolve_merge_slot, work_of, write_poem
from pycento.scansion import ScansionUnavailable
from pycento.scheme import iter_scheme_rows

_ROOT = op.dirname(op.abspath(__file__))


def _line_totals(line_segs) -> list:
    """The morae total of each segment accumulated for one output line,
    anceps-normalized (last mora forced to 2)."""
    totals = []
    for pattern, _ in line_segs:
        totals.append(sum(pattern[:-1]) + 2 if pattern else 0)
    return totals


def _filter_by_work(candidates: list, works) -> list:
    if not works:
        return candidates
    return [e for e in candidates if work_of(e["id"]) in works]


class LineSkipped(Exception):
    pass


def resolve_line(line_segs, by_total: dict, works, used_refs: set, allow_unchecked: bool, stats: MergeStats) -> list:
    """Resolve one output line's segments (1 or 2) by total morae. Raises
    LineSkipped if the required split isn't covered by by_total, or if no
    valid combination could be found."""
    totals = _line_totals(line_segs)

    if len(totals) != 2:
        raise LineSkipped(f"{len(totals)}-segment lines aren't covered by "
                           f"segment_table_by_total.json (curated splits are all 2-part)")

    start_total, end_total = totals
    key = f"{start_total}/{end_total}"
    entry = by_total.get(key)
    if entry is None:
        raise LineSkipped(f"split {key} isn't one of the curated splits in segment_table_by_total.json")

    a_candidates = _filter_by_work(entry.get("start", []), works)
    b_candidates = _filter_by_work(entry.get("end", []), works)

    result = resolve_merge_slot([], a_candidates, b_candidates, used_refs, allow_unchecked, stats=stats)
    if result is None:
        raise LineSkipped(f"could not resolve start/end candidates for split {key}")
    words_a, words_b, ids = result
    used_refs.update(ids)
    return [
        ResolvedSegment(source=ids[0], words=words_a, continued=False),
        ResolvedSegment(source=ids[1], words=words_b, continued=False),
    ]


def generate_poem(rows: list, by_total: dict, works, allow_unchecked: bool, stats: MergeStats):
    used_refs: set = set()
    all_lines: list = []
    current_line: list = []
    skipped_lines = 0

    for segs in rows:
        for pattern, is_start in segs:
            if is_start and current_line:
                try:
                    all_lines.append(resolve_line(current_line, by_total, works, used_refs, allow_unchecked, stats))
                except LineSkipped:
                    skipped_lines += 1
                current_line = []
            current_line.append((pattern, is_start))

    if current_line:
        try:
            all_lines.append(resolve_line(current_line, by_total, works, used_refs, allow_unchecked, stats))
        except LineSkipped:
            skipped_lines += 1

    return assemble_lines(all_lines), skipped_lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--works", nargs="*", default=None, choices=["Aeneid", "Eclogues", "Georgics"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--allow-unchecked-merges", action="store_true",
                         help="Skip re-scanning merged joints (rescan_joint is not implemented yet).")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print("Loading scheme.json...")
    with open(op.join(_ROOT, "scheme.json"), encoding="utf-8") as fh:
        scheme_table = json.load(fh)["table"]
    rows = list(iter_scheme_rows(scheme_table))
    print(f"  {len(rows)} rows")

    print("Loading segment table (by total)...")
    with open(op.join(_ROOT, "data", "segment_table_by_total.json"), encoding="utf-8") as fh:
        by_total = json.load(fh)
    print(f"  {len(by_total)} curated splits")

    out_dir = op.join(_ROOT, "data", "generated-compact", "loose")

    print(f"\nGenerating {args.count} poems -> {out_dir}/")
    written, failed = 0, 0
    total_line_skips = 0
    stats = MergeStats()
    for n in range(1, args.count + 1):
        try:
            lines, skipped_lines = generate_poem(rows, by_total, args.works, args.allow_unchecked_merges, stats)
        except ScansionUnavailable as exc:
            print(f"\nMulti-segment lines here are always independently combined (step-05 "
                  f"never uses pre-validated adjacent-verse pairs) and every one needs a "
                  f"re-scanned merge, but the scansion grammar isn't available: {exc}\n"
                  f"Pass --allow-unchecked-merges to generate anyway.")
            raise SystemExit(1)
        total_line_skips += skipped_lines
        if not lines:
            print(f"  [SKIP] poem {n}: no lines resolved")
            failed += 1
            continue
        out_path = op.join(out_dir, f"cento_{n:04d}.xml")
        write_poem(lines, out_path)
        written += 1
        if n % 100 == 0:
            print(f"  {n}/{args.count}")

    print(f"Done. Generated {written}/{args.count} poems ({failed} skipped) in {out_dir}/")
    print(f"  {total_line_skips} line(s) skipped across all generated poems "
          f"(uncovered splits / unresolved candidates)")
    print("Merge-slot resolution:")
    print(stats.summary())


if __name__ == "__main__":
    main()

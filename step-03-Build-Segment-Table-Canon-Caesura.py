"""Build a segment table indexed by TOTAL morae, covering every split, the
whole-verse case, and every genuine cross-line continuation actually needed
by the gold cento.

step-02 indexes the EXACT syllable sequence of every fragment scheme.json
actually attests. This script is looser: for every (start_total, end_total)
morae split scheme.json's own cento lines require -- e.g. (10, 14), meaning
"a 10-morae opening half plus a 14-morae closing half" -- it finds every
word-boundary-respecting prefix/suffix of a well-formed Virgil hexameter
whose morae SUM to that target, regardless of the specific long/short
arrangement within it. That's a much bigger, less exact candidate pool than
step-02's, meant for step-04/step-05 to draw fresh vocabulary from while
still respecting the metrical CAESURA SHAPE of a real cento line (same
number of segments, same split point) -- not necessarily the same
dactyl/spondee pattern.

It reuses the exact same word-boundary machinery as step-02
(IndexedLine.boundary_word_count_by_total, in pycento/virgil_index.py): a
morae total is only accepted as a start match if that many morae land
exactly on a word boundary, and as an end match if (24 - total) does --
never a mid-word cut. See pycento.virgil_index.match_by_total().

The splits, the whole-verse bucket, and the continuation pairs are all
derived directly from scheme.json via pycento.scheme.build_line_specs (the
same real-cento-line reconstruction step-04/step-05 use, which also flags
each line whose first segment is a genuine `type="sq"` continuation of the
previous line's last segment). This covers:
  - every (start_total, end_total) pair actually required by a 2-segment
    line, whatever it sums to (previously only 8 hardcoded splits were
    covered, silently skipping every line whose split wasn't one of them);
  - a "whole" bucket of every well-formed Virgil hexameter, for 1-segment
    (whole-verse) lines, which previously had no entries at all here;
  - a "sequential" bucket of pre-validated ADJACENT Virgil-verse pairs (same
    file, raw_index differs by exactly 1), for the boundary segments of a
    genuine `type="sq"` continuation -- so step-05 can still draw those two
    segments from two verses that were really next to each other in Virgil,
    even though it otherwise only matches by total morae. Without this,
    "loose" generation would glue together two unrelated verses at exactly
    the points the gold cento marks as a deliberate sequential quotation.

Output structure (data/segment_table_by_total.json):
    {
      "<start_total>/<end_total>": {
        "start": [ {found_object}, ... ],   # prefixes summing to start_total
        "end":   [ {found_object}, ... ]    # suffixes summing to end_total
      },
      ...
      "whole": [ {found_object}, ... ],           # every well-formed hexameter, in full
      "sequential": {
        "<a_total>/<b_total>": [ [found_object_a, found_object_b], ... ],
        ...
      }
    }
found_object is the same shape as step-02's (id/filepath/kind/text/words).
"""

import json
import os.path as op
from typing import Dict, List, Set, Tuple

from pycento.scheme import build_line_specs, iter_scheme_rows, line_segment_totals
from pycento.virgil_index import load_virgil_index, match_by_total, match_consecutive_pairs_by_total

_ROOT = op.dirname(op.abspath(__file__))


def required_splits(table: list) -> Tuple[Set[Tuple[int, int]], bool, Set[Tuple[int, int]]]:
    """Walk scheme.json's rows into real cento lines (pycento.scheme.build_line_specs)
    and collect: every distinct 2-segment (start_total, end_total) split
    actually needed; whether any 1-segment (whole verse) line occurs; and
    every distinct (a_total, b_total) needed at a genuine continuation
    boundary (the previous line's last-segment total, and this line's
    first-segment total)."""
    line_specs = build_line_specs(iter_scheme_rows(table))
    totals_per_line = [line_segment_totals(spec.segs) for spec in line_specs]

    splits: Set[Tuple[int, int]] = set()
    needs_whole = False
    seq_totals: Set[Tuple[int, int]] = set()

    for i, spec in enumerate(line_specs):
        totals = totals_per_line[i]
        if len(totals) == 1:
            needs_whole = True
        elif len(totals) == 2:
            splits.add((totals[0], totals[1]))

        if spec.continues_previous and i > 0:
            prev_totals = totals_per_line[i - 1]
            seq_totals.add((prev_totals[-1], totals[0]))

    return splits, needs_whole, seq_totals


def build_table(
    splits: Set[Tuple[int, int]], needs_whole: bool, seq_totals: Set[Tuple[int, int]],
) -> Dict[str, object]:
    print("Indexing Virgil corpus...")
    index = load_virgil_index(annotated=True)
    print(f"  {len(index)} well-formed hexameters")

    # Each distinct total is matched once and shared across every split that
    # needs it (e.g. total=10 backs both "10/14" as a start and "14/10" as
    # an end), instead of re-scanning the whole index per split.
    start_cache: Dict[int, List[dict]] = {}
    end_cache: Dict[int, List[dict]] = {}

    table: Dict[str, object] = {}
    for start_total, end_total in sorted(splits):
        if start_total not in start_cache:
            start_cache[start_total] = match_by_total(start_total, True, index)
        if end_total not in end_cache:
            end_cache[end_total] = match_by_total(end_total, False, index)

        starts = start_cache[start_total]
        ends = end_cache[end_total]
        key = f"{start_total}/{end_total}"
        table[key] = {"start": starts, "end": ends}
        print(f"  {key}: {len(starts)} start matches, {len(ends)} end matches")

    if needs_whole:
        whole = match_by_total(24, True, index)
        table["whole"] = whole
        print(f"  whole: {len(whole)} whole-verse matches")

    if seq_totals:
        sequential: Dict[str, list] = {}
        for a_total, b_total in sorted(seq_totals):
            key = f"{a_total}/{b_total}"
            pairs = match_consecutive_pairs_by_total(a_total, b_total, index)
            sequential[key] = pairs
            print(f"  sequential {key}: {len(pairs)} adjacent-verse pairs")
        table["sequential"] = sequential

    return table


if __name__ == "__main__":
    with open(op.join(_ROOT, "scheme.json"), encoding="utf-8") as fh:
        scheme_table = json.load(fh)["table"]
    splits, needs_whole, seq_totals = required_splits(scheme_table)
    print(f"Required: {len(splits)} distinct 2-segment splits"
          f"{', whole-verse lines' if needs_whole else ''}"
          f"{f', {len(seq_totals)} continuation-boundary total(s)' if seq_totals else ''}")

    table = build_table(splits, needs_whole, seq_totals)

    out_path = op.join(_ROOT, "data", "segment_table_by_total.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"\nWrote {out_path}")

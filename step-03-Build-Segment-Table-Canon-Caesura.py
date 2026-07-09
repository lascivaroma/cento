"""Build a segment table indexed by TOTAL morae, for a curated set of splits.

step-02 indexes the EXACT syllable sequence of every fragment scheme.json
actually attests. This script is looser: for a fixed list of (start_total,
end_total) morae splits -- e.g. (10, 14), meaning "a 10-morae opening half
plus a 14-morae closing half" -- it finds every word-boundary-respecting
prefix/suffix of a well-formed Virgil hexameter whose morae SUM to that
target, regardless of the specific long/short arrangement within it. That's
a much bigger, less exact candidate pool than step-02's, meant for step-04 to
draw fresh vocabulary from while still respecting the metrical shape of a
real cento line.

It reuses the exact same word-boundary machinery as step-02
(IndexedLine.boundary_word_count_by_total, in pycento/virgil_index.py): a
morae total is only accepted as a start match if that many morae land
exactly on a word boundary, and as an end match if (24 - total) does --
never a mid-word cut. See pycento.virgil_index.match_by_total().

The splits below were supplied directly (not derived from segment_stats.csv):
every pair sums to 24 morae -- a full hexameter split into a start segment
and an end segment. 7 of the 8 exactly match `schema` values already observed
in segment_stats.csv; 4/20 sums to 24 too but isn't yet attested in the gold
cento.xml.

Output structure (data/segment_table_by_total.json):
    {
      "<start_total>/<end_total>": {
        "start": [ {found_object}, ... ],   # prefixes summing to start_total
        "end":   [ {found_object}, ... ]    # suffixes summing to end_total
      },
      ...
    }
found_object is the same shape as step-02's (id/filepath/kind/text/words).
"""

import json
import os.path as op
from typing import Dict, List, Tuple

from pycento.virgil_index import load_virgil_index, match_by_total

_ROOT = op.dirname(op.abspath(__file__))

_SPLITS: List[Tuple[int, int]] = [
    (6, 18),
    (10, 14),
    (11, 13),
    (12, 12),
    (16, 8),
    (8, 16),
    (4, 20),
    (14, 10),
]


def build_table() -> Dict[str, dict]:
    print("Indexing Virgil corpus...")
    index = load_virgil_index(annotated=True)
    print(f"  {len(index)} well-formed hexameters")

    # Each distinct total is matched once and shared across every split that
    # needs it (e.g. total=10 backs both "10/14" as a start and "14/10" as
    # an end), instead of re-scanning the whole index per split.
    start_cache: Dict[int, List[dict]] = {}
    end_cache: Dict[int, List[dict]] = {}

    table: Dict[str, dict] = {}
    for start_total, end_total in _SPLITS:
        if start_total not in start_cache:
            start_cache[start_total] = match_by_total(start_total, True, index)
        if end_total not in end_cache:
            end_cache[end_total] = match_by_total(end_total, False, index)

        starts = start_cache[start_total]
        ends = end_cache[end_total]
        key = f"{start_total}/{end_total}"
        table[key] = {"start": starts, "end": ends}
        print(f"  {key}: {len(starts)} start matches, {len(ends)} end matches")

    return table


if __name__ == "__main__":
    table = build_table()

    out_path = op.join(_ROOT, "data", "segment_table_by_total.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"\nWrote {out_path}")

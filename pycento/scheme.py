"""Shared parsing of scheme.json's "table" (produced by step-01-Build-Stats.py).

Each row is a flat mix of the int 0 (cento-line-start marker) and morae
tuples (one per segment, elisions already excluded). See iter_scheme_patterns()
for the exact meaning of the 0 marker and how a segment's position (start/end
of a cento line) determines whether it must come from the START or the END of
a Virgil verse.
"""

import json
from typing import Iterator, List, Tuple


def iter_scheme_patterns(table: List[list]) -> Iterator[Tuple[Tuple[int, ...], bool]]:
    """Walk scheme.json's "table", yielding (pattern, is_start) per segment tuple.

    Each row is a flat sequence mixing the int 0 (cento-line-start marker)
    with morae tuples (one per segment, serialized as JSON lists). A tuple
    immediately preceded by 0 is the FIRST segment of a cento line: if that
    line has a second segment, this first one supplies the opening of the new
    hexameter, so by cento-construction convention it must be lifted from the
    START of some Virgil verse. A tuple with nothing (or anything other than
    0) immediately before it is NOT line-initial -- in this corpus a cento
    line never has more than two segments, so a non-initial tuple is always
    the one that CLOSES the hexameter, and must be lifted from the END of
    some Virgil verse.

    Rows can contain more than one (0, tuple) pair when a `type=` XML
    continuation merges a later cento line into the same row as the one
    before it (step-01's `table[-1].extend([0, *scheme])`). Two shapes occur:
      - [tupA, 0, tupB]     : tupA has nothing before it -> end;
                              tupB is preceded by 0        -> start.
      - [0, tupA, 0, tupB]  : both tupA and tupB are each preceded by a 0
                              -> both start (two consecutive whole-verse
                              lines, the second a continuation of the first).
    Tracking only "the item immediately before this one" as we scan resolves
    both shapes (and any row shorter than that) without special-casing.
    """
    for row in table:
        prev = None
        for item in row:
            if isinstance(item, list):
                yield tuple(item), (prev == 0)
            prev = item


RowShape = Tuple[Tuple[Tuple[int, ...], bool], ...]


def iter_scheme_rows(table: List[list]) -> Iterator[RowShape]:
    """Yield each scheme.json row as an ordered tuple of (pattern, is_start) segments.

    Most rows carry a single segment: either `[0, tup]` (a line-start segment
    with no partner) or `[tup]` (a line-end segment with no partner -- the
    second segment of an ordinary 2-segment cento line, stored as its own row
    since `table.append(scheme)` never merges it with anything).

    A row carries TWO segments only when a `type=` XML continuation merges
    the tail segment of one cento line with the (continued) head segment of
    the next -- these are the "consecutive lines" rows, identifiable by
    having a `0` marker somewhere other than as the row's sole leading item:
    `[tupA, 0, tupB]` (end + start) or `[0, tupA, 0, tupB]` (start + start).
    In the current scheme.json there are 18 rows of the first shape and 8 of
    the second (26 total, out of 188 rows) -- verified directly against the
    data; no row ever carries more than two segments.
    """
    for row in table:
        prev = None
        segs: List[Tuple[Tuple[int, ...], bool]] = []
        for item in row:
            if isinstance(item, list):
                segs.append((tuple(item), prev == 0))
            prev = item
        yield tuple(segs)


def render_row(segs: RowShape) -> str:
    """Reconstruct a row's scheme.json rendering (with 0 markers), for display."""
    parts = []
    for pattern, is_start in segs:
        if is_start:
            parts.append("0")
        parts.append("(" + " ".join(map(str, pattern)) + ")")
    return " ".join(parts)


def render_row_key(segs: RowShape) -> str:
    """JSON key for a full multi-segment row, reconstructed exactly as it
    appears in scheme.json (0 markers included) -- e.g. "[[..], 0, [..]]".
    """
    parts: List[object] = []
    for pattern, is_start in segs:
        if is_start:
            parts.append(0)
        parts.append(list(pattern))
    return json.dumps(parts)

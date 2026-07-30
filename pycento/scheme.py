"""Shared parsing of scheme.json's "table" (produced by step-01-Build-Stats.py).

Each row is a flat mix of the int 0 (cento-line-start marker) and morae
tuples (one per segment, elisions already excluded). See iter_scheme_patterns()
for the exact meaning of the 0 marker and how a segment's position (start/end
of a cento line) determines whether it must come from the START or the END of
a Virgil verse.
"""

import json
from dataclasses import dataclass
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


def line_segment_totals(line_segs: RowShape) -> Tuple[int, ...]:
    """The morae total of each segment in one accumulated output line
    (as built by walking iter_scheme_rows()'s is_start-driven line
    accumulation -- see step-04/step-05/step-03).

    Only the line's actual FINAL segment (always the last one in
    `line_segs`, whether or not it is itself an `is_start` segment) ends the
    whole hexameter, so only its last mora gets the anceps-normalization
    (forced to 2 regardless of its stored length -- the "line-final anceps
    convention", see pycento/serialize.py's `X` coding). Every other
    segment's last syllable is a genuine mid-verse syllable and must use its
    real stored value -- normalizing it too silently corrupts the total
    (e.g. a real (16, 8) split reads back as a nonexistent (17, 8) if the
    start segment's last mora, actually short, gets force-bumped to 2).
    """
    totals = []
    last = len(line_segs) - 1
    for i, (pattern, _is_start) in enumerate(line_segs):
        if not pattern:
            totals.append(0)
        elif i == last:
            totals.append(sum(pattern[:-1]) + 2)
        else:
            totals.append(sum(pattern))
    return tuple(totals)


@dataclass(frozen=True)
class LineSpec:
    """One real cento line, reconstructed from scheme.json's rows -- the
    same is_start-driven accumulation iter_scheme_rows' shapes already
    imply, but flattened across row boundaries into actual per-line units
    (see build_line_specs)."""
    segs: RowShape
    continues_previous: bool


def build_line_specs(rows: Iterator[RowShape]) -> List[LineSpec]:
    """Partition scheme.json's rows into real cento lines, marking each line
    whose first segment is a genuine `type="sq"` continuation of the
    immediately preceding line's LAST segment (`continues_previous=True`).

    A continuation is bundled into a single 2-segment ROW (see
    iter_scheme_rows) in exactly two shapes, and both reduce to the same
    rule -- the row's second element always starts a new line that
    continues whatever the row's first element just closed:
      - [tupA, 0, tupB]    : tupA (is_start=False) closes whatever line was
                              already open (from an earlier row); tupB
                              (is_start=True) opens the continuing line.
      - [0, tupA, 0, tupB] : tupA (is_start=True) first closes out and
                              replaces whatever was open with its own
                              (non-continuing) single-segment line; tupB
                              then opens a new line continuing THAT one.

    Verified directly against data/gold/cento.xml's own `continued` flags
    (via pycento.data.parse_cento): matches all 131 lines and all 26
    continuations exactly.
    """
    specs: List[LineSpec] = []
    current: List[Tuple[Tuple[int, ...], bool]] = []
    continues_previous = False

    def flush():
        nonlocal current, continues_previous
        if current:
            specs.append(LineSpec(segs=tuple(current), continues_previous=continues_previous))
        current = []
        continues_previous = False

    for row_segs in rows:
        if len(row_segs) == 2:
            (pattern_a, is_start_a), (pattern_b, is_start_b) = row_segs
            if is_start_a and current:
                flush()
            current.append((pattern_a, is_start_a))
            flush()
            continues_previous = True
            current.append((pattern_b, is_start_b))
        else:
            for pattern, is_start in row_segs:
                if is_start and current:
                    flush()
                current.append((pattern, is_start))
    flush()
    return specs


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

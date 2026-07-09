"""Build a concordance from scheme.json's segment patterns to matching Virgil lines.

scheme.json (produced by step-01) records, for every segment actually used in
the gold-aligned Cento Nuptialis (data/gold/cento.xml), the sequence of morae
(syllable weights, elisions dropped) that segment consists of. Its "table" is
a list of rows; each row is a flat mix of the int 0 and morae-tuples (JSON
lists), e.g. [0, [2, 1, 1, 2, ...]]. See iter_scheme_patterns() below for the
exact meaning of the 0 marker and how a segment's position (start/end of a
cento line) determines whether it must come from the START or the END of a
Virgil verse.

For every DISTINCT (pattern, start_or_end) pair that occurs anywhere in
scheme.json, this script searches the full Virgil corpus
(data/gold/metric/urn:cts:latinLit:phi0690.phi00?.xml -- Aeneid, Eclogues,
Georgics) for every verse where that exact morae sequence occurs anchored to
the verse's own start or end, cut at a real word boundary (never mid-word).
This replaces the old approach of splitting every Virgil hexameter at one
fixed, heuristic caesura point (~10 morae) regardless of where Ausonius
actually cut his source verses.

Output structure (data/segment_table.json):
    {
      "<json-encoded scheme.json row-slice, e.g. '[0, [2, 1, 1, 2]]'>": [
        {
          "id": "<source line urn>",
          "filepath": "<relative path to the Virgil source file>",
          "kind": "H1" | "H2" | "AB",   # start-partial / end-partial / whole verse
          "text": "<space-joined word forms of the matched span>",
          "words": [
            {"text": "...", "syllables": [{"text": "...", "length": "long"|"short"|"anceps"|"end"|"elided"}, ...]},
            ...
          ]
        },
        ...
      ],
      ...
    }

The key is deliberately the JSON serialization of exactly the row-slice this
pattern corresponds to in scheme.json ([0, pattern] for a start match,
[pattern] for an end match), so a consumer can take a slice straight out of
scheme.json's table and use it as a lookup key with no reformatting.

Some scheme.json rows carry TWO segments -- a `type=` XML continuation
merging the tail of one cento line with the (continued) start of the next
(see iter_scheme_rows()). Reproducing one of these faithfully needs more than
each segment matched independently: the `type=` attribute means segment B's
citation sequentially follows segment A's, so a real replacement needs the
two matched Virgil verses to themselves be ADJACENT in the same work (see
find_consecutive_pairs()). For these rows, segment_table.json gets an
EXTRA entry keyed by the full row (again reconstructed exactly as it appears
in scheme.json, e.g. "[[..], 0, [..]]"), whose value is a list of
[found_object_a, found_object_b] pairs verified to come from consecutive
verses -- on top of (not instead of) each segment's own independent entry.

Elided syllables are kept in "words"/"syllables" (so text and full scansion
stay recoverable) but are excluded from the morae sequence used for matching,
mirroring step-01's "not counting elision" rule.
"""

import csv
import json
import os.path as op
import sys
from collections import Counter
from typing import Dict, List, Tuple

from pycento.data import Word
from pycento.scheme import RowShape, iter_scheme_patterns, iter_scheme_rows, render_row, render_row_key
from pycento.virgil_index import IndexedLine, load_virgil_index, to_found_object

_ROOT = op.dirname(op.abspath(__file__))


# ---------------------------------------------------------------------------
# scheme.json row/pattern parsing moved to pycento/scheme.py (shared with
# step-04, which also needs to walk scheme.json's rows).
# ---------------------------------------------------------------------------

def consecutive_line_stats(row_counts: Counter, table: Dict[str, List[dict]]) -> List[dict]:
    """Stats for the multi-segment ("consecutive lines") rows only, ranked by
    how often that exact combination of segments occurs in the real Cento.

    `n_virgil_matches` is each segment matched independently, for context
    only. `n_pairs` is the count that actually matters: how many of those
    independent matches survive find_consecutive_pairs()'s "B's verse must
    immediately follow A's verse in the same Virgil work" constraint -- i.e.
    how many genuinely faithful replacements exist for this row.
    """
    rows = []
    for segs, occurrences in row_counts.items():
        if len(segs) < 2:
            continue
        match_counts = []
        for pattern, is_start in segs:
            key = json.dumps([0, list(pattern)] if is_start else [list(pattern)])
            match_counts.append(len(table.get(key, [])))
        row_key = render_row_key(segs)
        rows.append({
            "occurrences_in_cento": occurrences,
            "n_segments": len(segs),
            "n_virgil_matches": match_counts,
            "n_pairs": len(table.get(row_key, [])),
            "row": render_row(segs),
        })
    rows.sort(key=lambda r: (-r["occurrences_in_cento"], -r["n_pairs"]))
    return rows


def print_consecutive_line_stats(rows: List[dict]) -> None:
    print("\nConsecutive-line (continuation) rows -- scheme.json rows with an "
          "embedded 0, i.e. the tail of one cento line merged with the "
          "(continued) start of the next. #indep is each segment matched on "
          "its own (context only); #pairs is how many of those combinations "
          "actually come from two consecutive Virgil verses, which is what a "
          "faithful reconstruction of this row requires:")
    print(f"  {'occ.':>4}  {'#indep':<16}  {'#pairs':>6}  row")
    for r in rows:
        indep = "/".join(str(n) for n in r["n_virgil_matches"])
        print(f"  {r['occurrences_in_cento']:>4}  {indep:<16}  {r['n_pairs']:>6}  {r['row']}")


# ---------------------------------------------------------------------------
# Matching patterns against the Virgil index
# ---------------------------------------------------------------------------

def _match_lines(
    pattern: Tuple[int, ...], is_start: bool, index: List[IndexedLine],
) -> List[Tuple[IndexedLine, List[Word]]]:
    """Find every Virgil verse where `pattern` occurs anchored to its start or
    end, returning the raw (line, matched_words) pairs.

    The cut point must land on a real word boundary (never mid-word), which
    is what `boundary_word_count` enforces: we only accept a match if the
    morae-position at the pattern's inner edge is a key of that dict.
    """
    n = len(pattern)
    out: List[Tuple[IndexedLine, List[Word]]] = []
    for vl in index:
        if len(vl.morae) < n:
            continue
        if is_start:
            if tuple(vl.morae[:n]) != pattern:
                continue
            boundary = n
        else:
            if tuple(vl.morae[-n:]) != pattern:
                continue
            boundary = len(vl.morae) - n

        word_count = vl.boundary_word_count.get(boundary)
        if word_count is None:
            continue  # the pattern's edge falls inside a word -- not a valid cut

        words = vl.words[:word_count] if is_start else vl.words[word_count:]
        out.append((vl, words))
    return out


def find_matches(pattern: Tuple[int, ...], is_start: bool, index: List[IndexedLine]) -> List[dict]:
    """Find every Virgil verse where `pattern` occurs anchored to its start or end."""
    return [to_found_object(vl, words, is_start) for vl, words in _match_lines(pattern, is_start, index)]


def find_consecutive_pairs(
    seg_a: Tuple[Tuple[int, ...], bool],
    seg_b: Tuple[Tuple[int, ...], bool],
    index: List[IndexedLine],
) -> List[Tuple[dict, dict]]:
    """Valid replacements for a "consecutive lines" row: segment A and segment
    B independently matching somewhere in Virgil is NOT enough. The `type=`
    attribute in cento.xml means B's citation sequentially follows A's
    citation -- i.e. this row only faithfully reproduces the original
    construction if A and B come from two ADJACENT verses of the SAME Virgil
    work (raw_index differs by exactly 1 in the same file), not just any
    combination of an A-shaped verse and a B-shaped verse from anywhere in
    the corpus.
    """
    pattern_a, is_start_a = seg_a
    pattern_b, is_start_b = seg_b

    # Index B's matches by (file, position) so each A-match does a single
    # dict lookup for "the verse right after mine" instead of a nested scan.
    b_by_position: Dict[Tuple[str, int], List[Tuple[IndexedLine, List[Word]]]] = {}
    for vl, words in _match_lines(pattern_b, is_start_b, index):
        b_by_position.setdefault((vl.filepath, vl.raw_index), []).append((vl, words))

    pairs: List[Tuple[dict, dict]] = []
    for vl_a, words_a in _match_lines(pattern_a, is_start_a, index):
        for vl_b, words_b in b_by_position.get((vl_a.filepath, vl_a.raw_index + 1), []):
            pairs.append((
                to_found_object(vl_a, words_a, is_start_a),
                to_found_object(vl_b, words_b, is_start_b),
            ))
    return pairs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_table() -> Tuple[Dict[str, List[dict]], Counter, Counter]:
    scheme_path = op.join(_ROOT, "scheme.json")
    with open(scheme_path, encoding="utf-8") as fh:
        scheme_table = json.load(fh)["table"]

    print("Indexing Virgil corpus...")
    index = load_virgil_index(annotated=True)
    print(f"  {len(index)} well-formed hexameters")

    # How many times each (pattern, is_start) actually occurs in the real
    # Cento -- i.e. how common this exact metrical fragment is in Ausonius's
    # own composition. This is independent of how many Virgil candidates back
    # it (a rare fragment can still have thousands of metrical look-alikes).
    pattern_counts = Counter(iter_scheme_patterns(scheme_table))
    print(f"  {len(pattern_counts)} distinct (pattern, start/end) pairs from scheme.json "
          f"({sum(pattern_counts.values())} total occurrences)")

    # How many times each full ROW shape occurs -- this is what surfaces the
    # "consecutive lines" (multi-segment, continuation) rows as their own
    # linked entries instead of two disconnected patterns.
    row_counts = Counter(iter_scheme_rows(scheme_table))
    n_multi = sum(c for segs, c in row_counts.items() if len(segs) > 1)
    print(f"  {len(row_counts)} distinct rows, {n_multi} of them multi-segment "
          f"(consecutive-line) rows")

    table: Dict[str, List[dict]] = {}
    unmatched: List[str] = []
    for pattern, is_start in sorted(pattern_counts):
        key = json.dumps([0, list(pattern)] if is_start else [list(pattern)])
        matches = find_matches(pattern, is_start, index)
        if matches:
            table[key] = matches
        else:
            unmatched.append(key)

    total_matches = sum(len(v) for v in table.values())
    print(f"  {total_matches} total matches across {len(table)} patterns")

    if unmatched:
        print(f"  WARNING: {len(unmatched)} pattern(s) have no match anywhere in Virgil "
              f"(possible scansion/alignment mismatch between cento.xml and the metric "
              f"source files):", file=sys.stderr)
        for key in unmatched:
            print(f"    {key}", file=sys.stderr)

    # For multi-segment ("consecutive lines") rows, also add an entry keyed by
    # the FULL row (0 markers included, e.g. "[[..], 0, [..]]"), whose value
    # is the list of VERIFIED PAIRS: combinations where segment B's Virgil
    # verse genuinely immediately follows segment A's, per the `type=`
    # continuation convention -- not just any independent match of each side.
    # A consumer that only used the per-segment entries above could pair up
    # two unrelated verses and silently break the continuation; this row-keyed
    # entry is what a faithful reconstruction of the original needs instead.
    multi_segment_rows = [segs for segs in row_counts if len(segs) > 1]
    zero_pair_rows: List[str] = []
    total_row_pairs = 0
    for segs in multi_segment_rows:
        seg_a, seg_b = segs
        pairs = find_consecutive_pairs(seg_a, seg_b, index)
        row_key = render_row_key(segs)
        if pairs:
            table[row_key] = [[obj_a, obj_b] for obj_a, obj_b in pairs]
            total_row_pairs += len(pairs)
        else:
            zero_pair_rows.append(row_key)

    print(f"  {total_row_pairs} total consecutive-verse pairs across "
          f"{len(multi_segment_rows) - len(zero_pair_rows)} consecutive-line rows")

    if zero_pair_rows:
        print(f"  WARNING: {len(zero_pair_rows)} consecutive-line row(s) have no valid "
              f"adjacent-verse pair anywhere in Virgil:", file=sys.stderr)
        for key in zero_pair_rows:
            print(f"    {key}", file=sys.stderr)

    return table, pattern_counts, row_counts


def pattern_stats(pattern_counts: Counter, table: Dict[str, List[dict]]) -> List[dict]:
    """Per-pattern stats, ranked by how often the pattern is used in the real
    Cento (most frequent first), alongside how many candidate Virgil matches
    back it up.
    """
    rows = []
    for (pattern, is_start), occurrences in pattern_counts.items():
        key = json.dumps([0, list(pattern)] if is_start else [list(pattern)])
        rows.append({
            "occurrences_in_cento": occurrences,
            "n_virgil_matches": len(table.get(key, [])),
            "position": "start" if is_start else "end",
            "morae": " ".join(map(str, pattern)),
            "key": key,
        })
    rows.sort(key=lambda r: (-r["occurrences_in_cento"], -r["n_virgil_matches"]))
    return rows


def print_pattern_stats(rows: List[dict]) -> None:
    print("\nPattern frequency in the real Cento (most -> least common):")
    print(f"  {'occ.':>4}  {'#matches':>8}  {'pos':<5}  morae")
    for r in rows:
        print(f"  {r['occurrences_in_cento']:>4}  {r['n_virgil_matches']:>8}  "
              f"{r['position']:<5}  {r['morae']}")


if __name__ == "__main__":
    table, pattern_counts, row_counts = build_table()

    out_path = op.join(_ROOT, "data", "segment_table.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"\nWrote {out_path}")

    rows = pattern_stats(pattern_counts, table)
    print_pattern_stats(rows)

    stats_path = op.join(_ROOT, "pattern_stats.csv")
    with open(stats_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "occurrences_in_cento", "n_virgil_matches", "position", "morae", "key",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {stats_path}")

    consecutive_rows = consecutive_line_stats(row_counts, table)
    print_consecutive_line_stats(consecutive_rows)

    consecutive_path = op.join(_ROOT, "consecutive_line_stats.csv")
    with open(consecutive_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "occurrences_in_cento", "n_segments", "n_virgil_matches", "n_pairs", "row",
        ])
        writer.writeheader()
        for r in consecutive_rows:
            writer.writerow({**r, "n_virgil_matches": "/".join(map(str, r["n_virgil_matches"]))})
    print(f"\nWrote {consecutive_path}")

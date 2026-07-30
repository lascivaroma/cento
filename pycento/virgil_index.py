"""Shared Virgil-corpus indexing, used by step-02 and step-02bis.

Parses every Virgil work (Aeneid, Eclogues, Georgics) from
data/gold/metric/urn:cts:latinLit:phi0690.phi00?.xml and pre-computes, per
well-formed hexameter, its non-elided morae sequence and a word-boundary map
(morae-position -> whole words consumed up to there). That map is what lets a
consumer restrict any prefix/suffix match to a real word boundary (never
mid-word) with a single dict lookup, whether the match is driven by an exact
syllable sequence (step-02) or just a target morae total (step-02bis).
"""

import os.path as op
from dataclasses import dataclass
from typing import Dict, List, Tuple

from pycento.data import Line, Word, parse
from pycento.segments import is_hexameter

_ROOT = op.join(op.dirname(op.abspath(__file__)), "..")

# Same mapping as step-01's segment_morae, so patterns computed on the Cento
# side and on the Virgil side are directly comparable.
_MORA = {"long": 2, "short": 1, "anceps": 2, "elided": 0, "end": 2}

_VIRGIL_FILES = {
    "phi0690.phi003": "Virgil (Aeneid)",
    "phi0690.phi001": "Virgil (Eclogues)",
    "phi0690.phi002": "Virgil (Georgics)",
}


@dataclass
class IndexedLine:
    """A Virgil hexameter, pre-computed for fast prefix/suffix pattern matching."""
    ref: str
    filepath: str
    raw_index: int                      # position in the file's own line sequence
    words: List[Word]
    morae: List[int]                    # non-elided syllable morae, in order
    boundary_word_count: Dict[int, int]        # syllable INDEX -> whole words consumed up to there
    boundary_word_count_by_total: Dict[int, int]  # morae SUM -> whole words consumed up to there


def _index_line(line: Line, filepath: str, raw_index: int) -> IndexedLine:
    morae: List[int] = []
    boundary_word_count: Dict[int, int] = {0: 0}
    boundary_word_count_by_total: Dict[int, int] = {0: 0}
    running_total = 0
    for i, word in enumerate(line.words):
        for syll in word.syllables:
            if syll.length == "elided":
                continue
            m = _MORA.get(syll.length, 0)
            morae.append(m)
            running_total += m
        # Record the boundary AFTER this word, in both units. Exact-sequence
        # matching (step-02) needs "how many syllables in"; total-morae
        # matching (step-02bis) needs "how many morae in" -- these are NOT
        # the same number (a syllable is worth 1 or 2 morae), so they need
        # separate maps. Either way, a later word's entry simply overwrites
        # an earlier one landing on the same key, which is fine: it still
        # marks a legitimate word boundary there.
        boundary_word_count[len(morae)] = i + 1
        boundary_word_count_by_total[running_total] = i + 1
    return IndexedLine(
        ref=line.ref, filepath=filepath, raw_index=raw_index, words=line.words,
        morae=morae, boundary_word_count=boundary_word_count,
        boundary_word_count_by_total=boundary_word_count_by_total,
    )


def to_found_object(vl: IndexedLine, words: List[Word], is_start: bool) -> dict:
    """A JSON-friendly view of a matched span: which verse, which words, and
    whether the match is a whole verse (AB), a start-anchored partial (H1),
    or an end-anchored partial (H2).
    """
    kind = "AB" if len(words) == len(vl.words) else ("H1" if is_start else "H2")
    return {
        "id": vl.ref,
        "filepath": vl.filepath,
        "kind": kind,
        "text": " ".join(w.text for w in words if w.text),
        # Space-joined, one token per word (not filtered like "text" above),
        # so step-04/step-05 can positionally .split() these against
        # "text".split() -- filtering here would shift a dropped word's
        # lemma/pos onto the wrong following word.
        "lemma": " ".join(w.lemma or "" for w in words),
        "pos": " ".join(w.pos or "" for w in words),
        "msd": " ".join(w.morph or "" for w in words),
        "words": [
            {
                "text": w.text,
                "lemma": w.lemma,
                "pos": w.pos,
                "msd": w.morph,
                "syllables": [{"text": s.text, "length": s.length} for s in w.syllables],
            }
            for w in words
        ],
    }


def match_by_total(total: int, is_start: bool, index: List[IndexedLine]) -> List[dict]:
    """Find every Virgil verse with a word-boundary-respecting prefix (if
    is_start) or suffix (otherwise) whose morae SUM to exactly `total` --
    regardless of the specific long/short arrangement within that budget.

    Same word-boundary system as the exact-sequence matching in step-02, just
    keyed by a morae TOTAL instead of a syllable count -- that's
    `boundary_word_count_by_total`, not `boundary_word_count` (which is keyed
    by syllable index and would silently reject almost every total, since a
    24-morae hexameter only ever has ~13-17 syllables). A start match needs
    `total` itself to be a valid morae boundary; an end match needs the
    verse's remaining length (24 - total, since every indexed line is a
    well-formed 24-morae hexameter) to be one.
    """
    found: List[dict] = []
    for vl in index:
        boundary = total if is_start else 24 - total
        word_count = vl.boundary_word_count_by_total.get(boundary)
        if word_count is None:
            continue
        words = vl.words[:word_count] if is_start else vl.words[word_count:]
        found.append(to_found_object(vl, words, is_start))
    return found


def match_consecutive_pairs_by_total(
    a_total: int, b_total: int, index: List[IndexedLine],
) -> List[Tuple[dict, dict]]:
    """Loose (total-morae) analogue of step-02's find_consecutive_pairs: every
    pair of Virgil verses that are genuinely ADJACENT (same file, raw_index
    differs by exactly 1) where a word-boundary-respecting PREFIX of the
    first verse sums to a_total and a word-boundary-respecting SUFFIX of the
    second sums to b_total -- regardless of the specific long/short
    arrangement within either budget.

    For scheme.json's `type="sq"` continuation slots (the tail of one cento
    line glued to the continued head of the next): even under loose,
    total-morae-only matching, these two segments must still come from two
    sequential Virgil verses, not just any two verses whose totals happen to
    fit -- that's the whole point of `type="sq"` in the gold cento.
    """
    by_position: Dict[Tuple[str, int], IndexedLine] = {
        (vl.filepath, vl.raw_index): vl for vl in index
    }
    pairs: List[Tuple[dict, dict]] = []
    for vl_a in index:
        word_count_a = vl_a.boundary_word_count_by_total.get(a_total)
        if word_count_a is None:
            continue
        vl_b = by_position.get((vl_a.filepath, vl_a.raw_index + 1))
        if vl_b is None:
            continue
        word_count_b = vl_b.boundary_word_count_by_total.get(24 - b_total)
        if word_count_b is None:
            continue
        words_a = vl_a.words[:word_count_a]
        words_b = vl_b.words[word_count_b:]
        pairs.append((
            to_found_object(vl_a, words_a, True),
            to_found_object(vl_b, words_b, False),
        ))
    return pairs


def load_virgil_index(annotated: bool = False) -> List[IndexedLine]:
    """Parse every Virgil work and index the well-formed hexameters.

    Lines with incomplete/missing syllable data (is_hexameter() false, i.e.
    total morae != 24) are dropped -- they can't supply a metrically valid
    fragment anyway. `raw_index` is assigned from the file's full,
    UNfiltered line sequence (enumerate() runs over parse(path) before the
    is_hexameter check), so "raw_index + 1" reliably means "the very next
    verse in Virgil's own text", not just "the next verse that happened to
    survive filtering" -- needed for detecting genuinely consecutive verses
    (see step-02's find_consecutive_pairs()).

    :param annotated: read the LASLA-tagged `-annotated.xml` siblings
        (produced by preprocess/annotate_virgil.py) instead of the bare
        syllable-only files, so Word.lemma/pos/morph are populated. Defaults
        to False so existing callers (e.g. this module's own __main__ demo)
        are unaffected until they opt in.
    """
    index: List[IndexedLine] = []
    for filename in sorted(_VIRGIL_FILES):
        suffix = "-annotated" if annotated else ""
        path = op.join(_ROOT, "data", "gold", "metric", f"urn:cts:latinLit:{filename}{suffix}.xml")
        rel_path = op.relpath(path, _ROOT)
        for raw_index, line in enumerate(parse(path)):
            if not is_hexameter(line):
                continue
            index.append(_index_line(line, rel_path, raw_index))
    return index

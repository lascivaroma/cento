"""Compact Pedecerto-style export: the inverse of
data/ausonius-raw/0-converter.py's parse_sy()/MET_MAP decoding.

Given the project's internal Line/Segment/Word/Syllable model, reconstructs
`<word sy="1A1b1c" mf="SY" pos="..." lemma="...">form</word>` elements, with
one `<line meter="H" pattern="DDSDDS">` per Line and a `<milestone>` marker
at each Segment boundary (for cento data that has segments; plain
Virgil/Ausonius-hexameter lines have none).

Lossy-by-design choices (documented, not silently assumed):
  - `long` -> "A", `anceps`/`end` -> "X" (both represent the metrically
    flexible final position; the source scheme has no separate code for
    'end', it is a validation-time concept in this codebase).
  - `short` -> "b" for the first short mora in a foot, "c" for the second
    (matches the dactyl's two short syllables); the b/c count resets per
    foot, not per word, since a foot's two shorts can be split across a
    word boundary (e.g. "nemorosa per" -> foot 4 = "...4A4b" + "4c").
  - The source format's `mf` distinguishes "SY" (synaloepha) from "PE"
    (prodelision); the internal model conflates both as
    Syllable.length == "elided", so this writer always emits mf="SY".
  - No `msd=` attribute is emitted (compact format is form/sy/mf/pos/lemma).
"""

import itertools
from typing import List, Optional, Tuple

import lxml.etree as et

from pycento.data import Line, Word, Syllable
from pycento.segments import assign_feet, scan_pattern


def _syllable_codes(syllables: List[Syllable], foot_numbers: List[Optional[int]]) -> List[Optional[str]]:
    """Per non-elided syllable with an assigned foot, the single-letter code
    (A/T/X/b/c); None for elided syllables or syllables past the last
    complete foot.

    A/T distinguish a foot's first vs. second long-mora syllable (A = first,
    T = second -- a spondee's two longs are coded A,T; a dactyl's single
    long is always A since it's the only one). This is NOT "long by nature
    vs. by position" (that theory doesn't survive contact with the raw data,
    e.g. AVSON-cent.xml codes the diphthong in "lae-tas-que" as T, and codes
    the two geminate-closed syllables of "Ac-ces-sit" as A then T
    respectively) -- it is purely foot-relative position, exactly mirroring
    how a dactyl's two shorts are coded b (first) then c (second). X marks
    an explicitly anceps/end-typed syllable. Short-mora b/c and long-mora A/T
    numbering both reset per foot number.

    The line's last non-elided syllable is always coded "X", regardless of
    its stored length -- matching the raw Pedecerto convention (confirmed
    against data/ausonius-raw/*.xml, e.g. "addi" -> sy="6A6X": the line-final
    syllable is metrically anceps no matter what length it's annotated with)
    and the same rule check_metrics.py/group_feet() already apply for
    scansion validation.
    """
    codes: List[Optional[str]] = [None] * len(syllables)
    short_count_by_foot: dict = {}
    long_count_by_foot: dict = {}
    for i, (syll, foot) in enumerate(zip(syllables, foot_numbers)):
        if foot is None or syll.length == "elided":
            continue
        if syll.length == "short":
            n = short_count_by_foot.get(foot, 0)
            codes[i] = "c" if n else "b"
            short_count_by_foot[foot] = n + 1
        elif syll.length in ("anceps", "end"):
            codes[i] = "X"
            long_count_by_foot[foot] = long_count_by_foot.get(foot, 0) + 1
        else:  # long
            n = long_count_by_foot.get(foot, 0)
            codes[i] = "T" if n else "A"
            long_count_by_foot[foot] = n + 1

    last_idx = next(
        (i for i in range(len(syllables) - 1, -1, -1) if foot_numbers[i] is not None),
        None,
    )
    if last_idx is not None:
        codes[last_idx] = "X"

    return codes


def word_to_sy(
    syllables: List[Syllable],
    foot_numbers: List[Optional[int]],
    codes: List[Optional[str]],
) -> Tuple[str, Optional[str]]:
    """Return (sy_string, mf_value_or_None) for one Word's syllables, given
    the foot numbers/codes already computed for the whole line (sliced to
    this word's syllable range)."""
    parts = []
    mf = None
    for syll, foot, code in zip(syllables, foot_numbers, codes):
        if syll.length == "elided":
            mf = "SY"
            continue
        if foot is not None and code is not None:
            parts.append(f"{foot}{code}")
    return "".join(parts), mf


def line_to_compact_xml(line: Line, parent: et.Element, milestone_counter: "itertools.count") -> None:
    """Append one <line> element (with <milestone>/<word> children) to
    `parent` for one internal Line."""
    all_syllables = [s for w in line.words for s in w.syllables]
    foot_numbers = assign_feet(all_syllables)
    codes = _syllable_codes(all_syllables, foot_numbers)
    pattern = scan_pattern(line)

    line_elem = et.SubElement(parent, "line", attrib={
        "n": line.ref or str(line.idx),
        "meter": "H",
        "pattern": pattern,
    })

    offset = 0

    def emit_word(w: Word) -> None:
        nonlocal offset
        n = len(w.syllables)
        w_foot = foot_numbers[offset: offset + n]
        w_codes = codes[offset: offset + n]
        offset += n
        if n == 0 or not w.text:
            return  # zero-syllable placeholder (duplicate enclitic annotation)
        sy, mf = word_to_sy(w.syllables, w_foot, w_codes)
        attrib = {"sy": sy}
        if mf:
            attrib["mf"] = mf
        if w.pos:
            attrib["pos"] = w.pos
        if w.lemma:
            attrib["lemma"] = w.lemma
        word_elem = et.SubElement(line_elem, "word", attrib=attrib)
        word_elem.text = w.text

    if line.segments:
        for seg in line.segments:
            n = next(milestone_counter)
            ms_attrib = {"unit": "segment", "n": str(n), "source": seg.source}
            if seg.continued:
                ms_attrib["continued"] = "true"
            milestone = et.SubElement(line_elem, "milestone", attrib=ms_attrib)
            milestone.text = f"segment ID {n}"
            for w in seg.words:
                emit_word(w)
    else:
        for w in line.words:
            emit_word(w)


def lines_to_compact_tree(lines: List[Line]) -> et.Element:
    """Top-level entry point: build a <text> root with one <line> per input
    Line, sharing one milestone counter across all of them."""
    root = et.Element("text")
    counter = itertools.count(1)
    for line in lines:
        line_to_compact_xml(line, root, counter)
    return root

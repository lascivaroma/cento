from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from pycento.data import Line, Segment, Word, Syllable

_MORA = {"long": 2, "short": 1, "anceps": 2, "elided": 0, "end": 2}
_LONG = {"long", "anceps", "end"}
_HEXAMETER_MORAE = 24
_CAESURA_MORAE = 10  # penthemimeral: feet 1-2 (8 morae) + arsis of foot 3 (2 morae)
_FOOT_MORAE = 4
_N_FEET = 6
_FOOT_PATTERNS = {(2, 1, 1): "D", (2, 2): "S"}


@dataclass
class Foot:
    number: int                # 1-based (1..6 for a hexameter)
    syllables: List[Syllable]  # non-elided syllables assigned to this foot
    pattern: str                # "D", "S", or "?" if it matches neither


def group_feet(syllables: List[Syllable], foot_morae: int = _FOOT_MORAE, n_feet: int = _N_FEET) -> List[Foot]:
    """Walk syllables into feet of `foot_morae` morae each, skipping elided
    syllables (mora 0) exactly like check_metrics.check_line() does, including
    forcing the last non-elided syllable to 'end' (anceps). Operates on a
    local copy — never mutates the caller's Syllable objects. Returns only
    fully-completed feet (an incomplete trailing foot, e.g. a malformed line,
    is dropped rather than partially reported)."""
    syll_queue = list(syllables)

    last_idx = next(
        (i for i in range(len(syll_queue) - 1, -1, -1)
         if _MORA.get(syll_queue[i].length, 0) > 0),
        None
    )
    if last_idx is not None:
        syll_queue[last_idx] = Syllable(text=syll_queue[last_idx].text, length="end")

    feet: List[Foot] = []
    pos = 0
    for foot_number in range(1, n_feet + 1):
        foot_morae_count = 0
        foot_syllables: List[Syllable] = []
        incomplete = False

        while foot_morae_count < foot_morae:
            if pos >= len(syll_queue):
                incomplete = True
                break
            syll = syll_queue[pos]
            pos += 1
            m = _MORA.get(syll.length, 0)
            if m == 0:
                continue
            foot_syllables.append(syll)
            foot_morae_count += m

        if incomplete or not foot_syllables:
            break

        pattern = _FOOT_PATTERNS.get(tuple(_MORA.get(s.length, 0) for s in foot_syllables), "?")
        feet.append(Foot(number=foot_number, syllables=foot_syllables, pattern=pattern))

    return feet


def assign_feet(syllables: List[Syllable], foot_morae: int = _FOOT_MORAE, n_feet: int = _N_FEET) -> List[Optional[int]]:
    """Return the foot number (1-based) each syllable belongs to, in the same
    order/length as `syllables`. Elided syllables, and any syllables past the
    last complete foot, get None. Unlike group_feet(), this does not force the
    last syllable to 'end' — mora accounting for foot boundaries is identical
    whether a 2-mora syllable is typed long/anceps/end, so raw lengths are
    used directly. This is the basis for reconstructing per-syllable foot
    numbers for the compact sy= export format (see pycento/serialize.py)."""
    assignments: List[Optional[int]] = [None] * len(syllables)
    pos = 0
    for foot_number in range(1, n_feet + 1):
        foot_morae_count = 0
        foot_positions: List[int] = []
        while foot_morae_count < foot_morae:
            if pos >= len(syllables):
                return assignments
            m = _MORA.get(syllables[pos].length, 0)
            if m > 0:
                foot_positions.append(pos)
                foot_morae_count += m
            pos += 1
        for p in foot_positions:
            assignments[p] = foot_number
    return assignments


def scan_pattern(line: Line) -> str:
    """Return e.g. 'DDSDDS' — one 'D' (dactyl) or 'S' (spondee) per foot, in
    order; '?' for a foot whose mora pattern is neither. Safe to call on
    not-yet-validated lines (never raises)."""
    syllables = [s for w in line.words for s in w.syllables]
    feet = group_feet(syllables)
    return "".join(f.pattern for f in feet)


@dataclass
class CandidateSegment:
    kind: str        # H1, H2, AB, H2+H1, H2+AB, AB+H1, AB+AB
    refs: List[str]  # source line ref(s)
    words: List[Word]

    def __repr__(self):
        text = " ".join(w.text for w in self.words if w.text)
        return f"[{self.kind}] ({', '.join(self.refs)}) {text}"


def _word_morae(word: Word) -> int:
    return sum(_MORA.get(s.length, 0) for s in word.syllables)


def line_morae(line: Line) -> int:
    return sum(_word_morae(w) for w in line.words)


def is_hexameter(line: Line) -> bool:
    return line_morae(line) == _HEXAMETER_MORAE


def segment_morae(seg: Segment) -> Tuple[int, List[Tuple[int, ...]]]:
    """Total morae for a segment, plus its non-elided syllable-mora sequence
    (elisions dropped) as a single-element list wrapping one flat tuple --
    e.g. (24, [(2, 1, 1, 2, ...)]). Used by step-01-Build-Stats.py to build
    scheme.json's per-line "table" rows, and by line_structure()/
    cento_structure() below to compare a generated cento's shape against the
    source."""
    total = 0
    segs = [[]]
    for word in seg.words:
        for syll in word.syllables:
            total += _MORA.get(syll.length, 0)
            if syll.length == "elided":
                continue
            elif length := _MORA.get(syll.length, 0):
                segs[-1].append(length)
            else:
                continue
    return total, [tuple(seg) for seg in segs if seg]


def line_schema(seg_data: List[Tuple[int, bool]]) -> str:
    """e.g. [(14, False), (10, True)] -> '14+~10' (a '~' prefix marks a
    continued segment) -- the same schema string step-01 writes into
    segment_stats.csv's "schema" column."""
    parts = []
    for morae, continued in seg_data:
        parts.append(f"~{morae}" if continued else str(morae))
    return "+".join(parts)


def line_structure(line: Line) -> List[Tuple[int, bool]]:
    """Per-segment (total_morae, continued) for one line -- the structural
    signature used to compare a generated cento's shape against the source
    (same line count, same segment count per line, same morae target per
    segment, same continuation flags)."""
    return [(segment_morae(seg)[0], seg.continued) for seg in line.segments]


def cento_structure(lines: List[Line]) -> List[List[Tuple[int, bool]]]:
    """The full structural signature of a cento (gold or generated): one
    line_structure() per line. Two centos have "the same structure" iff
    cento_structure(lines_a) == cento_structure(lines_b)."""
    return [line_structure(line) for line in lines]


def split_at_caesura(line: Line) -> Optional[Tuple[List[Word], List[Word]]]:
    """Return (first_hemistich_words, second_hemistich_words) or None."""
    words = line.words
    if not words:
        return None

    # Strategy A: explicit <caesura/> marker stored as caesura_after on a word
    for i, w in enumerate(words):
        if w.caesura_after:
            h1, h2 = words[:i + 1], words[i + 1:]
            if h1 and h2:
                return h1, h2

    # Strategy B: mora-counting — split before the word that crosses 10 morae
    cumulative = 0
    for i, w in enumerate(words):
        word_m = _word_morae(w)
        if cumulative + word_m > _CAESURA_MORAE:
            # This word goes over the boundary; caesura is before it
            h1, h2 = words[:i], words[i:]
            if h1 and h2:
                return h1, h2
            break
        cumulative += word_m
        if cumulative == _CAESURA_MORAE:
            h1, h2 = words[:i + 1], words[i + 1:]
            if h1 and h2:
                return h1, h2
            break

    return None


def build_segments(lines: List[Line]) -> List[CandidateSegment]:
    """Generate all candidate cento segments from a list of parsed lines.

    Only hexameter lines are included. Multi-line segments (H2+H1, etc.) are
    only emitted for lines that are consecutive in the source (no index gap).
    """
    hex_lines = [l for l in lines if is_hexameter(l)]
    segments: List[CandidateSegment] = []

    splits = {l.idx: split_at_caesura(l) for l in hex_lines}

    for i, line in enumerate(hex_lines):
        ref = line.ref or str(line.idx)
        split = splits[line.idx]

        # Single-line segments
        if split:
            h1, h2 = split
            segments.append(CandidateSegment("H1", [ref], h1))
            segments.append(CandidateSegment("H2", [ref], h2))
        segments.append(CandidateSegment("AB", [ref], list(line.words)))

        # Multi-line segments with the next hexameter line
        if i + 1 >= len(hex_lines):
            continue
        next_line = hex_lines[i + 1]
        # Only combine lines that are actually adjacent in the source
        if next_line.idx != line.idx + 1:
            continue

        next_ref = next_line.ref or str(next_line.idx)
        next_split = splits[next_line.idx]

        if split and next_split:
            _, h2_cur = split
            h1_next, _ = next_split
            segments.append(CandidateSegment("H2+H1", [ref, next_ref], h2_cur + h1_next))

        if split:
            _, h2_cur = split
            segments.append(CandidateSegment("H2+AB", [ref, next_ref], h2_cur + list(next_line.words)))

        if next_split:
            h1_next, _ = next_split
            segments.append(CandidateSegment("AB+H1", [ref, next_ref], list(line.words) + h1_next))

        segments.append(CandidateSegment("AB+AB", [ref, next_ref], list(line.words) + list(next_line.words)))

    return segments


if __name__ == "__main__":
    import os.path as op
    from collections import Counter
    from pycento.data import parse

    _root = op.join(op.dirname(__file__), "..", "data")

    print("=== Aeneid (explicit caesura markers) ===")
    aen = parse(op.join(_root, "gold", "metric", "urn:cts:latinLit:phi0690.phi003.xml"))
    segs = build_segments(aen)
    print(Counter(s.kind for s in segs))
    # Spot-check Ae. 1.1
    for s in segs[:6]:
        print(s)

    print()
    print("=== Ausonius Epigrams (inferred caesura) ===")
    epig = parse(op.join(_root, "ausonius", "AVSON-epig.xml"))
    segs2 = build_segments(epig)
    print(Counter(s.kind for s in segs2))
    for s in segs2[:6]:
        print(s)

from dataclasses import dataclass
from typing import List, Optional, Tuple

from pycento.data import Line, Word

_MORA = {"long": 2, "short": 1, "anceps": 2, "elided": 0, "end": 2}
_HEXAMETER_MORAE = 24
_CAESURA_MORAE = 10  # penthemimeral: feet 1-2 (8 morae) + arsis of foot 3 (2 morae)


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
    epig = parse(op.join(_root, "ausonius-gold", "AVSON-epig.xml"))
    segs2 = build_segments(epig)
    print(Counter(s.kind for s in segs2))
    for s in segs2[:6]:
        print(s)

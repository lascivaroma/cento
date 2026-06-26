"""Check metrical validity of each hexameter line in the cento.

A hexameter has 6 feet (24 morae, 4 per foot). Each foot must be:
  - Dactyl:  long + short + short  (2 + 1 + 1)
  - Spondee: long + long           (2 + 2)

Rules:
  1. Foot must start with a long syllable (not short).
  2. Elided syllables are skipped metrically everywhere, except at the absolute
     start of a line (before any non-elided syllable) which is always flagged.
  3. Foot pattern must be dactyl (2+1+1) or spondee (2+2).
  4. The last non-elided syllable is always treated as anceps ("end", 2 morae).
  5. Any "end"-typed syllable appearing mid-line is flagged as a data error.
  6. Line total morae != 24 is flagged independently.

Lines with any violation get need_check="true" on their <l> element in
data/gold/cento.xml, which is written back in place.
"""

import os.path as op
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple

import lxml.etree as et

from pycento.data import parse_cento, Syllable

_ROOT = op.dirname(op.abspath(__file__))
_GOLD = op.join(_ROOT, "..", "data", "gold", "cento.xml")
_NS = "http://www.tei-c.org/ns/1.0"
_NSM = {"t": _NS}

_MORA = {"long": 2, "short": 1, "anceps": 2, "elided": 0, "end": 2}
_LONG = {"long", "anceps", "end"}
_FOOT_MORAE = 4
_N_FEET = 6


@dataclass
class Violation:
    line_idx: int
    foot: int
    mora_pos: int
    syllable: Syllable
    message: str


def check_line(line_idx: int, syllables: List[Syllable]) -> List[Violation]:
    violations: List[Violation] = []
    syll_queue = list(syllables)

    # Find index of last non-elided syllable
    last_idx = next(
        (i for i in range(len(syll_queue) - 1, -1, -1)
         if _MORA.get(syll_queue[i].length, 0) > 0),
        None
    )

    # Force last non-elided syllable to "end" (anceps)
    if last_idx is not None:
        syll_queue[last_idx] = Syllable(text=syll_queue[last_idx].text, length="end")

    # Flag any "end" syllable that is not the last non-elided syllable
    mora_pos = 0
    for i, syll in enumerate(syll_queue):
        m = _MORA.get(syll.length, 0)
        if syll.length == "end" and i != last_idx:
            violations.append(Violation(
                line_idx, 0, mora_pos, syll,
                f"mid-line 'end' syllable '{syll.text}' at mora {mora_pos}"
            ))
        mora_pos += m
    mora_pos = 0
    line_started = False  # True once we've seen the first non-elided syllable

    pos = 0  # index into syll_queue

    for foot in range(1, _N_FEET + 1):
        foot_morae = 0
        foot_syllables: List[Tuple[int, Syllable]] = []

        while foot_morae < _FOOT_MORAE:
            if pos >= len(syll_queue):
                return violations  # incomplete line, mora check handles this

            syll = syll_queue[pos]
            pos += 1
            m = _MORA.get(syll.length, 0)

            if m == 0:  # elided — always skip metrically
                if not line_started:
                    # Elided at absolute line start — always a problem
                    violations.append(Violation(
                        line_idx, foot, mora_pos, syll,
                        f"foot {foot}: elided syllable '{syll.text}' at line start"
                    ))
                continue

            line_started = True
            foot_syllables.append((mora_pos, syll))
            foot_morae += m
            mora_pos += m

        if not foot_syllables:
            continue

        # Rule 1: foot-initial syllable must be long
        first_pos, first_syll = foot_syllables[0]
        if first_syll.length not in _LONG:
            violations.append(Violation(
                line_idx, foot, first_pos, first_syll,
                f"foot {foot}: starts with short '{first_syll.text}' at mora {first_pos}"
            ))

        # Rule 2: foot pattern must be dactyl (2+1+1) or spondee (2+2)
        pattern = tuple(_MORA.get(s.length, 0) for _, s in foot_syllables)
        if pattern not in ((2, 1, 1), (2, 2)):
            violations.append(Violation(
                line_idx, foot, first_pos, first_syll,
                f"foot {foot}: unexpected pattern {pattern} "
                f"({[s.length for _, s in foot_syllables]})"
            ))

    return violations


def line_morae(syllables: List[Syllable]) -> int:
    return sum(_MORA.get(s.length, 0) for s in syllables)


def main():
    lines = parse_cento(_GOLD)

    violations_by_line: dict[int, List[Violation]] = defaultdict(list)
    bad_mora_lines: set[int] = set()

    for line in lines:
        syllables = [s for w in line.words for s in w.syllables]
        if not syllables:
            continue
        total = line_morae(syllables)
        if total != 24:
            bad_mora_lines.add(line.idx)
        vs = check_line(line.idx, syllables)
        if vs:
            violations_by_line[line.idx].extend(vs)

    flagged = set(violations_by_line.keys()) | bad_mora_lines

    # --- Annotate cento.xml ---
    tree = et.parse(_GOLD)
    for l_elem in tree.xpath("//t:l", namespaces=_NSM):
        n = l_elem.get("n")
        idx = int(n) if n and n.isdigit() else None
        if idx in flagged:
            l_elem.set("need_check", "true")
        elif "need_check" in l_elem.attrib:
            del l_elem.attrib["need_check"]

    tree.write(_GOLD, encoding="utf-8", xml_declaration=True, pretty_print=True)

    # --- Report ---
    total_v = sum(len(v) for v in violations_by_line.values())
    print(f"{total_v} violation(s) across {len(violations_by_line)} line(s); "
          f"{len(bad_mora_lines)} line(s) with wrong mora count; "
          f"{len(flagged)} line(s) marked need_check.\n")

    for line_idx in sorted(flagged):
        line = lines[line_idx - 1]
        text = " ".join(w.text for w in line.words if w.text and w.text.strip())
        reasons = []
        if line_idx in bad_mora_lines:
            syll = [s for w in line.words for s in w.syllables]
            reasons.append(f"total morae = {line_morae(syll)}")
        for v in violations_by_line.get(line_idx, []):
            reasons.append(v.message)
        print(f"  Line {line_idx}: {text}")
        for r in reasons:
            print(f"    {r}")

    if flagged:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Build a JSON segment table from all parsed source texts.

Ausonius source: data/ausonius-hexameter-annotated.xml (lemma/pos/msd included,
cento excluded). Virgil sources: data/gold/metric/urn:cts:latinLit:phi0690.phi00?.xml.

Output structure:
    {
      "<author>": {
        "<kind>": {          # H1, H2, AB, H2+H1, H2+AB, AB+H1, AB+AB
          "<form>": [        # metrical pattern, e.g. "2 2 1 1 2 2 2"
            {
              "id": "<source:lineref>",
              "filepath": "<relative path to source file>",
              "text": "<space-joined word forms>",
              "lemma": "<space-joined lemmas>",
              "pos": "<space-joined pos tags>"
            },
            ...
          ]
        }
      }
    }
"""

import glob
import json
import os.path as op
from dataclasses import dataclass
from typing import Iterator

import lxml.etree as et

from pycento.data import Line, Word, Syllable, parse
from pycento.segments import build_segments, CandidateSegment, is_hexameter

_ROOT = op.dirname(op.abspath(__file__))
_TEI = "http://www.tei-c.org/ns/1.0"

# Effective mora value for the form string (long/anceps/end=2, short=1, elided=skip)
_FORM_MORA = {"long": 2, "short": 1, "anceps": 2, "end": 2, "elided": None}


# ---------------------------------------------------------------------------
# Parser for ausonius-hexameter-annotated.xml
# ---------------------------------------------------------------------------

def _parse_w(w_elem) -> Word:
    """Parse a <w> element from the annotated XML into a Word."""
    form = w_elem.get("form", "")
    sylls = [
        Syllable(text=s.text, length=s.get("met"))
        for s in w_elem.findall(f"{{{_TEI}}}s")
    ]
    has_caesura = any(
        s.find(f"{{{_TEI}}}caesura") is not None
        for s in w_elem.findall(f"{{{_TEI}}}s")
    )
    return Word(
        text=form if not form.startswith("{") else "",
        lemma=w_elem.get("lemma", ""),
        pos=w_elem.get("pos", ""),
        morph=w_elem.get("msd", ""),
        syllables=sylls,
        caesura_after=has_caesura,
    )


def iter_annotated_poems(filepath: str) -> Iterator[tuple[str, list[Line]]]:
    """Yield (source_filename, lines) for each <poem> in the annotated XML."""
    tree = et.parse(filepath)
    root = tree.getroot()
    for poem in root.findall(f".//{{{_TEI}}}poem"):
        source = poem.get("source", "unknown")
        lines: list[Line] = []
        for idx, l_elem in enumerate(poem.findall(f"{{{_TEI}}}l")):
            ws = [_parse_w(w) for w in l_elem.findall(f"{{{_TEI}}}w")]
            lines.append(Line(
                idx=idx + 1,
                segments=[],
                ws=ws,
                ref=f"{source}:{l_elem.get('n', str(idx + 1))}",
            ))
        if lines:
            yield source, lines


# ---------------------------------------------------------------------------
# Segment table helpers
# ---------------------------------------------------------------------------

def segment_form(seg: CandidateSegment) -> str:
    values = []
    for word in seg.words:
        for syll in word.syllables:
            m = _FORM_MORA.get(syll.length)
            if m is not None:
                values.append(str(m))
    return " ".join(values)


def segment_entry(seg: CandidateSegment, source_label: str) -> dict:
    texts, lemmas, poses = [], [], []
    for w in seg.words:
        if w.text:
            texts.append(w.text)
        lemmas.append(w.lemma or "")
        poses.append(w.pos or "")
    return {
        "id": ", ".join(seg.refs),
        "filepath": source_label,
        "text": " ".join(texts),
        "lemma": " ".join(lemmas),
        "pos": " ".join(poses),
    }


def _add_to_table(table: dict, author: str, segs: list[CandidateSegment], source_label: str):
    author_table = table.setdefault(author, {})
    for seg in segs:
        kind_table = author_table.setdefault(seg.kind, {})
        form = segment_form(seg)
        kind_table.setdefault(form, []).append(segment_entry(seg, source_label))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_table() -> dict:
    table: dict = {}
    # --- Virgil from source XMLs (no lemma/pos) ---
    virgil_map = {
        "phi0690.phi003": "Virgil (Aeneid)",
        "phi0690.phi001": "Virgil (Eclogues)",
        "phi0690.phi002": "Virgil (Georgics)",
    }
    for filepath in sorted(glob.glob(
        op.join(_ROOT, "data", "gold", "metric", "urn:cts:latinLit:phi0690.phi00?.xml")
    )):
        key = next((k for k in virgil_map if k in filepath), None)
        author = virgil_map.get(key, op.basename(filepath))
        print(f"{author}: {op.basename(filepath)}")
        lines = parse(filepath)
        segs = build_segments(lines)
        source_label = op.relpath(filepath, _ROOT)
        _add_to_table(table, author, segs, source_label)

    return table


if __name__ == "__main__":
    table = build_table()

    out_path = op.join(_ROOT, "data", "segment_table.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=2)

    for author, kinds in table.items():
        total = sum(sum(len(v) for v in forms.values()) for forms in kinds.values())
        print(f"  {author}: {total} segments across {len(kinds)} kinds")

    print(f"\nWrote {out_path}")

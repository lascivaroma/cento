"""Generate random centos matching the exact metrical sequence of the Cento Nuptialis.

For each cento line (or cross-line sequence when a segment is continued), the
full metrical form string is extracted from cento.xml. A SINGLE source entry
is selected whose normalized form matches the full sequence, then its words and
syllables are split at the original segment boundaries to produce the correct
number of <seg> elements.

For continued sequences (line N last seg + line N+1 first continued seg), the
combined form is computed and multi-line kinds (H2+H1, H2+AB, AB+H1, AB+AB)
from segment_table.json are included alongside AB entries.

The last syllable of every sequence is always treated as anceps (end, 2 morae).

Usage:
    python generate_centos_metric.py [--count N] [--authors AUTHOR ...]
    python generate_centos_metric.py --count 100 --seed 42
"""

import argparse
import json
import os
import os.path as op
import random
from dataclasses import dataclass

import lxml.etree as et

from pycento.data import parse_cento, Line

_ROOT = op.dirname(op.abspath(__file__))
_TEI = "http://www.tei-c.org/ns/1.0"
_MORA = {"long": 2, "short": 1, "anceps": 2, "end": 2, "elided": 0}


# ---------------------------------------------------------------------------
# Template: one entry per sequence (line or cross-line pair)
# ---------------------------------------------------------------------------

@dataclass
class Sequence:
    """One metrically coherent unit to fill with a single source entry."""
    lines: list[int]            # cento line numbers covered (1 or 2)
    full_form: str              # normalized mora sequence for the whole span
    splits: list[int]           # mora positions of segment boundaries within span
    continueds: list[bool]      # continued flag per segment


def _seg_raw_sylls(seg) -> list[int]:
    """Return mora values (excluding elided) for a segment's syllables."""
    return [_MORA[s.length] for w in seg.words for s in w.syllables
            if _MORA.get(s.length, 0) > 0]


def _normalize(values: list[int]) -> str:
    if not values:
        return ""
    v = list(values)
    v[-1] = 2
    return " ".join(str(x) for x in v)


def extract_template(lines: list[Line]) -> list[Sequence]:
    sequences: list[Sequence] = []
    consumed = set()  # line indices already merged into a cross-line sequence

    for i, line in enumerate(lines):
        if line.idx in consumed:
            continue

        segs = line.segments
        if not segs:
            continue

        # Check if the NEXT line starts with a continued segment → cross-line sequence
        next_line = lines[i + 1] if i + 1 < len(lines) else None
        if (next_line and next_line.segments
                and next_line.segments[0].continued):
            # Cross-line: last seg of this line + first (continued) seg of next line
            # form a single sequence entry; the rest of next_line is independent
            tail_seg = segs[-1]
            head_seg = next_line.segments[0]

            tail_vals = _seg_raw_sylls(tail_seg)
            head_vals = _seg_raw_sylls(head_seg)
            combined = tail_vals + head_vals
            split_at = sum(tail_vals)  # mora boundary between the two halves

            sequences.append(Sequence(
                lines=[line.idx, next_line.idx],
                full_form=_normalize(combined),
                splits=[split_at],
                continueds=[tail_seg.continued, True],
            ))
            consumed.add(next_line.idx)

            # Any preceding segs on this line are independent single-seg sequences
            for seg in segs[:-1]:
                vals = _seg_raw_sylls(seg)
                sequences.append(Sequence(
                    lines=[line.idx],
                    full_form=_normalize(vals),
                    splits=[],
                    continueds=[seg.continued],
                ))

            # Any remaining segs on next_line after the continued one are independent
            for seg in next_line.segments[1:]:
                vals = _seg_raw_sylls(seg)
                sequences.append(Sequence(
                    lines=[next_line.idx],
                    full_form=_normalize(vals),
                    splits=[],
                    continueds=[seg.continued],
                ))
        else:
            # Single-line: treat all segs as one sequence per line
            all_vals = []
            splits = []
            for seg in segs:
                vals = _seg_raw_sylls(seg)
                all_vals.extend(vals)
                splits.append(sum(all_vals))

            sequences.append(Sequence(
                lines=[line.idx],
                full_form=_normalize(all_vals),
                splits=splits[:-1],          # exclude the final total
                continueds=[s.continued for s in segs],
            ))

    # Sort by first line so generation is in order
    sequences.sort(key=lambda s: (s.lines[0], len(s.lines)))
    return sequences


# ---------------------------------------------------------------------------
# Index: full_form -> list of entries (AB + multi-line kinds)
# ---------------------------------------------------------------------------

_SEQUENCE_KINDS = {"AB", "H2+H1", "H2+AB", "AB+H1", "AB+AB"}


def build_index(table: dict, authors: list[str] | None = None) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for author, kinds in table.items():
        if authors and author not in authors:
            continue
        for kind, forms in kinds.items():
            if kind not in _SEQUENCE_KINDS:
                continue
            for form_str, entries in forms.items():
                norm = _normalize([int(v) for v in form_str.split()])
                if not norm:
                    continue
                bucket = index.setdefault(norm, [])
                for entry in entries:
                    bucket.append({**entry, "_form": norm, "_author": author, "_kind": kind})
    return index


# ---------------------------------------------------------------------------
# XML generation: split one entry across segment boundaries
# ---------------------------------------------------------------------------

def _form_to_mets(form_str: str) -> list[str]:
    """Normalized form → syllable met values (last = 'end')."""
    parts = form_str.split()
    result = []
    for i, v in enumerate(parts):
        if i == len(parts) - 1:
            result.append("end")
        elif v == "2":
            result.append("long")
        else:
            result.append("short")
    return result


def _split_at_mora(form_str: str, mora_boundary: int) -> tuple[str, str]:
    """Split a form string at a mora boundary into two sub-forms."""
    values = [int(v) for v in form_str.split()]
    acc, cut = 0, len(values)
    for i, v in enumerate(values):
        acc += v
        if acc >= mora_boundary:
            cut = i + 1
            break
    return (" ".join(str(v) for v in values[:cut]),
            " ".join(str(v) for v in values[cut:]))


def _words_to_xml(parent: et.Element, words: list[str], lemmas: list[str],
                   poses: list[str], mets: list[str]):
    """Write <w> elements distributing mets syllables across words."""
    n = len(words) if words else 1
    base, rem = divmod(len(mets), n)
    pos = 0
    for i, form in enumerate(words):
        size = base + (1 if i < rem else 0)
        chunk = mets[pos:pos + size]
        pos += size
        w = et.SubElement(parent, f"{{{_TEI}}}w", attrib={"form": form})
        if i < len(lemmas) and lemmas[i]:
            w.set("lemma", lemmas[i])
        if i < len(poses) and poses[i]:
            w.set("pos", poses[i])
        for met in chunk:
            et.SubElement(w, f"{{{_TEI}}}s", attrib={"met": met})


def _add_seg(l_elem: et.Element, entry: dict, form_part: str, continued: bool):
    attrib = {"source": entry["filepath"], "ref": entry["id"], "form": form_part}
    if continued:
        attrib["type"] = "sq"
    seg = et.SubElement(l_elem, f"{{{_TEI}}}seg", attrib=attrib)
    words = entry["text"].split()
    lemmas = entry["lemma"].split() if entry.get("lemma") else []
    poses = entry["pos"].split() if entry.get("pos") else []
    mets = _form_to_mets(form_part)
    _words_to_xml(seg, words, lemmas, poses, mets)


def generate_poem(
    poem_n: int,
    sequences: list[Sequence],
    index: dict[str, list[dict]],
    l_elements: dict[int, et.Element],
) -> et.Element:
    cento = et.Element(f"{{{_TEI}}}cento", attrib={"n": str(poem_n), "generated": "true"})
    # Pre-create line elements in order
    line_elems: dict[int, et.Element] = {}
    all_lines = sorted({ln for seq in sequences for ln in seq.lines})
    for ln in all_lines:
        line_elems[ln] = et.SubElement(cento, f"{{{_TEI}}}l", attrib={"n": str(ln)})

    used_refs: set[str] = set()

    for seq in sequences:
        candidates = index.get(seq.full_form, [])
        if not candidates:
            continue
        pool = [e for e in candidates if e["id"] not in used_refs] or candidates
        entry = random.choice(pool)
        used_refs.add(entry["id"])

        if not seq.splits:
            # Single segment — write directly to its line
            _add_seg(line_elems[seq.lines[0]], entry, seq.full_form, seq.continueds[0])
        else:
            # Split entry across segment boundaries
            remaining_form = seq.full_form
            mora_offset = 0
            part_forms = []
            for boundary in seq.splits:
                local_boundary = boundary - mora_offset
                left, remaining_form = _split_at_mora(remaining_form, local_boundary)
                part_forms.append(left)
                mora_offset = boundary
            part_forms.append(remaining_form)

            # Assign each part to the correct line
            # segs alternate across lines; for cross-line sequences, first part
            # goes to lines[0] and second to lines[1] (or all to lines[0] for single-line)
            line_idx_for_part = []
            if len(seq.lines) == 2:
                # cross-line: last part of lines[0] + first part of lines[1]
                # parts before the cross-boundary → lines[0], after → lines[1]
                # The cross-boundary is the last split (seq.splits[-1])
                for k in range(len(part_forms) - 1):
                    line_idx_for_part.append(seq.lines[0])
                line_idx_for_part.append(seq.lines[1])
            else:
                line_idx_for_part = [seq.lines[0]] * len(part_forms)

            for k, (part_form, continued) in enumerate(zip(part_forms, seq.continueds)):
                _add_seg(line_elems[line_idx_for_part[k]], entry, part_form, continued)

    return cento


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate metrically exact random centos (sequence level)")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--authors", nargs="*", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print("Parsing cento.xml...")
    lines = parse_cento(op.join(_ROOT, "data", "gold", "cento.xml"))

    print("Extracting sequence-level template...")
    sequences = extract_template(lines)
    unique_forms = set(s.full_form for s in sequences)
    cross_line = sum(1 for s in sequences if len(s.lines) == 2)
    print(f"  {len(sequences)} sequences ({cross_line} cross-line), "
          f"{len(unique_forms)} distinct forms")

    print("Loading segment table...")
    with open(op.join(_ROOT, "data", "segment_table.json"), encoding="utf-8") as fh:
        table = json.load(fh)

    index = build_index(table, authors=args.authors)
    covered = sum(1 for f in unique_forms if f in index)
    print(f"  Index: {len(index)} forms, coverage {covered}/{len(unique_forms)} "
          f"({100*covered//len(unique_forms)}%)")

    out_dir = op.join(_ROOT, "data", "generated")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\nGenerating {args.count} poems → {out_dir}/")
    for n in range(1, args.count + 1):
        cento_elem = generate_poem(n, sequences, index, {})
        et.indent(cento_elem, space="  ")
        out_path = op.join(out_dir, f"cento_{n:04d}.xml")
        et.ElementTree(cento_elem).write(out_path, encoding="utf-8",
                                          xml_declaration=True, pretty_print=True)
        if n % 100 == 0:
            print(f"  {n}/{args.count}")

    print(f"Done. {args.count} files in {out_dir}/")


if __name__ == "__main__":
    main()

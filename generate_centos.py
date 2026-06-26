"""Generate random centos following the structural pattern of the Cento Nuptialis.

Each generated poem mirrors the exact line-by-line pattern of the real cento
(which lines are AB, H1+H2, H2+H1, etc.) but fills each slot with a randomly
chosen segment of the matching kind from segment_table.json.

Usage:
    python generate_centos.py [--count N] [--authors AUTHOR ...]
    python generate_centos.py --count 1000
    python generate_centos.py --count 100 --authors Ausonius

Output: data/generated/cento_{n:04d}.xml
"""

import argparse
import json
import os
import os.path as op
import random

import lxml.etree as et

_ROOT = op.dirname(op.abspath(__file__))
_TEI = "http://www.tei-c.org/ns/1.0"
_MORA = {"long": 2, "short": 1, "anceps": 2, "end": 2, "elided": 0}

# ---------------------------------------------------------------------------
# Extract the structural template from the real cento
# ---------------------------------------------------------------------------

def _seg_morae(seg) -> int:
    return sum(_MORA.get(s.length, 0) for w in seg.words for s in w.syllables)


def _classify_seg(morae: int) -> str:
    if morae < 14:
        return "H1"
    if morae < 22:
        return "H2"
    return "AB"


def extract_template() -> list[list[str]]:
    """Return a list of 131 entries, each a list of kind strings for that cento line."""
    from pycento.data import parse_cento
    lines = parse_cento(op.join(_ROOT, "data", "gold", "metric", "cento-aligned.xml"))
    template = []
    for line in lines:
        morae_per_seg = [_seg_morae(s) for s in line.segments]
        if len(morae_per_seg) == 1:
            kinds = [_classify_seg(morae_per_seg[0])]
        else:
            kinds = [_classify_seg(m) for m in morae_per_seg]
        template.append(kinds)
    return template


# ---------------------------------------------------------------------------
# Build a flat index: kind -> list of entry dicts (with syllable data inlined)
# ---------------------------------------------------------------------------

def build_index(table: dict, authors: list[str] | None = None) -> dict[str, list[dict]]:
    """Flatten segment_table.json into kind -> [entry, ...].

    Each entry is augmented with 'form' (the metrical pattern string) so the
    XML writer can reconstruct syllable elements.
    """
    index: dict[str, list[dict]] = {}
    for author, kinds in table.items():
        if authors and author not in authors:
            continue
        for kind, forms in kinds.items():
            bucket = index.setdefault(kind, [])
            for form_str, entries in forms.items():
                for entry in entries:
                    bucket.append({**entry, "_form": form_str, "_author": author})
    return index


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------

def _form_to_syllables(form_str: str) -> list[str]:
    """Convert '2 1 1 2' → ['long', 'short', 'short', 'long']."""
    mapping = {"2": "long", "1": "short"}
    return [mapping.get(v, "long") for v in form_str.split()]


def _words_to_xml(parent: et.Element, entry: dict):
    """Append <w> children to parent reconstructing form/lemma/pos/msd/<s> data."""
    forms = entry["text"].split()
    lemmas = entry["lemma"].split() if entry.get("lemma") else []
    poses = entry["pos"].split() if entry.get("pos") else []
    sylls_all = _form_to_syllables(entry["_form"])

    # Distribute syllables across words heuristically: each word gets as many
    # syllables as it has vowel nuclei (rough estimate). Since we only have the
    # aggregate form string, we attach all syllables to a single <w> element
    # per entry and rely on the morph attributes for linguistic info.
    # A more precise reconstruction would require syllable-per-word counts.

    # Write one <w> per word token, attaching syllables proportionally.
    # We spread syllables evenly across words using a greedy split.
    n_words = len(forms) if forms else 1
    syll_chunks = _split_syllables(sylls_all, n_words)

    for i, form in enumerate(forms):
        w = et.SubElement(parent, f"{{{_TEI}}}w", attrib={"form": form})
        if i < len(lemmas) and lemmas[i]:
            w.set("lemma", lemmas[i])
        if i < len(poses) and poses[i]:
            w.set("pos", poses[i])
        for met in syll_chunks[i]:
            et.SubElement(w, f"{{{_TEI}}}s", attrib={"met": met})


def _split_syllables(sylls: list[str], n: int) -> list[list[str]]:
    """Divide syllable list into n roughly equal chunks."""
    if n == 0:
        return []
    base, rem = divmod(len(sylls), n)
    chunks, pos = [], 0
    for i in range(n):
        size = base + (1 if i < rem else 0)
        chunks.append(sylls[pos:pos + size])
        pos += size
    return chunks


def generate_poem(poem_n: int, template: list[list[str]], index: dict[str, list[dict]]) -> et.Element:
    cento = et.Element(f"{{{_TEI}}}cento", attrib={"n": str(poem_n), "generated": "true"})

    for line_n, kinds in enumerate(template, start=1):
        l_elem = et.SubElement(cento, f"{{{_TEI}}}l", attrib={"n": str(line_n)})
        used_refs: set[str] = set()

        for kind in kinds:
            candidates = index.get(kind, [])
            if not candidates:
                continue
            # Avoid reusing the same source segment within this line
            pool = [e for e in candidates if e["id"] not in used_refs] or candidates
            entry = random.choice(pool)
            used_refs.add(entry["id"])

            seg = et.SubElement(l_elem, f"{{{_TEI}}}seg", attrib={
                "kind": kind,
                "source": entry["filepath"],
                "ref": entry["id"],
            })
            _words_to_xml(seg, entry)

    return cento


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate random centos")
    parser.add_argument("--count", type=int, default=1000, help="Number of poems to generate")
    parser.add_argument("--authors", nargs="*", default=None,
                        help="Restrict to specific authors, e.g. Ausonius 'Virgil (Aeneid)'")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print("Loading segment table...")
    table_path = op.join(_ROOT, "data", "segment_table.json")
    with open(table_path, encoding="utf-8") as fh:
        table = json.load(fh)

    print("Extracting cento template...")
    template = extract_template()
    kind_counts = {}
    for kinds in template:
        key = "+".join(kinds)
        kind_counts[key] = kind_counts.get(key, 0) + 1
    print(f"  Template: {dict(sorted(kind_counts.items(), key=lambda x: -x[1]))}")

    index = build_index(table, authors=args.authors)
    for kind, entries in index.items():
        print(f"  Pool {kind}: {len(entries)} candidates")

    out_dir = op.join(_ROOT, "data", "generated")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\nGenerating {args.count} poems → {out_dir}/")
    for n in range(1, args.count + 1):
        cento_elem = generate_poem(n, template, index)
        tree = et.ElementTree(cento_elem)
        et.indent(cento_elem, space="  ")
        out_path = op.join(out_dir, f"cento_{n:04d}.xml")
        tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        if n % 100 == 0:
            print(f"  {n}/{args.count}")

    print(f"Done. {args.count} files in {out_dir}/")


if __name__ == "__main__":
    main()

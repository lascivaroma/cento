"""Extract all hexameter lines from Ausonius works into a single TEI XML.

Each consecutive run of hexameter lines within a source file becomes a <poem>
element. Non-hexameter lines (pentameters, iambics, etc.) break the run and
are discarded.

Output: data/ausonius-hexameter.xml
"""

import glob
import os.path as op
from itertools import groupby

import lxml.etree as et

_ROOT = op.dirname(op.abspath(__file__))
_TEI = "http://www.tei-c.org/ns/1.0"
_NS = {"t": _TEI}
_MORA = {"long": 2, "short": 1, "anceps": 2, "end": 2, "elided": 0}


# ---------------------------------------------------------------------------
# Hexameter detection (operates on raw lxml elements)
# ---------------------------------------------------------------------------

def _line_morae(l_elem) -> int:
    """Sum morae of all syllables in a <l> element (namespace-agnostic)."""
    total = 0
    for s in l_elem.iter("{%s}s" % _TEI):
        total += _MORA.get(s.get("met", ""), 0)
    # Fallback: no-namespace syllables
    if total == 0:
        for s in l_elem.iter("s"):
            total += _MORA.get(s.get("met", ""), 0)
    return total


def _is_hexameter(l_elem) -> bool:
    return _line_morae(l_elem) == 24


# ---------------------------------------------------------------------------
# Namespace normalisation helpers
# ---------------------------------------------------------------------------

def _strip_ns(tag: str) -> str:
    """Return local name without namespace."""
    return tag.split("}")[-1] if "}" in tag else tag


def _copy_to_tei(src_elem) -> et.Element:
    """Deep-copy src_elem into TEI namespace, preserving attributes and text."""
    local = _strip_ns(src_elem.tag)
    dst = et.Element("{%s}%s" % (_TEI, local), attrib=src_elem.attrib)
    dst.text = src_elem.text
    dst.tail = None  # tails belong to the parent context, drop them
    for child in src_elem:
        child_local = _strip_ns(child.tag)
        if child_local == "caesura":
            c = et.SubElement(dst, "{%s}caesura" % _TEI)
            c.tail = child.tail
        else:
            dst.append(_copy_to_tei(child))
    return dst


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

_EXCLUDE = {"AVSON-cent.xml"}  # the cento itself is not a source for generation


def build_hexameter_xml(source_files: list[str]) -> et.Element:
    body = et.Element("{%s}body" % _TEI)

    poem_counter = 0
    for filepath in source_files:
        filename = op.basename(filepath)
        if filename in _EXCLUDE:
            print(f"  SKIP {filename} (excluded)")
            continue
        try:
            tree = et.parse(filepath)
        except et.XMLSyntaxError as exc:
            print(f"  SKIP {filename}: {exc}")
            continue

        root = tree.getroot()
        # Collect <l> elements regardless of namespace
        l_elems = root.findall(".//{%s}l" % _TEI) or root.findall(".//l")

        if not l_elems:
            continue

        # Tag each line as hexameter (True) or not (False)
        tagged = [(elem, _is_hexameter(elem)) for elem in l_elems]

        # Group into consecutive runs of hexameter lines
        for is_hex, group_iter in groupby(tagged, key=lambda x: x[1]):
            if not is_hex:
                continue
            group = list(group_iter)
            poem_counter += 1
            poem = et.SubElement(body, "{%s}poem" % _TEI, attrib={
                "n": str(poem_counter),
                "source": filename,
            })
            for l_elem, _ in group:
                poem.append(_copy_to_tei(l_elem))

    return body


if __name__ == "__main__":
    sources = sorted(glob.glob(op.join(_ROOT, "data", "ausonius-gold", "AVSON-*.xml")))
    print(f"Processing {len(sources)} Ausonius files...")

    body = build_hexameter_xml(sources)

    # Wrap in a minimal TEI document
    tei = et.Element("{%s}TEI" % _TEI)
    tei.append(body)

    poems = body.findall("{%s}poem" % _TEI)
    total_lines = sum(len(p) for p in poems)
    print(f"  {len(poems)} poem sections, {total_lines} hexameter lines total")

    # Pretty-print
    et.indent(tei, space="    ")
    tree = et.ElementTree(tei)

    out_path = op.join(_ROOT, "data", "ausonius-hexameter.xml")
    tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    print(f"Wrote {out_path}")

    # Per-source summary
    from collections import Counter
    source_counts = Counter(p.get("source") for p in poems)
    for src, n in sorted(source_counts.items()):
        line_count = sum(len(p) for p in poems if p.get("source") == src)
        print(f"  {src:20s}  {n:3d} poem(s)  {line_count:5d} lines")

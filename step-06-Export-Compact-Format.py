"""Export line-based sources into the compact Pedecerto-style sy=/mf=/pattern=
format (see pycento/serialize.py — the inverse of
data/ausonius-raw/0-converter.py's decoding), respecting each source's natural
grouping: one continuous poem (cento), per-poem <div> (Ausonius hexameters),
or per-book <div> (Virgil).

Usage:
    python step-06-Export-Compact-Format.py --source cento
    python step-06-Export-Compact-Format.py --source ausonius
    python step-06-Export-Compact-Format.py --source virgil
    python step-06-Export-Compact-Format.py --source custom --input PATH --output PATH

Output goes to data/generated-compact/{cento,ausonius,virgil}-compact.xml
(for --source custom, to the --output path given).
"""

import argparse
import itertools
import os
import os.path as op

import lxml.etree as et

from pycento.data import parse_cento, parse, parse_line_element
from pycento.serialize import line_to_compact_xml
from pycento.virgil_index import _VIRGIL_FILES

_ROOT = op.dirname(op.abspath(__file__))
_TEI = "http://www.tei-c.org/ns/1.0"
_OUT_DIR = op.join(_ROOT, "data", "generated-compact")


def _write(root: et.Element, out_path: str) -> None:
    et.indent(root, space="    ")
    et.ElementTree(root).write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    print(f"Wrote {out_path}")


def export_cento() -> None:
    lines = parse_cento(op.join(_ROOT, "data", "gold", "cento.xml"))
    root = et.Element("text")
    counter = itertools.count(1)
    for line in lines:
        line_to_compact_xml(line, root, counter)
    _write(root, op.join(_OUT_DIR, "cento-compact.xml"))


def export_ausonius() -> None:
    annotated = op.join(_ROOT, "data", "ausonius-hexameter-annotated.xml")
    in_path = annotated if op.exists(annotated) else op.join(_ROOT, "data", "ausonius-hexameter.xml")

    tree = et.parse(in_path)
    root_out = et.Element("text")
    counter = itertools.count(1)
    for poem in tree.xpath("//t:poem", namespaces={"t": _TEI}):
        div = et.SubElement(root_out, "div", attrib={
            "type": "poem",
            "n": poem.get("n", ""),
            "source": poem.get("source", ""),
        })
        for idx, l_elem in enumerate(poem.xpath("./t:l", namespaces={"t": _TEI})):
            line_to_compact_xml(parse_line_element(l_elem, idx), div, counter)
    _write(root_out, op.join(_OUT_DIR, "ausonius-compact.xml"))


def _book_of(ref: str) -> str:
    """'urn:cts:latinLit:phi0690.phi003:1.545' -> '1'"""
    *_, passage = ref.split(":")
    book, _, _ = passage.partition(".")
    return book


def export_virgil() -> None:
    root_out = et.Element("text")
    counter = itertools.count(1)
    for filename, display_name in sorted(_VIRGIL_FILES.items()):
        annotated = op.join(_ROOT, "data", "gold", "metric", f"urn:cts:latinLit:{filename}-annotated.xml")
        plain = op.join(_ROOT, "data", "gold", "metric", f"urn:cts:latinLit:{filename}.xml")
        in_path = annotated if op.exists(annotated) else plain

        work_div = et.SubElement(root_out, "div", attrib={"type": "work", "n": filename, "title": display_name})
        book_div, current_book = None, object()  # sentinel guarantees first line opens a div
        for line in parse(in_path):
            book = _book_of(line.ref) if line.ref else None
            if book != current_book:
                book_div = et.SubElement(work_div, "div", attrib={"type": "book", "n": book or "?"})
                current_book = book
            line_to_compact_xml(line, book_div, counter)
    _write(root_out, op.join(_OUT_DIR, "virgil-compact.xml"))


def export_custom(input_path: str, output_path: str) -> None:
    """Same-shaped-as-Ausonius input: plain <l>/<w>/<s>, optionally wrapped in
    <poem> elements (reuses the poem grouping if present; otherwise emitted
    as one ungrouped run, since a generic file has no book-number convention
    to fall back on)."""
    tree = et.parse(input_path)
    root_out = et.Element("text")
    counter = itertools.count(1)

    poems = tree.xpath("//t:poem", namespaces={"t": _TEI}) or tree.xpath("//poem")
    if poems:
        for poem in poems:
            div = et.SubElement(root_out, "div", attrib={
                "type": "poem",
                "n": poem.get("n", ""),
                "source": poem.get("source", ""),
            })
            ns = {"t": _TEI} if poem.nsmap.get(None) == _TEI else {}
            for idx, l_elem in enumerate(poem.xpath(f"./{'t:l' if ns else 'l'}", namespaces=ns)):
                line_to_compact_xml(parse_line_element(l_elem, idx), div, counter)
    else:
        for line in parse(input_path):
            line_to_compact_xml(line, root_out, counter)

    _write(root_out, output_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, choices=["cento", "ausonius", "virgil", "custom"])
    parser.add_argument("--input", help="Input file path (only for --source custom)")
    parser.add_argument("--output", help="Output file path (only for --source custom)")
    args = parser.parse_args()

    os.makedirs(_OUT_DIR, exist_ok=True)

    if args.source == "cento":
        export_cento()
    elif args.source == "ausonius":
        export_ausonius()
    elif args.source == "virgil":
        export_virgil()
    else:
        if not args.input or not args.output:
            parser.error("--source custom requires --input and --output")
        export_custom(args.input, args.output)


if __name__ == "__main__":
    main()

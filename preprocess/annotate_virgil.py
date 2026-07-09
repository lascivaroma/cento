"""Annotate the Virgil metric source files with lemma/pos/msd from the LASLA
model, so segments matched purely from Virgil (not traceable back to already-
tagged data/gold/cento.xml text) can also carry POS data downstream.

Adapted from annotate_ausonius_hexameter.py: same tagger, same per-line
tag-and-align approach, just looped over the three Virgil works instead of a
single hexameter file. Each input file gets a sibling `-annotated.xml` output
(data/gold/metric/urn:cts:latinLit:phi0690.phi00X-annotated.xml), mirroring
the existing data/ausonius-hexameter.xml -> -annotated.xml convention — the
pristine syllable-only gold files are left untouched.

Run with the repo root on PYTHONPATH, e.g.:
    PYTHONPATH=. python preprocess/annotate_virgil.py
"""

import os.path as op
import sys

import lxml.etree as et
from tqdm import tqdm

sys.path.insert(0, op.dirname(op.abspath(__file__)))
from annotate_ausonius_hexameter import load_tagger, annotate_line
from pycento.virgil_index import _VIRGIL_FILES

_TEI = "http://www.tei-c.org/ns/1.0"
_ROOT = op.dirname(op.abspath(__file__))
_METRIC_DIR = op.join(_ROOT, "..", "data", "gold", "metric")


def main():
    print("Loading LASLA model...")
    tagger, iterator, processor = load_tagger()
    print("Model loaded.\n")

    for filename, display_name in sorted(_VIRGIL_FILES.items()):
        in_path = op.join(_METRIC_DIR, f"urn:cts:latinLit:{filename}.xml")
        out_path = op.join(_METRIC_DIR, f"urn:cts:latinLit:{filename}-annotated.xml")

        tree = et.parse(in_path)
        root = tree.getroot()
        lines = root.findall(f".//{{{_TEI}}}l")
        print(f"Annotating {display_name} ({len(lines)} lines)...")

        for l_elem in tqdm(lines, unit="line", desc=display_name):
            annotate_line(l_elem, tagger, iterator, processor)

        et.indent(root, space="    ")
        tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        print(f"  Wrote {out_path}")

        sample = root.findall(f".//{{{_TEI}}}w")[:5]
        print("  Sample annotations:")
        for w in sample:
            print(f"    form={w.get('form'):20s} lemma={w.get('lemma', ''):20s} "
                  f"pos={w.get('pos', ''):10s} msd={w.get('msd', '')}")
        print()


if __name__ == "__main__":
    main()

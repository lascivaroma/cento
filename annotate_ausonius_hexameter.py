"""Annotate data/ausonius-hexameter.xml with lemma/pos/morph from the LASLA model.

Words are already segmented; we pass each verse as a pre-tokenized string and
map results back by position. The model handles normalisation (u/v, j/i, etc.)
internally via the MemorizingTokenizer, which restores original forms in output.

Adds/overwrites lemma=, pos=, msd= attributes on every <w> element.
Writes output to data/ausonius-hexameter-annotated.xml.
"""

import re
import os.path as op
from tqdm import tqdm

import lxml.etree as et

_TEI = "http://www.tei-c.org/ns/1.0"
_NS = {"t": _TEI}
_ROOT = op.dirname(op.abspath(__file__))


# ---------------------------------------------------------------------------
# Load the LASLA model (done once)
# ---------------------------------------------------------------------------

def load_tagger():
    from pie_extended.models.lasla import Models
    from pie_extended.models.lasla.imports import get_iterator_and_processor, Disambiguator
    from pie_extended.tagger import ExtensibleTagger

    tagger = ExtensibleTagger(disambiguation=Disambiguator.create())
    entries = re.findall(r"<([^>]+)>", Models)
    for entry in entries:
        path, task = entry.split(",")
        tagger.add_model(path, task)

    iterator, processor = get_iterator_and_processor()
    return tagger, iterator, processor


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------

def words_of_line(l_elem) -> list:
    """Return <w> elements in document order (TEI namespace)."""
    return l_elem.findall(f"{{{_TEI}}}w")


def verse_text(w_elems) -> str:
    """Build a space-joined string of word forms for the tagger."""
    return " ".join(w.get("form", "") for w in w_elems if w.get("form"))


def annotate_line(l_elem, tagger, iterator, processor):
    w_elems = words_of_line(l_elem)
    if not w_elems:
        return

    text = verse_text(w_elems)
    if not text.strip():
        return

    try:
        results = tagger.tag_str(text, iterator, processor, no_tokenizer=False)
    except Exception as exc:
        print(f"  [WARN] tagging failed for '{text[:60]}': {exc}")
        return

    # Match results back to <w> elements by form (the tokenizer may skip
    # punctuation tokens; we iterate both lists together, ignoring None gaps).
    result_iter = iter(r for r in results if r is not None)
    for w in w_elems:
        form = w.get("form", "")
        if not form:
            continue
        try:
            token = next(result_iter)
        except StopIteration:
            break
        w.set("lemma", token.get("lemma", ""))
        w.set("pos", token.get("pos", ""))
        w.set("msd", token.get("morph", ""))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    in_path = op.join(_ROOT, "data", "ausonius-hexameter.xml")
    out_path = op.join(_ROOT, "data", "ausonius-hexameter-annotated.xml")

    print("Loading LASLA model...")
    tagger, iterator, processor = load_tagger()
    print("Model loaded.\n")

    tree = et.parse(in_path)
    root = tree.getroot()

    lines = root.findall(f".//{{{_TEI}}}l")
    print(f"Annotating {len(lines)} lines...")

    for l_elem in tqdm(lines, unit="line"):
        annotate_line(l_elem, tagger, iterator, processor)

    et.indent(root, space="    ")
    tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    print(f"\nWrote {out_path}")

    # Quick spot-check
    sample = root.findall(f".//{{{_TEI}}}w")[:5]
    print("\nSample annotations:")
    for w in sample:
        print(f"  form={w.get('form'):20s} lemma={w.get('lemma', ''):20s} pos={w.get('pos', ''):10s} msd={w.get('msd', '')}")


if __name__ == "__main__":
    main()

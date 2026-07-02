"""Generate random centos following the structural pattern of the Cento Nuptialis.

The line-by-line template is read from segment_stats.csv (produced by
stats_segments.py). Each slot is filled with a randomly chosen segment whose
normalized mora count matches the slot's target (the last syllable of every
segment is always treated as anceps = 2 morae regardless of its marked value).

Usage:
    python generate_centos.py [--count N] [--authors AUTHOR ...]
    python generate_centos.py --count 1000
    python generate_centos.py --count 100 --authors Ausonius

Output: data/generated/cento_{n:04d}.xml
"""

import argparse
import csv
import json
import os
import os.path as op
import random

import lxml.etree as et

_ROOT = op.dirname(op.abspath(__file__))
_TEI = "http://www.tei-c.org/ns/1.0"
_MORA = {"long": 2, "short": 1, "anceps": 2, "end": 2, "elided": 0}


# ---------------------------------------------------------------------------
# Template from segment_stats.csv
# ---------------------------------------------------------------------------

def read_template() -> list[list[tuple[int, bool]]]:
    """Read segment_stats.csv and return a list of lines.

    Each line is a list of (raw_morae, continued) tuples.
    For continued segments (combined morae stored in CSV), raw morae is
    recovered as: total_morae - sum(non-continued segment morae).
    """
    csv_path = op.join(_ROOT, "segment_stats.csv")
    template = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n = int(row["n_segments"])
            total = int(row["total_morae"])
            segs = []
            for i in range(1, n + 1):
                raw = row.get(f"seg{i}_morae", "")
                cont = row.get(f"seg{i}_continued", "False") == "True"
                segs.append((int(raw) if raw else 0, cont))

            # Recover raw morae for continued segments
            non_cont_total = sum(m for m, c in segs if not c)
            result = []
            for morae, cont in segs:
                if cont:
                    result.append((total - non_cont_total, True))
                else:
                    result.append((morae, False))
            template.append(result)
    return template


# ---------------------------------------------------------------------------
# Build index: normalized_morae -> list of entries
# ---------------------------------------------------------------------------

def _normalize_form(form_str: str) -> str:
    """Replace the last mora value with '2' (anceps rule)."""
    parts = form_str.split()
    if not parts:
        return form_str
    parts[-1] = "2"
    return " ".join(parts)


def _form_total(form_str: str) -> int:
    return sum(int(v) for v in form_str.split())


def build_index(table: dict, authors: list[str] | None = None) -> dict[int, list[dict]]:
    """Flatten segment_table.json into normalized_mora_count -> [entry, ...]."""
    index: dict[int, list[dict]] = {}
    for author, kinds in table.items():
        if authors and author not in authors:
            continue
        for kind, forms in kinds.items():
            for form_str, entries in forms.items():
                norm = _normalize_form(form_str)
                total = _form_total(norm)
                bucket = index.setdefault(total, [])
                for entry in entries:
                    bucket.append({**entry, "_form": norm, "_author": author, "_kind": kind})
    return index


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------

def _form_to_syllables(form_str: str) -> list[str]:
    """Convert normalized form string to syllable length list.

    Last value is always '2' (anceps), rendered as 'end'.
    """
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


def _words_to_xml(parent: et.Element, entry: dict):
    forms = entry["text"].split()
    lemmas = entry["lemma"].split() if entry.get("lemma") else []
    poses = entry["pos"].split() if entry.get("pos") else []
    sylls_all = _form_to_syllables(entry["_form"])
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


def generate_poem(poem_n: int, template: list[list[tuple[int, bool]]], index: dict[int, list[dict]]) -> et.Element:
    cento = et.Element(f"{{{_TEI}}}cento", attrib={"n": str(poem_n), "generated": "true"})

    for line_n, segs in enumerate(template, start=1):
        l_elem = et.SubElement(cento, f"{{{_TEI}}}l", attrib={"n": str(line_n)})
        used_refs: set[str] = set()

        for morae, continued in segs:
            candidates = index.get(morae, [])
            if not candidates:
                continue
            pool = [e for e in candidates if e["id"] not in used_refs] or candidates
            entry = random.choice(pool)
            used_refs.add(entry["id"])

            attrib = {"source": entry["filepath"], "ref": entry["id"], "morae": str(morae)}
            if continued:
                attrib["type"] = "sq"
            seg = et.SubElement(l_elem, f"{{{_TEI}}}seg", attrib=attrib)
            _words_to_xml(seg, entry)

    return cento


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate random centos")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--authors", nargs="*", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print("Loading segment table...")
    with open(op.join(_ROOT, "data", "segment_table.json"), encoding="utf-8") as fh:
        table = json.load(fh)

    print("Reading template from segment_stats.csv...")
    template = read_template()
    from collections import Counter
    schema_counts = Counter(
        "+".join(("~" if c else "") + str(m) for m, c in line)
        for line in template
    )
    print(f"  {len(template)} lines, {len(schema_counts)} distinct schemas")

    index = build_index(table, authors=args.authors)
    print(f"  {sum(len(v) for v in index.values())} segments across {len(index)} mora counts")

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

#!/usr/bin/env python3
"""Generate metrical detail files from source scansion data.

Reads XML (Pedecerto) or JSON (hypotactic) source files and produces a
human-readable tabular report showing per-word scansion details for each
hexameter line.

Auto-detects input format by file extension (.xml or .json).

Output files are named {stem}_metrical_details.txt.

Usage:
    PYTHONPATH=scripts python scripts/generate_metrical_details.py SOURCE_FILE [SOURCE_FILE ...]
    PYTHONPATH=scripts python scripts/generate_metrical_details.py data/generated-compact/exact/cento_0001.xml
    PYTHONPATH=scripts python scripts/generate_metrical_details.py raw/vergil/vergil_georgics_1.json -o vergil_g1_metrical_details.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from metrical_numbering import WordResult, process_line as xml_process_line
from hypotactic_numbering import process_line as json_process_line


def _patch_prodelision(line_elem) -> None:
    """Detect prodelision and mark est with mf=PE.

    Prodelision occurs when a word with mf=SY (elision) is followed by
    'est'. In that case, est loses its initial vowel. We mark est with
    mf=PE and clear its scansion so metrical_numbering.process_line
    treats it as a lost word (number=0).
    """
    words = line_elem.find_all("word")
    for i, w in enumerate(words[:-1]):
        if w.get("mf") == "SY":
            next_w = words[i + 1]
            next_text = next_w.get_text(strip=True).lower().rstrip(".,;:!?")
            if next_text == "est":
                next_w["mf"] = "PE"
                next_w["sy"] = ""


def process_xml(xml_path: Path) -> list[list[WordResult | str]]:
    """Process an XML file and return per-line word data.

    Milestone markers are inserted as the string ``"*"`` at the position
    where a segment join occurs within a line.

    Args:
        xml_path: Path to a Pedecerto XML file.

    Returns:
        List of word result lists, one per hexameter line. Each list may
        contain ``"*"`` entries marking segment boundaries.
    """
    from bs4 import BeautifulSoup

    tree = BeautifulSoup(xml_path.read_text(encoding="utf-8"), "xml")
    lines: list[list[WordResult | str]] = []
    for line_elem in tree.find_all("line"):
        if line_elem.get("meter") not in ("H", None):
            continue
        _patch_prodelision(line_elem)

        # Track milestone positions relative to the word sequence
        milestone_after: set[int] = set()
        word_count = 0
        for child in line_elem.children:
            if child.name == "milestone":
                if word_count > 0:
                    milestone_after.add(word_count)
            elif child.name == "word":
                word_count += 1

        word_results = xml_process_line(line_elem)
        row: list[WordResult | str] = []
        for idx, w in enumerate(word_results, start=1):
            row.append(w)
            if idx in milestone_after:
                row.append("*")
        lines.append(row)
    return lines


def process_json(json_path: Path) -> list[list[WordResult | str]]:
    """Process a JSON file and return per-line word data.

    Args:
        json_path: Path to a hypotactic JSON file.

    Returns:
        List of word result lists, one per hexameter line.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    for line_dict in data.get("lines", []):
        if line_dict.get("metre") != "hexameter":
            continue
        word_results = json_process_line(line_dict)
        lines.append(word_results)
    return lines


def format_details(lines: list[list[WordResult | str]], title: str) -> str:
    """Format word data into a human-readable table.

    Segment boundaries within a line are shown as a row with ``*`` in the
    word column and empty columns for the scansion data.

    Args:
        lines: List of word result lists, one per hexameter line. Entries
            may be ``"*"`` strings marking segment boundaries.
        title: Title to display at the top of the table.

    Returns:
        Formatted text string with the scansion table.
    """
    out = []
    out.append("=" * 100)
    out.append(title)
    out.append("=" * 100)
    out.append("")

    for i, word_results in enumerate(lines, 1):
        if not word_results:
            continue

        out.append(f"Line {i}:")
        header = (
            f"  {'Word':<25} {'sy':<20} {'base':<14} "
            f"{'added':<16} {'final':<16} {'number':>8}"
        )
        out.append(header)
        out.append(f"  {'─'*25} {'─'*20} {'─'*14} {'─'*16} {'─'*16} {'─'*8}")

        for entry in word_results:
            if entry == "*":
                out.append(f"  {'*':<25} {'':20} {'':14} {'':16} {'':16} {'':>8}")
                continue

            w: WordResult = entry  # type: ignore[assignment]
            text = str(w["text"])
            sy_raw = str(w.get("sy_raw", ""))
            base = ",".join(w["syllables"]) if w["syllables"] else "—"
            added = ",".join(w["added"]) if w["added"] else "—"
            final = ",".join(w["final_syllables"]) if w["final_syllables"] else "—"
            num = int(w["number"])
            out.append(
                f"  {text:<25} {sy_raw:<20} {base:<14} "
                f"{added:<16} {final:<16} {num:>8}"
            )

        out.append("")

    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        nargs="+",
        help="Source XML or JSON files to process",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (default: {stem}_metrical_details.txt next to source)",
    )
    args = parser.parse_args()

    for src_str in args.sources:
        src_path = Path(src_str)
        if not src_path.exists():
            print(f"File not found: {src_path}", file=sys.stderr)
            continue

        suffix = src_path.suffix.lower()
        if suffix == ".xml":
            lines = process_xml(src_path)
        elif suffix == ".json":
            lines = process_json(src_path)
        else:
            print(f"Unknown format: {src_path} (expected .xml or .json)", file=sys.stderr)
            continue

        title = f"{src_path} — all hexameter lines"
        text = format_details(lines, title)

        if args.output and len(args.sources) == 1:
            out_path = Path(args.output)
        else:
            out_path = src_path.parent / f"{src_path.stem}_metrical_details.txt"

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"  {src_path.name} → {out_path} ({len(lines)} lines)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

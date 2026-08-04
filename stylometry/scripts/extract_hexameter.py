#!/usr/bin/env python3
"""Extract continuous hexameter stretches from Pedecerto XML files.

Reads raw XML files from raw/ausonius/ and raw/question/, finds stretches
of 10+ continuous hexameter lines (meter="H", pattern not "not scanned",
words have sy= attributes), and writes clean hexameter XML to
processed/ausonius_hexameter/ and processed/question_hexameter/.

Usage:
    python extract_hexameter.py [--min-stretch 10]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bs4 import BeautifulSoup

from xml_utils import clean_xml

BASE_DIR = Path(__file__).resolve().parent.parent

# Input → output pairs
SOURCES = [
    (BASE_DIR / "raw" / "ausonius", BASE_DIR / "processed" / "ausonius_hexameter"),
    (BASE_DIR / "raw" / "question", BASE_DIR / "processed" / "question_hexameter"),
]

# meter="H" is hexameter in Pedecerto's encoding
HEXAMETER_METER = "H"


def is_valid_hexameter(line_tag) -> bool:
    """Check if a line is valid hexameter.

    A line is valid if meter="H", pattern is not "not scanned", and at
    least one word has a sy attribute (is scanned).

    Args:
        line_tag: A BeautifulSoup <line> element.

    Returns:
        True if the line is a valid hexameter line.
    """
    if line_tag.get("meter") != "H":
        return False

    pattern = line_tag.get("pattern", "")
    if pattern == "not scanned":
        return False

    # Check that at least one word has a sy attribute (scanned)
    words = line_tag.find_all("word")
    if not words:
        return False
    has_sy = any(w.get("sy") for w in words)
    return has_sy


def is_verse_line(line) -> bool:
    """Check if an element is an actual verse line.

    Some Pedecerto XML files contain <line> elements that are structural
    markers (prose section headers, scene changes) rather than actual verse
    lines. These have no 'name' attribute and should be skipped.

    Args:
        line: A BeautifulSoup <line> element.

    Returns:
        True if the element has a 'name' attribute (is an actual verse).
    """
    return bool(line.get("name"))


def find_hexameter_stretches(lines: list, min_stretch: int = 10) -> list[list]:
    """Find continuous stretches of valid hexameter lines.

    A stretch is a run of consecutive hexameter lines (meter="H"). Lacunose
    lines (meter="H" but pattern="not scanned" or missing sy=) are allowed
    within a stretch but are stripped from the final output. Only stretches
    with >= min_stretch valid lines are kept.

    Args:
        lines: List of BeautifulSoup <line> elements.
        min_stretch: Minimum number of valid hexameter lines to keep a stretch.

    Returns:
        List of stretches, each a list of valid <line> elements.
    """
    stretches: list[list] = []
    current_raw: list = []

    for line in lines:
        if not is_verse_line(line):
            continue  # skip structural markers

        meter = line.get("meter", "")
        if meter == HEXAMETER_METER:
            # Hexameter line — keep the stretch alive (even if unscanned)
            current_raw.append(line)
        else:
            # Non-hexameter verse line — break the stretch
            valid = [ln for ln in current_raw if is_valid_hexameter(ln)]
            if len(valid) >= min_stretch:
                stretches.append(valid)
            current_raw = []

    # Finalise last stretch
    valid = [ln for ln in current_raw if is_valid_hexameter(ln)]
    if len(valid) >= min_stretch:
        stretches.append(valid)

    return stretches


def process_file(input_path: Path, min_stretch: int) -> tuple[int, int, int]:
    """Process a single XML file and count hexameter lines.

    Args:
        input_path: Path to the Pedecerto XML file.
        min_stretch: Minimum stretch length to count as eligible.

    Returns:
        Tuple of (total_lines, hex_lines, eligible_lines).
    """
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")
    lines = soup.find_all("line")

    # Find all valid hexameter lines
    all_hex = [ln for ln in lines if is_valid_hexameter(ln)]

    # Find stretches of continuous hexameter
    stretches = find_hexameter_stretches(lines, min_stretch)

    # Build output
    eligible_lines = []
    for stretch in stretches:
        eligible_lines.extend(stretch)

    return len(lines), len(all_hex), len(eligible_lines)


def extract_file(input_path: Path, output_path: Path, min_stretch: int) -> int:
    """Extract hexameter stretches from a single file.

    Args:
        input_path: Path to the source Pedecerto XML file.
        output_path: Path to write the extracted hexameter XML.
        min_stretch: Minimum continuous hexameter lines to keep.

    Returns:
        Number of hexameter lines written.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")
    lines = soup.find_all("line")

    stretches = find_hexameter_stretches(lines, min_stretch)

    # Build output: header + all eligible lines
    header = soup.find("head")
    output_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    output_lines.append("<document>")
    if header:
        output_lines.append(str(header))

    written = 0
    for stretch in stretches:
        for line in stretch:
            output_lines.append(str(line))
            written += 1

    output_lines.append("</document>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract continuous hexameter stretches")
    parser.add_argument("--min-stretch", type=int, default=10,
                        help="Minimum continuous hexameter lines (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be extracted without writing files")
    args = parser.parse_args()

    total_written = 0

    for input_dir, output_dir in SOURCES:
        if not input_dir.exists():
            continue

        output_dir.mkdir(parents=True, exist_ok=True)
        xml_files = sorted(input_dir.glob("*.xml"))
        if not xml_files:
            continue

        print(f"Scanning {len(xml_files)} XML files in {input_dir}...")
        print(f"Minimum stretch: {args.min_stretch} lines\n")

        eligible_files = []

        for xml_path in xml_files:
            total, hex_count, eligible = process_file(xml_path, args.min_stretch)
            if eligible > 0:
                eligible_files.append((xml_path, eligible))
                print(f"  {xml_path.name:<45} {total:>5} lines, {hex_count:>5} hex, {eligible:>5} eligible")

        print(f"\n{len(eligible_files)} files with eligible stretches (total {sum(e for _, e in eligible_files)} lines)")

        if args.dry_run:
            print("[dry run] No files written.\n")
            continue

        for xml_path, eligible in eligible_files:
            out_path = output_dir / xml_path.name
            written = extract_file(xml_path, out_path, args.min_stretch)
            total_written += written
            print(f"  → {out_path.name} ({written} lines)")

        print(f"\nDone: {total_written} lines written so far\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Filter hexameter lines from Ausonius XML files.

Reads XML files from ausonius_raw/ and extracts only lines with meter="H"
(hexameter). Lines that are "not scanned" (meter="" or meter="X") or contain
'*' in the text are skipped.

Only files listed in to_process.md are processed.

Output files are written to ausonius_hexameter/ with "_H" suffix.

Usage:
    python filter_hexameter.py
"""

from bs4 import BeautifulSoup
from pathlib import Path
import re
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(__file__).parent / "ausonius_raw"
OUTPUT_DIR = Path(__file__).parent / "ausonius_hexameter"
TO_PROCESS_FILE = Path(__file__).parent / "to_process.md"

# meter="H" is hexameter in Pedecerto's encoding
HEXAMETER_METER = "H"

# Meters that indicate "not scanned" lines
UNSCANNED_METERS = {"", "X"}


def line_is_unscanned(line_elem) -> bool:
    """Check if a line is 'not scanned' (empty/X meter or 'not scanned' pattern)."""
    meter = line_elem.get("meter", "")
    pattern = line_elem.get("pattern", "")
    return meter in UNSCANNED_METERS or pattern == "not scanned"


def clean_xml(content: str) -> str:
    """
    Fix common XML issues in Pedecerto files.

    Some files contain unescaped < and > characters in attribute values
    (e.g., division title attributes with <emph> tags).

    This function walks the file line by line, removing <division> opening
    and closing tags while keeping everything else (including <line> elements).
    Division opening tags are always on single lines (ending with ">).
    """
    output_lines = []

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip division opening and closing tags
        if stripped.startswith('<division') or stripped.startswith('</division'):
            continue

        output_lines.append(line)

    return '\n'.join(output_lines)


def line_has_asterisk(line_elem) -> bool:
    """Check if any word in the line contains an asterisk."""
    for word_elem in line_elem.find_all("word"):
        if "*" in word_elem.get_text():
            return True
    return False


def filter_file(input_path: Path, output_path: Path) -> tuple[int, int, int]:
    """
    Filter a single XML file to keep only hexameter lines.

    Skips lines that:
    - Are not scanned (meter="" or meter="X")
    - Contain '*' in any word text

    Returns (hexameter_lines, skipped_unscanned, skipped_asterisk).
    """
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Clean malformed XML before parsing
    content = clean_xml(content)

    soup = BeautifulSoup(content, "xml")

    # Find all <line> elements
    lines = soup.find_all("line")

    hex_lines = 0
    skipped_unscanned = 0
    skipped_asterisk = 0

    for line in lines:
        # Skip unscanned lines (empty/X meter or 'not scanned' pattern)
        if line_is_unscanned(line):
            skipped_unscanned += 1
            line.extract()
            continue

        # Skip lines with asterisks in text
        if line_has_asterisk(line):
            skipped_asterisk += 1
            line.extract()
            continue

        # Keep hexameter lines, remove others
        if line.get("meter", "") == HEXAMETER_METER:
            hex_lines += 1
        else:
            line.extract()

    if hex_lines > 0:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

    return hex_lines, skipped_unscanned, skipped_asterisk


def load_to_process() -> list[str]:
    """Load the list of files to process from to_process.md."""
    if not TO_PROCESS_FILE.exists():
        print(f"WARNING: {TO_PROCESS_FILE} not found. Processing all XML files.")
        return []

    with open(TO_PROCESS_FILE, "r", encoding="utf-8") as f:
        files = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    return files


def main():
    print(f"Input directory:  {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load list of files to process
    to_process = load_to_process()
    if to_process:
        print(f"Processing {len(to_process)} files from to_process.md:")
        for f in to_process:
            print(f"  - {f}")
    else:
        xml_files = sorted(INPUT_DIR.glob("*.xml"))
        to_process = [f.name for f in xml_files]
        print(f"\nNo to_process.md found. Processing all {len(to_process)} XML files.")

    print()

    kept = 0
    total_hex = 0
    total_skipped_unscanned = 0
    total_skipped_asterisk = 0

    for filename in to_process:
        input_path = INPUT_DIR / filename
        if not input_path.exists():
            print(f"  ✗ {filename} — file not found")
            continue

        output_name = input_path.stem + "_H.xml"
        output_path = OUTPUT_DIR / output_name

        hex_lines, skipped_unscanned, skipped_asterisk = filter_file(input_path, output_path)

        if hex_lines > 0:
            print(f"  ✓ {filename} → {output_name} ({hex_lines} hex lines, "
                  f"{skipped_unscanned} unscanned, {skipped_asterisk} asterisk)")
            kept += 1
            total_hex += hex_lines
            total_skipped_unscanned += skipped_unscanned
            total_skipped_asterisk += skipped_asterisk
        else:
            print(f"  ✗ {filename} — no hexameter lines after filtering")

    print(f"\nDone: {kept} files processed.")
    print(f"  Total hexameter lines: {total_hex}")
    print(f"  Skipped (unscanned): {total_skipped_unscanned}")
    print(f"  Skipped (asterisk): {total_skipped_asterisk}")

    if kept == 0:
        print("WARNING: No files with hexameter lines found!")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Analyze Ausonius XML files for hexameter content.

Reads XML files from ausonius_raw/ and reports:
- Total lines per file
- Meter distribution
- Continuous stretches of hexameter (meter="H") lines
- Files that are pure hexameter vs mixed meter vs non-hexameter

This helps identify which files to use for the Ausonius hexameter corpus.

Usage:
    python analyze_hexameter.py
"""

import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(__file__).parent / "ausonius_raw"

# meter="H" is hexameter in Pedecerto's encoding
HEXAMETER_METER = "H"


def clean_xml(content: str) -> str:
    """Fix common XML issues in Pedecerto files.

    Some files contain unescaped < and > characters in attribute values
    (e.g., division title attributes with <emph> tags).

    Args:
        content: Raw XML content string.

    Returns:
        Cleaned XML content with problematic characters escaped.
    """
    # Fix title attributes that contain <emph> tags
    content = re.sub(
        r'title="[^"]*<[^>]*>[^"]*"',
        lambda m: 'title="' + re.sub(r'<[^>]+>', '', m.group(0)[7:-1]).replace('"', "'") + '"',
        content
    )
    return content


def analyze_file(input_path: Path) -> dict:
    """Analyze a single XML file for hexameter content.

    Args:
        input_path: Path to the Pedecerto XML file.

    Returns:
        Dict with keys: filename, total_lines, meter_counts, hex_stretches,
        longest_hex_stretch, hex_line_numbers.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")

    lines = soup.find_all("line")
    total_lines = len(lines)

    meter_counts = Counter()
    hex_line_numbers = set()
    hex_stretches = []

    current_stretch_start = None
    current_stretch_len = 0

    for i, line_elem in enumerate(lines, 1):
        meter = line_elem.get("meter", "")
        meter_counts[meter] += 1

        if meter == HEXAMETER_METER:
            hex_line_numbers.add(i)
            if current_stretch_start is None:
                current_stretch_start = i
                current_stretch_len = 1
            else:
                current_stretch_len += 1
        else:
            if current_stretch_start is not None:
                hex_stretches.append((current_stretch_start, current_stretch_len))
                current_stretch_start = None
                current_stretch_len = 0

    # Close any open stretch at end of file
    if current_stretch_start is not None:
        hex_stretches.append((current_stretch_start, current_stretch_len))

    longest_stretch = max((s[1] for s in hex_stretches), default=0)

    return {
        "filename": input_path.name,
        "total_lines": total_lines,
        "meter_counts": meter_counts,
        "hex_stretches": hex_stretches,
        "longest_hex_stretch": longest_stretch,
        "hex_line_numbers": hex_line_numbers,
    }


def classify_file(analysis: dict) -> str:
    """Classify a file based on its hexameter content.

    Args:
        analysis: Dict from analyze_file with meter counts and stretch data.

    Returns:
        One of: "pure_hexameter", "predominant_hexameter", "mixed_hexameter",
        "minimal_hexameter", "no_hexameter", "elegiac_couplets".
    """
    total = analysis["total_lines"]
    hex_count = analysis["meter_counts"].get(HEXAMETER_METER, 0)

    if hex_count == 0:
        return "no_hexameter"

    hex_ratio = hex_count / total

    if hex_ratio == 1.0:
        return "pure_hexameter"

    # Check for elegiac couplet pattern (alternating hexameter and non-hex)
    # In elegiac couplets, hexameter lines are at odd positions (1, 3, 5, ...)
    # and non-hex lines at even positions (2, 4, 6, ...)
    if hex_count > 0 and total > 0:
        hex_lines = sorted(analysis["hex_line_numbers"])
        # Check if hexameter lines are at every other position
        expected_positions = list(range(1, total + 1, 2))
        if hex_lines == expected_positions[:len(hex_lines)]:
            return "elegiac_couplets"

    # Check for long continuous stretches
    longest = analysis["longest_hex_stretch"]
    if hex_ratio > 0.5 and longest >= 10:
        return "predominant_hexameter"

    if hex_ratio > 0.1:
        return "mixed_hexameter"

    return "minimal_hexameter"


def main() -> None:
    """Analyze all XML files and print a summary report to stdout."""
    print(f"Input directory: {INPUT_DIR}")

    xml_files = sorted(INPUT_DIR.glob("*.xml"))
    print(f"Found {len(xml_files)} XML files to analyze.\n")

    results = []
    for xml_file in xml_files:
        analysis = analyze_file(xml_file)
        category = classify_file(analysis)
        analysis["category"] = category
        results.append(analysis)

    # Print summary table
    print("=" * 120)
    print(f"{'File':<55} {'Total':>6} {'Hex':>6} {'%':>5} {'Longest':>8} {'Category':<25}")
    print("=" * 120)

    for r in sorted(results, key=lambda x: x["filename"]):
        hex_count = r["meter_counts"].get(HEXAMETER_METER, 0)
        hex_pct = f"{100 * hex_count / r['total_lines']:.0f}%" if r["total_lines"] > 0 else "N/A"
        print(f"{r['filename']:<55} {r['total_lines']:>6} {hex_count:>6} {hex_pct:>5} {r['longest_hex_stretch']:>8} {r['category']:<25}")

    print("\n" + "=" * 120)
    print("\nDetailed meter distributions:\n")

    for r in sorted(results, key=lambda x: x["filename"]):
        print(f"\n--- {r['filename']} ---")
        print(f"  Category: {r['category']}")
        print(f"  Total lines: {r['total_lines']}")
        print(f"  Hexameter lines: {r['meter_counts'].get(HEXAMETER_METER, 0)}")
        print(f"  Meter distribution: {dict(sorted(r['meter_counts'].items(), key=lambda x: -x[1]))}")
        print(f"  Continuous hexameter stretches: {len(r['hex_stretches'])}")
        if r['hex_stretches']:
            for start, length in r['hex_stretches']:
                end = start + length - 1
                print(f"    Lines {start}-{end}: {length} hexameter lines")

    # Summary by category
    print("\n" + "=" * 120)
    print("\nSummary by category:\n")
    by_category = Counter(r["category"] for r in results)
    for cat, count in sorted(by_category.items()):
        files = [r["filename"] for r in results if r["category"] == cat]
        print(f"  {cat} ({count} files):")
        for f in files:
            print(f"    - {f}")


if __name__ == "__main__":
    main()

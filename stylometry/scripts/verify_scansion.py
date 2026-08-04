#!/usr/bin/env python3
"""Verify hexameter scansion in generated cento XML files.

Checks that every hexameter line has valid foot structure:
  Foot 1-5: spondee (A+T) or dactyl (A+b+c)
  Foot 6:    always A+X

Each syllable is encoded as position+type (e.g. 1A, 2b, 3T, 6X).
A valid line has exactly 6 complete feet with no partial or missing feet.

Usage:
    python scripts/verify_scansion.py
    python scripts/verify_scansion.py --limit 5
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIRS = [
    BASE_DIR.parent / "data" / "generated-compact" / "exact",
    BASE_DIR.parent / "data" / "generated-compact" / "loose",
]

# Valid foot patterns: foot_num -> set of valid type sequences
VALID_FEET = {
    1: {("A", "T"), ("A", "b", "c")},
    2: {("A", "T"), ("A", "b", "c")},
    3: {("A", "T"), ("A", "b", "c")},
    4: {("A", "T"), ("A", "b", "c")},
    5: {("A", "T"), ("A", "b", "c")},
    6: {("A", "X"),},
}


def parse_sy(sy: str) -> list[tuple[int, str]]:
    """Parse a sy string into (foot_num, type) pairs.

    Args:
        sy: Pedecerto sy attribute string (e.g. "1A1b1c2A").

    Returns:
        List of (foot_number, syllable_type) tuples.
    """
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r'(\d)([A-Za-z])', sy)]


def validate_line(sy: str) -> list[str]:
    """Validate a complete line's scansion.

    Args:
        sy: Concatenated sy attributes from all words in the line.

    Returns:
        List of error messages (empty if valid).
    """
    if not sy:
        return ["empty scansion"]

    pairs = parse_sy(sy)
    if not pairs:
        return [f"no syllables found in '{sy}'"]

    # Group into feet
    feet: dict[int, list[str]] = {}
    for foot_num, syl_type in pairs:
        feet.setdefault(foot_num, []).append(syl_type)

    errors = []

    # Check all 6 feet present
    for f in range(1, 7):
        if f not in feet:
            errors.append(f"missing foot {f}")

    # Check each foot is valid
    for f, types in sorted(feet.items()):
        if f < 1 or f > 6:
            errors.append(f"invalid foot number {f}")
            continue
        tuple_types = tuple(types)
        valid = VALID_FEET.get(f, set())
        if tuple_types not in valid:
            errors.append(f"foot {f}: {tuple_types} not in {valid}")

    return errors


def verify_file(xml_path: Path) -> list[tuple[int, str, list[str]]]:
    """Verify all hexameter lines in a file.

    Args:
        xml_path: Path to the generated cento XML file.

    Returns:
        List of (line_num, full_sy, errors) tuples for lines with issues.
    """
    tree = BeautifulSoup(xml_path.read_text(), "xml")
    issues = []

    for line_idx, line in enumerate(tree.find_all("line"), 1):
        if line.get("meter") not in ("H", None):
            continue

        # Build complete line scansion from all words
        full_sy = ""
        for w in line.find_all("word"):
            sy = w.get("sy", "")
            if sy:
                full_sy += sy

        errors = validate_line(full_sy)
        if errors:
            issues.append((line_idx, full_sy, errors))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="Process only the first N files (0 = all)")
    args = parser.parse_args()

    source_files = []
    for source_dir in SOURCE_DIRS:
        source_files.extend(sorted(source_dir.glob("cento_*.xml")))

    if args.limit > 0:
        source_files = source_files[: args.limit]

    if not source_files:
        print(f"No XML files found in {SOURCE_DIRS}", file=sys.stderr)
        return 1

    print(f"Verifying scansion in {len(source_files)} files...")

    total_issues = 0
    files_with_issues = 0

    for xml_path in source_files:
        issues = verify_file(xml_path)
        if issues:
            files_with_issues += 1
            total_issues += len(issues)
            print(f"\n{xml_path.name}: {len(issues)} issues")
            for line_num, sy, errors in issues[:5]:
                print(f"  Line {line_num}: sy='{sy}'")
                for e in errors:
                    print(f"    {e}")
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more")

    print(f"\n{'='*60}")
    print(f"Files checked: {len(source_files)}")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total issues: {total_issues}")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

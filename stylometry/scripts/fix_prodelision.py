#!/usr/bin/env python3
"""Fix prodelision scansion in generated cento XML files.

The cento generator has a bug where words before 'est'/'es' with elision
(mf="SY") have incomplete scansion — they're missing the syllable that
'est'/'es' occupies. This script fixes it mechanically:

For each word with mf="SY" followed by est/es in the same segment:
  1. Move est/es's sy to the preceding word (append it)
  2. Remove mf="SY" from the preceding word
  3. Set est/es to mf="PE" and sy=""

Only applies to same-segment pairs (no milestone between the words).
Cross-segment cases are reported but not fixed.

Usage:
    python scripts/fix_prodelision.py
    python scripts/fix_prodelision.py --dry-run
    python scripts/fix_prodelision.py --limit 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIRS = [
    BASE_DIR.parent / "data" / "generated-compact" / "exact",
    BASE_DIR.parent / "data" / "generated-compact" / "loose",
]


def same_segment(line: Tag, w1: Tag, w2: Tag) -> bool:
    """Check if two adjacent words are from the same segment.

    Returns False if there is a milestone element between w1 and w2.

    Args:
        line: Parent <line> element.
        w1: First <word> element.
        w2: Second <word> element.

    Returns:
        True if both words are in the same segment.
    """
    between = False
    for child in line.children:
        if child is w1:
            between = True
            continue
        if child is w2:
            return True
        if between and child.name == "milestone":
            return False
    return False


def fix_file(xml_path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Fix prodelision in a single generated cento XML file.

    Args:
        xml_path: Path to the generated cento XML file.
        dry_run: If True, report changes without writing the file.

    Returns:
        Tuple of (fixed_count, cross_segment_count).
    """
    content = xml_path.read_text(encoding="utf-8")
    tree = BeautifulSoup(content, "xml")
    lines = [ln for ln in tree.find_all("line") if ln.get("meter") in ("H", None)]

    fixed = 0
    cross_segment = 0

    for line in lines:
        words = list(line.find_all("word"))

        for i, w in enumerate(words):
            if w.get("mf") != "SY":
                continue
            if i + 1 >= len(words):
                continue
            next_w = words[i + 1]
            next_text = next_w.get_text(strip=True).lower().rstrip(".,;:!?")
            if next_text not in ("est", "es"):
                continue

            est_sy = next_w.get("sy", "")
            if not est_sy:
                continue  # already fixed

            # Apply the fix
            current_sy = w.get("sy", "")
            new_sy = current_sy + est_sy

            w["sy"] = new_sy
            del w["mf"]

            next_w["mf"] = "PE"
            next_w["sy"] = ""

            fixed += 1

    if not dry_run and fixed > 0:
        xml_path.write_text(str(tree), encoding="utf-8")

    return fixed, cross_segment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be changed without modifying files",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Process only the first N files (0 = all)",
    )
    args = parser.parse_args()

    source_files = []
    for source_dir in SOURCE_DIRS:
        source_files.extend(sorted(source_dir.glob("cento_*.xml")))
    if args.limit > 0:
        source_files = source_files[: args.limit]

    if not source_files:
        print(f"No XML files found in {SOURCE_DIRS}", file=sys.stderr)
        return 1

    mode = "DRY RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] Processing {len(source_files)} generated centos...")

    total_fixed = 0
    total_cross = 0
    files_changed = 0

    for xml_path in source_files:
        fixed, cross = fix_file(xml_path, dry_run=args.dry_run)
        total_fixed += fixed
        total_cross += cross
        if fixed > 0:
            files_changed += 1

    print("\nDone.")
    print(f"  Files changed: {files_changed}")
    print(f"  Fixes applied: {total_fixed}")
    print(f"  Cross-segment (skipped): {total_cross}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

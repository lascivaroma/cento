#!/usr/bin/env python3
"""Check for missing elision markers at segment joins in generated cento XML.

Scans generated cento XML files for cases where a word ending with a vowel
or 'm' is followed by a word starting with a vowel or 'h' across a segment
boundary, but no mf="SY" elision marker is present.

Words starting with consonantal 'u' (v in classical Latin) or consonantal 'i'
(j in classical Latin) are filtered out using a vocabulary file derived from
Vergil's hypotactic scansion data.

This script reports only — it does not modify any files.

Usage:
    python scripts/check_missing_elision.py [--limit N]
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup, Tag

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIRS = [
    BASE_DIR.parent / "data" / "generated-compact" / "exact",
    BASE_DIR.parent / "data" / "generated-compact" / "loose",
]
VJ_VOCAB_PATH = BASE_DIR / "vergil_vj_vocab.txt"


def strip_diacritics(text: str) -> str:
    """Remove diacritics/macrons from text.

    Args:
        text: Input text.

    Returns:
        Lowercase text with diacritics removed.
    """
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def clean_word(text: str) -> str:
    """Strip punctuation and diacritics from a word.

    Args:
        text: Raw word text.

    Returns:
        Lowercase alphabetic characters only.
    """
    return re.sub(r"[^a-z]", "", strip_diacritics(text))


def load_vj_vocab(path: Path) -> set[str]:
    """Load the v/j vocabulary file.

    Args:
        path: Path to the vocabulary file (one word per line).

    Returns:
        Set of lowercase v/j words.
    """
    if not path.exists():
        print(f"Warning: v/j vocab not found at {path}", file=sys.stderr)
        return set()
    return {line.strip().lower() for line in path.read_text().splitlines() if line.strip()}


def is_consonantal_v(word: str, vj_vocab: set[str]) -> bool:
    """Check if a word starting with 'u' is consonantal (v in classical Latin).

    The vocab file has v-words with all non-initial v normalized to u.
    So just change the first 'u' to 'v' and look up.

    Args:
        word: Cleaned lowercase word.
        vj_vocab: Set of normalized v/j words from Vergil's hypotactic data.

    Returns:
        True if 'v' + word[1:] matches the vocabulary.
    """
    if not word or word[0] != "u":
        return False
    return ("v" + word[1:]) in vj_vocab


def is_consonantal_j(word: str, vj_vocab: set[str]) -> bool:
    """Check if a word starting with 'i' is consonantal (j in classical Latin).

    The vocab file has j-words with all non-initial j normalized to i.
    So just change the first 'i' to 'j' and look up.

    Args:
        word: Cleaned lowercase word.
        vj_vocab: Set of normalized v/j words from Vergil's hypotactic data.

    Returns:
        True if 'j' + word[1:] matches the vocabulary.
    """
    if not word or word[0] != "i":
        return False
    return ("j" + word[1:]) in vj_vocab


def is_vowel_ending(word: str) -> bool:
    """Check if a word ends with a vowel or 'm'.

    Args:
        word: Cleaned lowercase word.

    Returns:
        True if the word ends with a, e, i, o, u, or m.
    """
    return bool(word) and word[-1] in "aeioum"


def is_vowel_start(word: str) -> bool:
    """Check if a word starts with a vowel or 'h'.

    Args:
        word: Cleaned lowercase word.

    Returns:
        True if the word starts with a, e, i, o, u, or h.
    """
    return bool(word) and word[0] in "aeiouh"


def find_cross_segment_pairs(line: Tag) -> list[tuple[Tag, Tag]]:
    """Find word pairs separated by a milestone within a line.

    Args:
        line: A BeautifulSoup <line> element.

    Returns:
        List of (prev_word, next_word) tuples where a milestone appears
        between them.
    """
    pairs: list[tuple[Tag, Tag]] = []
    children = list(line.children)
    for i, child in enumerate(children):
        if child.name != "milestone":
            continue
        # Find the word before this milestone
        prev_word = None
        for j in range(i - 1, -1, -1):
            if children[j].name == "word":
                prev_word = children[j]
                break
        # Find the word after this milestone
        next_word = None
        for j in range(i + 1, len(children)):
            if children[j].name == "word":
                next_word = children[j]
                break
        if prev_word is not None and next_word is not None:
            pairs.append((prev_word, next_word))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="Process only the first N files (0 = all)")
    parser.add_argument("--file", type=str, default=None,
                        help="Process a single specific file instead of scanning directories")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Write report to this file instead of stdout")
    args = parser.parse_args()

    vj_vocab = load_vj_vocab(VJ_VOCAB_PATH)
    print(f"Loaded {len(vj_vocab)} v/j words from {VJ_VOCAB_PATH.name}")

    source_files: list[Path] = []
    if args.file:
        source_files = [Path(args.file)]
    else:
        for source_dir in SOURCE_DIRS:
            source_files.extend(sorted(source_dir.glob("cento_*.xml")))
        if args.limit > 0:
            source_files = source_files[: args.limit]

    out = open(args.output, "w") if args.output else sys.stdout

    if not source_files:
        print(f"No XML files found in {SOURCE_DIRS}", file=sys.stderr)
        return 1

    print(f"Checking {len(source_files)} files for missing elision at segment joins...", file=out)

    total_missing = 0
    total_consonantal_v = 0
    total_consonantal_j = 0
    files_with_issues = 0

    for xml_path in source_files:
        tree = BeautifulSoup(xml_path.read_text(), "xml")
        file_missing = 0

        for line in tree.find_all("line"):
            for prev_w, next_w in find_cross_segment_pairs(line):
                if prev_w.get("mf") == "SY":
                    continue  # elision already marked

                prev_text = clean_word(prev_w.text)
                next_text = clean_word(next_w.text)

                if not prev_text or not next_text:
                    continue
                if not is_vowel_ending(prev_text):
                    continue
                if not is_vowel_start(next_text):
                    continue

                # Filter consonantal v/u
                if is_consonantal_v(next_text, vj_vocab):
                    total_consonantal_v += 1
                    continue

                # Filter consonantal j/i
                if is_consonantal_j(next_text, vj_vocab):
                    total_consonantal_j += 1
                    continue

                total_missing += 1
                file_missing += 1
                if total_missing <= 30:
                    print(f"  {xml_path.name} line {line.get('n', '?')}: "
                          f"{prev_w.text.strip()} + {next_w.text.strip()}", file=out)
                    print(f"  <line n=\"{line.get('n', '')}\">", file=out)
                    for child in line.children:
                        if child.name:
                            print(f"    {child}", file=out)
                    print("  </line>", file=out)
                    print(f"{'='*15}", file=out)

        if file_missing > 0:
            files_with_issues += 1

    print(f"\n{'='*60}", file=out)
    print(f"Files checked: {len(source_files)}", file=out)
    print(f"Files with missing elision: {files_with_issues}", file=out)
    print(f"Total missing elision: {total_missing}", file=out)
    print(f"Filtered as consonantal u/v: {total_consonantal_v}", file=out)
    print(f"Filtered as consonantal i/j: {total_consonantal_j}", file=out)

    if args.output:
        out.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

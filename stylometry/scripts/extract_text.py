#!/usr/bin/env python3
"""Extract plain text from Pedecerto XML and hypotactic JSON files.

Reads source files and writes one .txt file per work (one verse per line,
space-separated words).  Output is compatible with the latin-masking
pipeline (process.py).

Sources:
  - Pedecerto XML  (processed/ausonius_hexameter/*.xml, processed/question_hexameter/*.xml)
  - Hypotactic JSON (raw/vergil/*.json, raw/aeneid/*.json, raw/background/*.json)

Outputs:
  - processed/ausonius/*.txt   (from XML, excluding cento)
  - processed/question/*.txt   (cento only)
  - processed/vergil/*.txt     (Vergil Georgics from JSON)
  - processed/aeneid/*.txt     (Vergil Aeneid from JSON)
  - processed/background/*.txt (from JSON)

Usage:
    python scripts/extract_text.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# Add scripts dir to path for corpus_utils
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from corpus_utils import line_text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# XML sources (from extract_hexameter.py)
AUSONIUS_XML = BASE_DIR / "processed" / "ausonius_hexameter"
QUESTION_XML = BASE_DIR / "processed" / "question_hexameter"

# JSON sources (raw fixtures)
VERGIL_INPUT = BASE_DIR / "raw" / "vergil"
AENEID_INPUT = BASE_DIR / "raw" / "aeneid"
BACKGROUND_INPUT = BASE_DIR / "raw" / "background"

# Output directories
AUSONIUS_OUT = BASE_DIR / "processed" / "ausonius"
VERGIL_OUT = BASE_DIR / "processed" / "vergil"
AENEID_OUT = BASE_DIR / "processed" / "aeneid"
BACKGROUND_OUT = BASE_DIR / "processed" / "background"
QUESTION_OUT = BASE_DIR / "processed" / "question"


# ---------------------------------------------------------------------------
# XML extraction (Pedecerto)
# ---------------------------------------------------------------------------

def extract_text_from_xml(input_path: Path) -> list[str]:
    """Extract text lines from a Pedecerto XML file.

    Each <line> element becomes one text line, with words joined by spaces.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, "xml")
    lines: list[str] = []

    for line_elem in soup.find_all("line"):
        words: list[str] = []
        for word_elem in line_elem.find_all("word"):
            text = word_elem.get_text(strip=True)
            if text:
                words.append(text)
        line_text_str = " ".join(words)
        if line_text_str:
            lines.append(line_text_str)

    return lines


# ---------------------------------------------------------------------------
# JSON extraction (Hypotactic)
# ---------------------------------------------------------------------------

def extract_text_from_json(input_path: Path) -> list[str]:
    """Extract text lines from a hypotactic JSON file.

    Each line object becomes one text line, using corpus_utils.line_text().
    """
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines_data = data.get("lines", [])
    result: list[str] = []

    for line_dict in lines_data:
        text = line_text(line_dict)
        if text.strip():
            result.append(text)

    return result


# ---------------------------------------------------------------------------
# Generic processor
# ---------------------------------------------------------------------------

def process_directory(
    input_dir: Path,
    output_dir: Path,
    extractor,
    glob_pattern: str,
    label: str,
    prefix: str = "",
) -> tuple[int, int]:
    """Process all files in a directory.

    Args:
        prefix: Optional prefix to add to output filenames (e.g. 'ausonius_').

    Returns (files_written, total_lines).
    """
    input_files = sorted(input_dir.glob(glob_pattern))
    if not input_files:
        print(f"  No {glob_pattern} files in {input_dir}")
        return 0, 0

    output_dir.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    total_words = 0
    for input_path in input_files:
        stem = input_path.stem
        output_name = prefix + stem + ".txt"
        output_path = output_dir / output_name

        text_lines = extractor(input_path)
        total_lines += len(text_lines)
        file_words = sum(len(line.split()) for line in text_lines)
        total_words += file_words

        with open(output_path, "w", encoding="utf-8") as f:
            for line in text_lines:
                f.write(line + "\n")

    print(f"  {label}: {len(input_files)} files, {total_lines} lines, {total_words} words")
    return len(input_files), total_lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Extracting plain text from source files...")
    print()

    total_files = 0
    total_lines = 0

    # Ausonius XML → processed/ausonius/
    print(f"XML source:  {AUSONIUS_XML}")
    print(f"XML output:  {AUSONIUS_OUT}")
    n_files, n_lines = process_directory(
        AUSONIUS_XML, AUSONIUS_OUT, extract_text_from_xml, "*.xml", "Ausonius XML",
        prefix="ausonius_",
    )
    total_files += n_files
    total_lines += n_lines
    print()

    # Question XML → processed/question/
    print(f"XML source:  {QUESTION_XML}")
    print(f"XML output:  {QUESTION_OUT}")
    n_files, n_lines = process_directory(
        QUESTION_XML, QUESTION_OUT, extract_text_from_xml, "*.xml", "Question XML"
    )
    total_files += n_files
    total_lines += n_lines
    print()

    # Vergil Georgics JSON → processed/vergil/
    print(f"JSON source: {VERGIL_INPUT}")
    print(f"JSON output: {VERGIL_OUT}")
    n_files, n_lines = process_directory(
        VERGIL_INPUT, VERGIL_OUT, extract_text_from_json, "*.json", "Vergil JSON"
    )
    total_files += n_files
    total_lines += n_lines
    print()

    # Vergil Aeneid JSON → processed/aeneid/
    print(f"JSON source: {AENEID_INPUT}")
    print(f"JSON output: {AENEID_OUT}")
    n_files, n_lines = process_directory(
        AENEID_INPUT, AENEID_OUT, extract_text_from_json, "*.json", "Aeneid JSON"
    )
    total_files += n_files
    total_lines += n_lines
    print()

    # Background JSON → processed/background/
    print(f"JSON source: {BACKGROUND_INPUT}")
    print(f"JSON output: {BACKGROUND_OUT}")
    n_files, n_lines = process_directory(
        BACKGROUND_INPUT, BACKGROUND_OUT, extract_text_from_json, "*.json", "Background JSON"
    )
    total_files += n_files
    total_lines += n_lines
    print()

    print(f"Total: {total_files} files, {total_lines} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

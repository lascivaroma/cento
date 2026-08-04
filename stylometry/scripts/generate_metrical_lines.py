#!/usr/bin/env python3
"""Generate line-based metrical-numbered sentence files.

Reads source files (Pedecerto XML or hypotactic JSON) and produces one
output sentence per hexameter line, with each word replaced by its
prime-encoded metrical position number.  Every sentence ends with <EOL>.

Output files are named {work}.mapped_lines.txt and written to
metrical_model_lines/{corpus}/.

Usage:
    PYTHONPATH=scripts python scripts/generate_metrical_lines.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup

from metrical_numbering import _norm, process_line as xml_process_line
from hypotactic_numbering import process_line as json_process_line
from xml_utils import clean_xml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# Source directories
XML_DIR = BASE_DIR / "processed" / "ausonius_hexameter"
QUESTION_XML = BASE_DIR / "processed" / "question_hexameter"
VERGIL_RAW = BASE_DIR / "raw" / "vergil"
AENEID_RAW = BASE_DIR / "raw" / "aeneid"
BACKGROUND_RAW = BASE_DIR / "raw" / "background"

# Output directories
OUT_AUSONIUS = BASE_DIR / "metrical_model_lines" / "ausonius"
OUT_VERGIL = BASE_DIR / "metrical_model_lines" / "vergil"
OUT_AENEID = BASE_DIR / "metrical_model_lines" / "aeneid"
OUT_BACKGROUND = BASE_DIR / "metrical_model_lines" / "background"
OUT_QUESTION = BASE_DIR / "metrical_model_lines" / "question"


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _norm_token(tok: str) -> str:
    """Normalise a token for alignment: lowercase, strip diacritics and punctuation."""
    nfd = unicodedata.normalize("NFD", tok)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    alpha = re.sub(r"[^a-zA-Z]", "", stripped)
    return _norm(alpha)


# ---------------------------------------------------------------------------
# Source loading (reused from generate_metrical.py)
# ---------------------------------------------------------------------------

def load_xml_lines(xml_path: Path) -> list:
    """Load hexameter lines from a Pedecerto XML file.

    Args:
        xml_path: Path to the Pedecerto XML file.

    Returns:
        List of hexameter <line> BeautifulSoup elements.
    """
    with open(xml_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")
    return [el for el in soup.find_all("line") if el.get("meter") == "H"]


def xml_line_to_numbers(line_tag) -> list[str]:
    """Encode one XML line as a list of metrical number strings.

    Args:
        line_tag: A BeautifulSoup <line> element.

    Returns:
        List of metrical number strings for the line.
    """
    tokens: list[str] = []
    for w in xml_process_line(line_tag):
        tokens.append(str(int(w["number"])))
    return tokens


def load_json_lines(json_path: Path) -> list[dict]:
    """Load hexameter lines from a hypotactic JSON file.

    Args:
        json_path: Path to the hypotactic JSON file.

    Returns:
        List of line dicts from the JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("lines", [])


def json_line_to_numbers(line_dict: dict) -> list[str]:
    """Encode one JSON line as a list of metrical number strings.

    Args:
        line_dict: A line dict from hypotactic JSON.

    Returns:
        List of metrical number strings for the line.
    """
    tokens: list[str] = []
    for w in json_process_line(line_dict):
        tokens.append(str(int(w["number"])))
    return tokens


# ---------------------------------------------------------------------------
# Line-level processing
# ---------------------------------------------------------------------------

def process_lines_to_file(
    line_numbers: list[list[str]],
    output_path: Path,
) -> int:
    """Write one sentence per hexameter line, each ending with <EOL>.

    Args:
        line_numbers: Per-line lists of metrical number strings.
        output_path: Path to write the output file.

    Returns:
        Number of sentences written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for numbers in line_numbers:
            if not numbers:
                continue
            line = " ".join(numbers) + " <EOL>"
            f.write(line + "\n")
    return len(line_numbers)


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_xml_corpus(
    source_dir: Path,
    source_glob: str,
    output_dir: Path,
    label: str,
    skip: set[str] | None = None,
    out_prefix: str = "",
) -> None:
    """Process XML sources and write mapped-lines files.

    Args:
        source_dir: Directory containing source XML files.
        source_glob: Glob pattern for source files.
        output_dir: Directory to write output files.
        label: Human-readable label for progress messages.
        skip: Set of file stems to skip.
        out_prefix: Prefix for output filenames.
    """
    if skip is None:
        skip = set()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_files = sorted(
        p for p in source_dir.glob(source_glob) if p.stem not in skip
    )
    if not source_files:
        print(f"  No {source_glob} files in {source_dir}")
        return

    total_files = 0
    total_sentences = 0

    for src_path in source_files:
        stem = src_path.stem
        raw_lines = load_xml_lines(src_path)
        line_numbers = [xml_line_to_numbers(line) for line in raw_lines]

        out_path = output_dir / f"{out_prefix}{stem}.mapped_lines.txt"
        count = process_lines_to_file(line_numbers, out_path)
        total_files += 1
        total_sentences += count

    print(f"  {label}: {total_files} files, {total_sentences} sentences")


def process_json_corpus(
    source_dir: Path,
    source_glob: str,
    output_dir: Path,
    label: str,
) -> None:
    """Process JSON sources and write mapped-lines files.

    Args:
        source_dir: Directory containing source JSON files.
        source_glob: Glob pattern for source files.
        output_dir: Directory to write output files.
        label: Human-readable label for progress messages.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    source_files = sorted(source_dir.glob(source_glob))
    if not source_files:
        print(f"  No {source_glob} files in {source_dir}")
        return

    total_files = 0
    total_sentences = 0

    for src_path in source_files:
        stem = src_path.stem
        raw_lines = load_json_lines(src_path)
        line_numbers = [json_line_to_numbers(line) for line in raw_lines]

        out_path = output_dir / f"{stem}.mapped_lines.txt"
        count = process_lines_to_file(line_numbers, out_path)
        total_files += 1
        total_sentences += count

    print(f"  {label}: {total_files} files, {total_sentences} sentences")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Generating line-based metrical-numbered sentences...")
    print()

    # Ausonius (exclude cento)
    process_xml_corpus(
        source_dir=XML_DIR, source_glob="*.xml",
        output_dir=OUT_AUSONIUS, label="Ausonius",
        skip={"cento_nuptialis"},
        out_prefix="ausonius_",
    )

    # Vergil Georgics
    process_json_corpus(
        source_dir=VERGIL_RAW, source_glob="vergil_georgics_*.json",
        output_dir=OUT_VERGIL, label="Vergil",
    )

    # Aeneid
    process_json_corpus(
        source_dir=AENEID_RAW, source_glob="*.json",
        output_dir=OUT_AENEID, label="Aeneid",
    )

    # Background
    process_json_corpus(
        source_dir=BACKGROUND_RAW, source_glob="*.json",
        output_dir=OUT_BACKGROUND, label="Background",
    )

    # Question (cento)
    cento_xml = QUESTION_XML / "cento_nuptialis.xml"
    if cento_xml.exists():
        OUT_QUESTION.mkdir(parents=True, exist_ok=True)
        raw_lines = load_xml_lines(cento_xml)
        line_numbers = [xml_line_to_numbers(line) for line in raw_lines]
        out_path = OUT_QUESTION / "cento_nuptialis.mapped_lines.txt"
        count = process_lines_to_file(line_numbers, out_path)
        print(f"  Question: 1 file, {count} sentences")
    else:
        print(f"  Question: cento XML not found at {cento_xml}")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

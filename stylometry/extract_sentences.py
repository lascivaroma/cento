#!/usr/bin/env python3
"""
Extract text from Ausonius hexameter XML files.

Reads filtered hexameter XML files from ausonius_hexameter/ and extracts
the text content, writing one file per work as plain text.

Each <line> element in the XML becomes one line of text, with words joined
by spaces. This format is compatible with the latin-masking pipeline
(see Liber-Regum/Lexical analysis/latin_masking_pipeline.ipynb).

Output files are written to ausonius_hexameter_txt/ with .txt extension.

Usage:
    python extract_sentences.py
"""

from bs4 import BeautifulSoup
from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(__file__).parent / "ausonius_hexameter"
OUTPUT_DIR = Path(__file__).parent / "ausonius_hexameter_txt"


def extract_text_from_xml(input_path: Path) -> list[str]:
    """
    Extract text lines from a Pedecerto XML file.

    Each <line> element becomes one text line, with words joined by spaces.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, "xml")

    lines = []
    for line_elem in soup.find_all("line"):
        words = []
        for word_elem in line_elem.find_all("word"):
            text = word_elem.get_text(strip=True)
            if text:
                words.append(text)
        line_text = " ".join(words)
        if line_text:
            lines.append(line_text)

    return lines


def main():
    print(f"Input directory:  {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(INPUT_DIR.glob("*_H.xml"))
    print(f"\nFound {len(xml_files)} XML files to process.\n")

    total_lines = 0
    total_words = 0
    for input_path in xml_files:
        output_name = input_path.stem.replace("_H", "") + ".txt"
        output_path = OUTPUT_DIR / output_name

        lines = extract_text_from_xml(input_path)
        total_lines += len(lines)

        # Count words
        file_words = sum(len(line.split()) for line in lines)
        total_words += file_words

        with open(output_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

        print(f"  ✓ {input_path.name} → {output_name} ({len(lines)} lines, {file_words} words)")

    print(f"\nDone: {len(xml_files)} files processed.")
    print(f"  Total lines: {total_lines}")
    print(f"  Total words: {total_words}")

    if len(xml_files) == 0:
        print("WARNING: No XML files found in input directory!")
        sys.exit(1)


if __name__ == "__main__":
    main()

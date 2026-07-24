#!/usr/bin/env python3
"""Generate metrical-numbered sentence files.

Reads source files (Pedecerto XML or hypotactic JSON) and the corresponding
_sentences.txt files produced by latin-masking stage 1, then outputs
metrical-numbered sentences where each word is replaced by its prime-encoded
metrical position number.

Inputs:
  - Source files: processed/ausonius_hexameter/*.xml, raw/vergil/*.json,
    raw/background/*.json
  - Sentence files: lexical_model/{ausonius,vergil,aeneid,background}/*_sentences.txt
  - Question sentence file: processed/question/cento_nuptialis_sentences.txt

Outputs:
  - metrical_model/{ausonius,vergil,aeneid,background,question}/*_sentences.metrical.txt

Usage:
    python scripts/generate_metrical.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

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

# Sentence file directories (output of latin-masking stage 1 in processed/)
AUSONIUS_SENT = BASE_DIR / "processed" / "ausonius"
VERGIL_SENT = BASE_DIR / "processed" / "vergil"
AENEID_SENT = BASE_DIR / "processed" / "aeneid"
BACKGROUND_SENT = BASE_DIR / "processed" / "background"
QUESTION_SENT = BASE_DIR / "processed" / "question"

# Output directories
OUT_AUSONIUS = BASE_DIR / "metrical_model" / "ausonius"
OUT_VERGIL = BASE_DIR / "metrical_model" / "vergil"
OUT_AENEID = BASE_DIR / "metrical_model" / "aeneid"
OUT_BACKGROUND = BASE_DIR / "metrical_model" / "background"
OUT_QUESTION = BASE_DIR / "metrical_model" / "question"


# ---------------------------------------------------------------------------
# Shared alignment logic
# ---------------------------------------------------------------------------

def build_word_index(
    texts: list[str], numbers: list[int]
) -> tuple[list[str], list[int]]:
    """Return parallel lists of normalised texts and their metrical numbers."""
    return texts, numbers


def build_permutation(
    source_texts: list[str],
    source_numbers: list[int],
    sent_words: list[str],
) -> list[int]:
    """FIFO permutation: map each sentence word to the next matching source position.

    Returns a list of source indices (one per sentence word).  -1 = no match.
    """
    index_map: dict[str, list[int]] = defaultdict(list)
    for i, w in enumerate(source_texts):
        index_map[w].append(i)
    for val in index_map:
        index_map[val].reverse()  # so pop() takes from front

    permutation: list[int] = []
    for sw in sent_words:
        if index_map.get(sw):
            permutation.append(index_map[sw].pop())
        else:
            permutation.append(-1)
    return permutation


def numbered_sentences_from_flat(
    source_texts: list[str],
    source_numbers: list[int],
    sentences_raw: list[str],
) -> list[str]:
    """Build numbered sentences from flat source data and sentence strings.

    Returns one string per sentence with <EOL> and <EOS> tokens preserved.
    """
    # Flatten sentence words, tracking <EOL>/<EOS> positions
    flat_words: list[str] = []
    eol_after: set[int] = set()

    for sent in sentences_raw:
        for tok in sent.split():
            if tok == "<EOL>":
                if flat_words:
                    eol_after.add(len(flat_words) - 1)
            else:
                w = _norm(re.sub(r"[^a-zA-Z]", "", tok))
                if w:
                    flat_words.append(w)

    # Build permutation
    permutation = build_permutation(source_texts, source_numbers, flat_words)

    # Report mismatches
    mismatches = sum(1 for p in permutation if p < 0)
    if mismatches:
        print(f"    WARNING: {mismatches}/{len(permutation)} words unmatched")

    # Build flat output
    flat_parts: list[str] = []
    for i, src_pos in enumerate(permutation):
        if src_pos >= 0:
            flat_parts.append(str(source_numbers[src_pos]))
        else:
            flat_parts.append("0")
        if i in eol_after:
            flat_parts.append("<EOL>")

    # Split into per-sentence strings at sentence boundaries.
    # Sentence boundaries are where the original sentence ended — we detect
    # them by replaying the sentence tokens and counting consumed words.
    result: list[str] = []
    current: list[str] = []
    word_idx = 0
    for sent in sentences_raw:
        for tok in sent.split():
            if tok == "<EOL>":
                if current:
                    current.append("<EOL>")
            else:
                w = _norm(re.sub(r"[^a-zA-Z]", "", tok))
                if w:
                    if word_idx < len(flat_parts):
                        # Find this word's number in flat_parts
                        # We need to walk through flat_parts matching word_idx
                        pass
                    word_idx += 1
        # Mark sentence end
        if current:
            current.append("<EOS>")
            result.append(" ".join(current))
            current = []

    # Simpler approach: rebuild from flat_parts using word count per sentence
    result = []
    current = []
    flat_idx = 0
    for sent in sentences_raw:
        word_count = sum(1 for tok in sent.split() if tok != "<EOL>" and _norm(re.sub(r"[^a-zA-Z]", "", tok)))
        for _ in range(word_count):
            if flat_idx < len(flat_parts):
                current.append(flat_parts[flat_idx])
                flat_idx += 1
        # Add <EOL> tokens that appeared in this sentence
        for tok in sent.split():
            if tok == "<EOL>" and current:
                current.append("<EOL>")
        current.append("<EOS>")
        result.append(" ".join(current))
        current = []

    if current:
        result.append(" ".join(current))

    return result


# ---------------------------------------------------------------------------
# XML source (Pedecerto)
# ---------------------------------------------------------------------------

def load_xml_lines(xml_path: Path) -> list:
    """Load hexameter lines from a Pedecerto XML file."""
    with open(xml_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")
    return [el for el in soup.find_all("line") if el.get("meter") == "H"]


def xml_to_flat(xml_lines: list) -> tuple[list[str], list[int]]:
    """Build flat (normalised_text, number) lists from XML lines."""
    texts: list[str] = []
    numbers: list[int] = []
    for line_tag in xml_lines:
        for w in xml_process_line(line_tag):
            texts.append(_norm(str(w["text"])))
            numbers.append(int(w["number"]))
    return texts, numbers


# ---------------------------------------------------------------------------
# JSON source (Hypotactic)
# ---------------------------------------------------------------------------

def load_json_lines(json_path: Path) -> list[dict]:
    """Load hexameter lines from a hypotactic JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("lines", [])


def json_to_flat(json_lines: list[dict]) -> tuple[list[str], list[int]]:
    """Build flat (normalised_text, number) lists from JSON lines."""
    texts: list[str] = []
    numbers: list[int] = []
    for line_dict in json_lines:
        for w in json_process_line(line_dict):
            texts.append(_norm(str(w["text"])))
            numbers.append(int(w["number"]))
    return texts, numbers


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_corpus(
    source_dir: Path,
    source_glob: str,
    source_loader,
    source_flattener,
    sentence_dir: Path,
    sentence_suffix: str,
    output_dir: Path,
    label: str,
    skip: set[str] | None = None,
) -> None:
    """Process one corpus: align source data with sentences, write metrical output.

    Args:
        skip: Optional set of file stems to exclude.
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
    total_mismatches = 0

    for src_path in source_files:
        stem = src_path.stem
        # Find matching sentence file
        sent_path = sentence_dir / f"{stem}{sentence_suffix}"
        if not sent_path.exists():
            print(f"    SKIP {stem}: no sentence file at {sent_path}")
            continue

        # Load source data
        raw_lines = source_loader(src_path)
        src_texts, src_numbers = source_flattener(raw_lines)

        # Load sentences
        with open(sent_path, "r", encoding="utf-8") as f:
            sentences = [line.strip() for line in f if line.strip()]

        # Generate numbered sentences
        numbered = numbered_sentences_from_flat(src_texts, src_numbers, sentences)

        # Count mismatches
        mismatches = sum(
            1 for s in numbered
            for tok in s.split()
            if tok not in ("<EOL>", "<EOS>") and tok == "0"
        )
        total_mismatches += mismatches

        # Write output
        out_path = output_dir / f"{stem}_sentences.metrical.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            for line in numbered:
                f.write(line + "\n")

        total_files += 1
        total_sentences += len(numbered)

    print(f"  {label}: {total_files} files, {total_sentences} sentences, {total_mismatches} unmatched words")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Generating metrical-numbered sentences...")
    print()

    # Ausonius: XML source + processed sentences (exclude cento)
    print(f"XML source:    {XML_DIR}")
    print(f"Sentences:     {AUSONIUS_SENT}")
    print(f"Output:        {OUT_AUSONIUS}")
    process_corpus(
        source_dir=XML_DIR,
        source_glob="*.xml",
        source_loader=load_xml_lines,
        source_flattener=xml_to_flat,
        sentence_dir=AUSONIUS_SENT,
        sentence_suffix="_sentences.txt",
        output_dir=OUT_AUSONIUS,
        label="Ausonius",
        skip={"cento_nuptialis"},
    )
    print()

    # Vergil Georgics: JSON source + processed sentences
    print(f"JSON source:   {VERGIL_RAW}")
    print(f"Sentences:     {VERGIL_SENT}")
    print(f"Output:        {OUT_VERGIL}")
    process_corpus(
        source_dir=VERGIL_RAW,
        source_glob="vergil_georgics_*.json",
        source_loader=load_json_lines,
        source_flattener=json_to_flat,
        sentence_dir=VERGIL_SENT,
        sentence_suffix="_sentences.txt",
        output_dir=OUT_VERGIL,
        label="Vergil",
    )
    print()

    # Vergil Aeneid: JSON source + processed sentences
    print(f"JSON source:   {AENEID_RAW}")
    print(f"Sentences:     {AENEID_SENT}")
    print(f"Output:        {OUT_AENEID}")
    process_corpus(
        source_dir=AENEID_RAW,
        source_glob="*.json",
        source_loader=load_json_lines,
        source_flattener=json_to_flat,
        sentence_dir=AENEID_SENT,
        sentence_suffix="_sentences.txt",
        output_dir=OUT_AENEID,
        label="Aeneid",
    )
    print()

    # Background: JSON source + processed sentences
    print(f"JSON source:   {BACKGROUND_RAW}")
    print(f"Sentences:     {BACKGROUND_SENT}")
    print(f"Output:        {OUT_BACKGROUND}")
    process_corpus(
        source_dir=BACKGROUND_RAW,
        source_glob="*.json",
        source_loader=load_json_lines,
        source_flattener=json_to_flat,
        sentence_dir=BACKGROUND_SENT,
        sentence_suffix="_sentences.txt",
        output_dir=OUT_BACKGROUND,
        label="Background",
    )
    print()

    # Question: XML source (cento_nuptialis) + processed sentences
    print(f"XML source:    {QUESTION_XML / 'cento_nuptialis.xml'}")
    print(f"Sentences:     {QUESTION_SENT}")
    print(f"Output:        {OUT_QUESTION}")
    cento_xml = QUESTION_XML / "cento_nuptialis.xml"
    cento_sent = QUESTION_SENT / "cento_nuptialis_sentences.txt"
    if cento_xml.exists() and cento_sent.exists():
        OUT_QUESTION.mkdir(parents=True, exist_ok=True)
        raw_lines = load_xml_lines(cento_xml)
        src_texts, src_numbers = xml_to_flat(raw_lines)
        with open(cento_sent, "r", encoding="utf-8") as f:
            sentences = [line.strip() for line in f if line.strip()]
        numbered = numbered_sentences_from_flat(src_texts, src_numbers, sentences)
        mismatches = sum(
            1 for s in numbered
            for tok in s.split()
            if tok not in ("<EOL>", "<EOS>") and tok == "0"
        )
        out_path = OUT_QUESTION / "cento_nuptialis_sentences.metrical.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            for line in numbered:
                f.write(line + "\n")
        print(f"  Question: 1 file, {len(numbered)} sentences, {mismatches} unmatched words")
    else:
        print(f"    SKIP: missing {cento_xml} or {cento_sent}")
    print()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

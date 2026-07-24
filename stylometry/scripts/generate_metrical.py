#!/usr/bin/env python3
"""Generate metrical-numbered sentence files.

Reads source files (Pedecerto XML or hypotactic JSON) and the corresponding
_sentences.txt files, then outputs metrical-numbered sentences where each
word is replaced by its prime-encoded metrical position number.

The output has the same sentence count and same token count per sentence
as the input _sentences.txt files.

Usage:
    python scripts/generate_metrical.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
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

# Sentence file directories (from latin-masking stage 1)
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
# Normalisation
# ---------------------------------------------------------------------------

def _norm_token(tok: str) -> str:
    """Normalise a token for alignment: lowercase, strip diacritics and punctuation."""
    nfd = unicodedata.normalize("NFD", tok)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    alpha = re.sub(r"[^a-zA-Z]", "", stripped)
    return _norm(alpha)


# ---------------------------------------------------------------------------
# Source loading
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
            texts.append(_norm_token(str(w["text"])))
            numbers.append(int(w["number"]))
    return texts, numbers


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
            texts.append(_norm_token(str(w["text"])))
            numbers.append(int(w["number"]))
    return texts, numbers


# ---------------------------------------------------------------------------
# Alignment and output
# ---------------------------------------------------------------------------

def build_numbered_sentences(
    source_texts: list[str],
    source_numbers: list[int],
    sentences_raw: list[str],
) -> tuple[list[str], int]:
    """Align source words to sentence words and produce numbered output.

    The output has the same sentence count and same token count per sentence
    as sentences_raw. Each word is replaced by its metrical number, <EOL>
    and <EOS> tokens are preserved in place.

    Returns (numbered_sentences, mismatch_count).
    """
    # Build lookup: normalised source word → list of metrical numbers (FIFO)
    src_lookup: dict[str, list[int]] = defaultdict(list)
    for text, num in zip(source_texts, source_numbers):
        src_lookup[text].append(num)
    for k in src_lookup:
        src_lookup[k].reverse()

    # Flatten sentence words (excluding <EOL>) for alignment
    flat_words: list[str] = []
    for sent in sentences_raw:
        for tok in sent.split():
            if tok != "<EOL>":
                norm = _norm_token(tok)
                if norm:
                    flat_words.append(norm)

    # Align: FIFO match
    numbers: list[int] = []
    mismatch_count = 0
    for sw in flat_words:
        if src_lookup.get(sw):
            numbers.append(src_lookup[sw].pop())
        else:
            numbers.append(0)
            mismatch_count += 1

    if mismatch_count:
        print(f"    WARNING: {mismatch_count}/{len(numbers)} words unmatched")

    # Build output: same structure as sentences_raw, with numbers replacing words
    # Skip pipe markers (|) — these are not words
    result: list[str] = []
    current: list[str] = []
    word_idx = 0
    for sent in sentences_raw:
        for tok in sent.split():
            if tok == "<EOL>":
                current.append("<EOL>")
            elif tok == "|":
                continue  # skip pipe markers
            else:
                norm = _norm_token(tok)
                if norm:
                    if word_idx < len(numbers):
                        current.append(str(numbers[word_idx]))
                        word_idx += 1
                    else:
                        current.append("0")
                else:
                    current.append("0")
        current.append("<EOS>")
        result.append(" ".join(current))
        current = []

    if current:
        result.append(" ".join(current))

    return result, mismatch_count


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
    """Process one corpus."""
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
        sent_path = sentence_dir / f"{stem}{sentence_suffix}"
        if not sent_path.exists():
            print(f"    SKIP {stem}: no sentence file at {sent_path}")
            continue

        raw_lines = source_loader(src_path)
        src_texts, src_numbers = source_flattener(raw_lines)

        with open(sent_path, "r", encoding="utf-8") as f:
            sentences = [line.strip() for line in f if line.strip()]

        numbered, mismatches = build_numbered_sentences(
            src_texts, src_numbers, sentences
        )
        total_mismatches += mismatches

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

    # Ausonius (exclude cento)
    process_corpus(
        source_dir=XML_DIR, source_glob="*.xml",
        source_loader=load_xml_lines, source_flattener=xml_to_flat,
        sentence_dir=AUSONIUS_SENT, sentence_suffix="_sentences.txt",
        output_dir=OUT_AUSONIUS, label="Ausonius",
        skip={"cento_nuptialis"},
    )

    # Vergil Georgics
    process_corpus(
        source_dir=VERGIL_RAW, source_glob="vergil_georgics_*.json",
        source_loader=load_json_lines, source_flattener=json_to_flat,
        sentence_dir=VERGIL_SENT, sentence_suffix="_sentences.txt",
        output_dir=OUT_VERGIL, label="Vergil",
    )

    # Aeneid
    process_corpus(
        source_dir=AENEID_RAW, source_glob="*.json",
        source_loader=load_json_lines, source_flattener=json_to_flat,
        sentence_dir=AENEID_SENT, sentence_suffix="_sentences.txt",
        output_dir=OUT_AENEID, label="Aeneid",
    )

    # Background
    process_corpus(
        source_dir=BACKGROUND_RAW, source_glob="*.json",
        source_loader=load_json_lines, source_flattener=json_to_flat,
        sentence_dir=BACKGROUND_SENT, sentence_suffix="_sentences.txt",
        output_dir=OUT_BACKGROUND, label="Background",
    )

    # Question (cento)
    cento_xml = QUESTION_XML / "cento_nuptialis.xml"
    cento_sent = QUESTION_SENT / "cento_nuptialis_sentences.txt"
    if cento_xml.exists() and cento_sent.exists():
        OUT_QUESTION.mkdir(parents=True, exist_ok=True)
        raw_lines = load_xml_lines(cento_xml)
        src_texts, src_numbers = xml_to_flat(raw_lines)
        with open(cento_sent, "r", encoding="utf-8") as f:
            sentences = [line.strip() for line in f if line.strip()]
        numbered, mismatches = build_numbered_sentences(
            src_texts, src_numbers, sentences
        )
        out_path = OUT_QUESTION / "cento_nuptialis_sentences.metrical.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            for line in numbered:
                f.write(line + "\n")
        print(f"  Question: 1 file, {len(numbered)} sentences, {mismatches} unmatched words")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

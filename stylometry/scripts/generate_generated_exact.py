#!/usr/bin/env python3
"""Convert generated cento XML to all stylometry formats.

Processes XML files from data/generated-compact/exact/ and produces:
- Plain text with pipe markers from <milestone> tags
- Sentence-split text (la_senter) with <EOL>/<EOS> markers
- Que-split text (latin_masking.clitics)
- POS-masked text using Pedecerto POS tags + mapping file
- Sentence-based metrical numbers
- Line-based metrical numbers

Parentheses are stripped from the text before sentence splitting to avoid
unmatched-paren errors in la_senter.

Usage:
    PYTHONPATH=scripts python scripts/generate_generated_exact.py
    PYTHONPATH=scripts python scripts/generate_generated_exact.py --limit 1
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from metrical_numbering import _norm, process_line as xml_process_line

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

SOURCE_DIR = BASE_DIR.parent / "data" / "generated-compact" / "exact"
POS_MAPPING_PATH = BASE_DIR / "pos_mapping.tsv"
ADVERBS_PATH = BASE_DIR / "scripts" / "common_adverbs.txt"

OUT_PROCESSED = BASE_DIR / "processed" / "generated_exact"
OUT_METRICAL_LINES = BASE_DIR / "metrical_model_lines" / "generated_exact"
OUT_METRICAL_SENT = BASE_DIR / "metrical_model" / "generated_exact"
OUT_LEXICAL = BASE_DIR / "lexical_model" / "generated_exact"


# ---------------------------------------------------------------------------
# POS mapping
# ---------------------------------------------------------------------------

def load_pos_mapping(path: Path) -> Dict[str, Tuple[str, bool]]:
    """Load the Pedecerto to UD POS mapping file.

    Returns dict: pedecerto_pos -> (ud_pos, should_mask).
    """
    mapping: Dict[str, Tuple[str, bool]] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            ped_pos, ud_pos, mask_flag = row[0], row[1], row[2].strip().lower()
            mapping[ped_pos] = (ud_pos, mask_flag == "y")
    return mapping


def load_common_adverbs(path: Path) -> set[str]:
    """Load common adverbs that should NOT be masked.

    Format: one adverb per line, tab-separated (word, count).
    """
    adverbs: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            word = line.split("\t")[0].strip()
            if word:
                adverbs.add(_norm(word))
    return adverbs


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
# XML extraction
# ---------------------------------------------------------------------------

def _patch_prodelision(line_elem) -> None:
    """Detect prodelision and mark est with mf=PE.

    Prodelision occurs when a word with mf=SY (elision) is followed by
    'est'. In that case, est loses its initial vowel. We mark est with
    mf=PE and clear its scansion so metrical_numbering.process_line
    treats it as a lost word (number=0).

    This catches ~98% of prodelision cases.
    """
    words = line_elem.find_all("word")
    for i, w in enumerate(words[:-1]):
        if w.get("mf") == "SY":
            next_w = words[i + 1]
            next_text = next_w.get_text(strip=True).lower().rstrip(".,;:!?")
            if next_text == "est":
                next_w["mf"] = "PE"
                next_w["sy"] = ""


def extract_xml_data(xml_path: Path) -> Tuple[
    List[str],
    List[List[str]],
    List[List[Tuple[str, str]]],
]:
    """Extract plain text, metrical numbers, and POS data from XML.

    Returns three parallel lists indexed by hexameter line number:
    - plain_lines: text with | pipe markers from <milestone> tags
    - line_numbers: per-line lists of metrical number strings
    - line_words: per-line lists of (normalised_text, pos_tag) tuples

    Prodelision is auto-detected: when a word with mf=SY is followed by
    'est', the est is marked with mf=PE before metrical processing.
    """
    tree = BeautifulSoup(xml_path.read_text(encoding="utf-8"), "xml")

    plain_lines: List[str] = []
    line_numbers: List[List[str]] = []
    line_words: List[List[Tuple[str, str]]] = []

    for line_elem in tree.find_all("line"):
        if line_elem.get("meter") != "H":
            continue

        # Plain text with pipe markers from milestones
        # Only insert | markers mid-line (skip the leading milestone)
        parts: List[str] = []
        for child in line_elem.children:
            if child.name == "milestone":
                if parts:
                    parts.append("|")
            elif child.name == "word":
                text = child.get_text(strip=True)
                if text:
                    parts.append(text)
        plain_lines.append(" ".join(parts))

        # Patch prodelision before metrical processing
        _patch_prodelision(line_elem)

        # Metrical numbers via existing metrical_numbering module
        word_results = xml_process_line(line_elem)
        line_numbers.append([str(int(w["number"])) for w in word_results])

        # POS tags from XML word elements (in same order as metrical numbers)
        words_for_line: List[Tuple[str, str]] = []
        for child in line_elem.children:
            if child.name == "word":
                text = child.get_text(strip=True)
                pos = child.get("pos", "")
                norm = _norm_token(text)
                if norm:
                    words_for_line.append((norm, pos))
        line_words.append(words_for_line)

    return plain_lines, line_numbers, line_words


def strip_parens(text: str) -> str:
    """Remove all parentheses and brackets from text."""
    return re.sub(r"[()[\]{}]", "", text)


# ---------------------------------------------------------------------------
# Sentence splitting and que-splitting
# ---------------------------------------------------------------------------

def sentence_split(text: str) -> List[str]:
    """Split text into sentences using latin_masking."""
    from latin_masking.sentences import split_sentences
    return split_sentences(text, preserve_eol=True)


def que_split_sentences(sentences: List[str], common_adverbs: set[str]) -> List[str]:
    """Apply -que clitic splitting to each sentence.

    Respects both the default blacklist and common_adverbs to protect
    known adverbs from being split.
    """
    from latin_masking.clitics import split_que_blacklist
    result: List[str] = []
    for sent in sentences:
        split_text, _ = split_que_blacklist(sent, common_adverbs=common_adverbs)
        result.append(split_text)
    return result


# ---------------------------------------------------------------------------
# FIFO alignment
# ---------------------------------------------------------------------------

def build_fifo_lookup(norms: List[str], values: list) -> Dict[str, list]:
    """Build a FIFO lookup from normalised words to their values."""
    lookup: Dict[str, list] = defaultdict(list)
    for norm, val in zip(norms, values):
        lookup[norm].append(val)
    for k in lookup:
        lookup[k].reverse()
    return lookup


# ---------------------------------------------------------------------------
# POS masking
# ---------------------------------------------------------------------------

def mask_sentences_fifo(
    quesplit_sentences: List[str],
    all_xml_norms: List[str],
    all_xml_pos: List[str],
    pos_mapping: Dict[str, Tuple[str, bool]],
    common_adverbs: set[str],
) -> List[str]:
    """Apply POS masking using FIFO alignment to XML POS tags.

    ADV words in common_adverbs are kept as lowercased words (not masked).
    """
    pos_lookup = build_fifo_lookup(all_xml_norms, all_xml_pos)

    masked_sentences: List[str] = []
    mismatches = 0

    for sent in quesplit_sentences:
        tokens = sent.split()
        masked: List[str] = []

        for tok in tokens:
            if tok in ("<EOL>", "<EOS>"):
                masked.append(tok)
                continue
            if tok == "|":
                continue
            if tok == "-que":
                masked.append("-que")
                continue

            norm = _norm_token(tok)
            if not norm:
                continue

            ped_pos = None
            if pos_lookup.get(norm):
                ped_pos = pos_lookup[norm].pop()
            elif pos_lookup.get(norm + "que"):
                # que-split: "clarum" matches XML "clarumque"
                ped_pos = pos_lookup[norm + "que"].pop()

            if ped_pos is not None:
                ud_pos, should_mask = pos_mapping.get(ped_pos, (ped_pos, False))
                # ADV: keep common adverbs as words, mask rare ones
                if ped_pos in ("ADV", "ADVneg") and norm in common_adverbs:
                    masked.append(tok.lower())
                elif should_mask:
                    masked.append(ud_pos)
                else:
                    masked.append(tok.lower())
            else:
                mismatches += 1
                masked.append(tok.lower())

        masked_sentences.append(" ".join(masked))

    if mismatches:
        print(f"    WARNING: {mismatches} POS alignment mismatches")

    return masked_sentences


# ---------------------------------------------------------------------------
# Sentence-based metrical numbering
# ---------------------------------------------------------------------------

def metrical_sentences_fifo(
    quesplit_sentences: List[str],
    all_xml_norms: List[str],
    all_xml_numbers: List[str],
) -> Tuple[List[str], int]:
    """Build sentence-based metrical output using FIFO alignment."""
    num_lookup = build_fifo_lookup(all_xml_norms, all_xml_numbers)

    result: List[str] = []
    mismatches = 0

    for sent in quesplit_sentences:
        tokens = sent.split()
        nums: List[str] = []

        for tok in tokens:
            if tok in ("<EOL>", "<EOS>"):
                nums.append(tok)
                continue
            if tok == "|":
                continue
            if tok == "-que":
                continue

            norm = _norm_token(tok)
            if not norm:
                continue

            num = None
            if num_lookup.get(norm):
                num = num_lookup[norm].pop()
            elif num_lookup.get(norm + "que"):
                # que-split: "clarum" matches XML "clarumque"
                num = num_lookup[norm + "que"].pop()

            if num is not None:
                nums.append(num)
            else:
                nums.append("0")
                mismatches += 1

        result.append(" ".join(nums))

    return result, mismatches


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_lines(path: Path, lines: List[str]) -> None:
    """Write lines to a file, one per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def write_metrical_lines(path: Path, line_numbers: List[List[str]]) -> None:
    """Write one metrical sentence per hexameter line, ending with <EOL>."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for nums in line_numbers:
            if nums:
                f.write(" ".join(nums) + " <EOL>\n")


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_one_file(
    xml_path: Path,
    pos_mapping: Dict[str, Tuple[str, bool]],
    common_adverbs: set[str],
    verbose: bool = True,
) -> None:
    """Process a single generated cento XML file."""
    stem = xml_path.stem

    if verbose:
        print(f"  Processing {stem}...")

    # 1. Extract data from XML
    plain_lines, line_numbers, line_words = extract_xml_data(xml_path)

    # 2. Write plain text
    write_lines(OUT_PROCESSED / f"{stem}.txt", plain_lines)

    # 3. Strip parentheses for sentence splitting
    text_no_parens = strip_parens("\n".join(plain_lines))

    # 4. Sentence splitting
    sentences = sentence_split(text_no_parens)
    write_lines(OUT_PROCESSED / f"{stem}_sentences.txt", sentences)

    # 5. Que-splitting
    quesplit = que_split_sentences(sentences, common_adverbs)
    write_lines(OUT_PROCESSED / f"{stem}_sentences.quesplit.txt", quesplit)

    # 6. Build flat XML word lists for FIFO alignment
    all_xml_norms: List[str] = []
    all_xml_pos: List[str] = []
    all_xml_numbers: List[str] = []
    for line_idx, words in enumerate(line_words):
        for norm, pos in words:
            all_xml_norms.append(norm)
            all_xml_pos.append(pos)
        for num in line_numbers[line_idx]:
            all_xml_numbers.append(num)

    # 7. POS masking
    masked = mask_sentences_fifo(quesplit, all_xml_norms, all_xml_pos, pos_mapping, common_adverbs)
    write_lines(OUT_PROCESSED / f"{stem}_sentences.quesplit.masked.txt", masked)
    write_lines(OUT_LEXICAL / f"{stem}_sentences.quesplit.masked.txt", masked)

    # 8. Line-based metrical numbers
    write_metrical_lines(OUT_METRICAL_LINES / f"{stem}.mapped_lines.txt", line_numbers)

    # 9. Sentence-based metrical numbers
    sent_met, met_mismatches = metrical_sentences_fifo(
        quesplit, all_xml_norms, all_xml_numbers
    )
    write_lines(OUT_METRICAL_SENT / f"{stem}_sentences.metrical.txt", sent_met)

    if verbose:
        print(f"    {len(plain_lines)} lines, {len(sentences)} sentences, {met_mismatches} metrical mismatches")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Process only the first N files (0 = all)",
    )
    args = parser.parse_args()

    # Load POS mapping
    if not POS_MAPPING_PATH.exists():
        print(f"POS mapping file not found: {POS_MAPPING_PATH}", file=sys.stderr)
        return 1
    pos_mapping = load_pos_mapping(POS_MAPPING_PATH)
    print(f"Loaded {len(pos_mapping)} POS mappings from {POS_MAPPING_PATH.name}")

    # Load common adverbs (kept as words, not masked)
    if not ADVERBS_PATH.exists():
        print(f"Common adverbs file not found: {ADVERBS_PATH}", file=sys.stderr)
        return 1
    common_adverbs = load_common_adverbs(ADVERBS_PATH)
    print(f"Loaded {len(common_adverbs)} common adverbs from {ADVERBS_PATH.name}")

    # Find source files
    source_files = sorted(SOURCE_DIR.glob("cento_*.xml"))
    if args.limit > 0:
        source_files = source_files[: args.limit]

    if not source_files:
        print(f"No XML files found in {SOURCE_DIR}", file=sys.stderr)
        return 1

    print(f"Processing {len(source_files)} generated centos from {SOURCE_DIR.name}/")
    print()

    for d in [OUT_PROCESSED, OUT_METRICAL_LINES, OUT_METRICAL_SENT, OUT_LEXICAL]:
        d.mkdir(parents=True, exist_ok=True)

    for xml_path in source_files:
        process_one_file(xml_path, pos_mapping, common_adverbs)

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

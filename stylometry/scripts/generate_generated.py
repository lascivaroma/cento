#!/usr/bin/env python3
"""Convert generated cento XML to all stylometry formats.

Processes XML files from a generated cento directory and produces:
- Plain text with pipe markers from <milestone> tags
- Sentence-split text (la_senter) with <EOL>/<EOS> markers
- Que-split text (latin_masking.clitics)
- POS-masked text using Pedecerto POS tags + mapping file
- Sentence-based metrical numbers
- Line-based metrical numbers

Parentheses are stripped from the text before sentence splitting to avoid
unmatched-paren errors in la_senter.

The output directory name is derived from the source directory name. For
example, --source-dir ../data/generated-compact/exact writes to
processed/generated_exact/, while --source-dir ../data/generated-compact/loose
writes to processed/generated_loose/.

Usage:
    PYTHONPATH=scripts python scripts/generate_generated.py --source-dir ../data/generated-compact/exact
    PYTHONPATH=scripts python scripts/generate_generated.py --source-dir ../data/generated-compact/loose --limit 1
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

from metrical_numbering import _norm, process_line as xml_process_line

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

POS_MAPPING_PATH = BASE_DIR / "pos_mapping.tsv"
ADVERBS_PATH = BASE_DIR / "scripts" / "common_adverbs.txt"
UNMASKED_VOCAB_PATH = BASE_DIR / "scripts" / "unmasked_vocab.txt"


# ---------------------------------------------------------------------------
# POS mapping
# ---------------------------------------------------------------------------

def load_pos_mapping(path: Path) -> Dict[str, str]:
    """Load the Pedecerto to UD POS mapping file.

    Args:
        path: Path to the TSV mapping file.

    Returns:
        Dict mapping pedecerto_pos to ud_pos.
    """
    mapping: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            mapping[row[0]] = row[1]
    return mapping


def load_common_adverbs(path: Path) -> set[str]:
    """Load common adverbs that should NOT be masked.

    Args:
        path: Path to the adverbs file (tab-separated word + count).

    Returns:
        Set of normalised adverb forms.
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


def load_unmasked_vocab(path: Path) -> set[str]:
    """Load the reference unmasked vocabulary from disk.

    This file is pre-extracted from Vergil, Ausonius, and background
    masked files.  Words in this set stay as lowercased words in the
    generated centos; everything else gets a POS tag.

    Args:
        path: Path to unmasked_vocab.txt (one word per line).

    Returns:
        Set of lowercased word forms.
    """
    words: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w:
                words.add(w)
    return words


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
    """Detect prodelision and mark est/es with mf=PE.

    Two detection passes:

    1. Classic: a word with mf="SY" is followed by 'est' → mark est as PE.
    2. Blank scansion: est or es with empty sy and no mf → mark as PE.

    In both cases est/es gets mf="PE" and cleared scansion so
    metrical_numbering.process_line treats it as a lost word (number=0).
    """
    words = line_elem.find_all("word")

    # Pass 1: classic prodelision (preceding word has mf="SY")
    for i, w in enumerate(words[:-1]):
        if w.get("mf") == "SY":
            next_w = words[i + 1]
            next_text = next_w.get_text(strip=True).lower().rstrip(".,;:!?")
            if next_text == "est":
                next_w["mf"] = "PE"
                next_w["sy"] = ""

    # Pass 2: est/es with blank scansion and no mf — likely prodelided
    for w in words:
        if w.get("mf"):
            continue  # already has an mf flag
        sy = str(w.get("sy", "") or "")
        if sy:
            continue  # has scansion, not lost
        text = w.get_text(strip=True).lower().rstrip(".,;:!?")
        if text in ("est", "es"):
            w["mf"] = "PE"


def extract_xml_data(xml_path: Path) -> Tuple[
    List[str],
    List[List[str]],
    List[List[Tuple[str, str]]],
]:
    """Extract plain text, metrical numbers, and POS data from XML.

    Prodelision is auto-detected: when a word with mf=SY is followed by
    'est', the est is marked with mf=PE before metrical processing.

    Args:
        xml_path: Path to the generated cento XML file.

    Returns:
        Tuple of (plain_lines, line_numbers, line_words) where:
        - plain_lines: text with | pipe markers from <milestone> tags
        - line_numbers: per-line lists of metrical number strings
        - line_words: per-line lists of (normalised_text, pos_tag) tuples
    """
    tree = BeautifulSoup(xml_path.read_text(encoding="utf-8"), "xml")

    plain_lines: List[str] = []
    line_numbers: List[List[str]] = []
    line_words: List[List[Tuple[str, str]]] = []

    for line_elem in tree.find_all("line"):
        if line_elem.get("meter") not in ("H", None):
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
                text = text.lstrip("-")  # strip leading hyphen (XML artefact)
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
    """Remove all parentheses and brackets from text.

    Args:
        text: Input text.

    Returns:
        Text with all parentheses and brackets removed.
    """
    return re.sub(r"[()[\]{}]", "", text)


# ---------------------------------------------------------------------------
# Sentence splitting and que-splitting
# ---------------------------------------------------------------------------

def sentence_split(text: str) -> List[str]:
    """Split text into sentences using latin_masking.

    Args:
        text: Plain text to split.

    Returns:
        List of sentence strings with <EOL>/<EOS> markers.
    """
    from latin_masking.sentences import split_sentences
    return split_sentences(text, preserve_eol=True)


def que_split_sentences(sentences: List[str], common_adverbs: set[str]) -> List[str]:
    """Apply -que clitic splitting to each sentence.

    Respects both the default blacklist and common_adverbs to protect
    known adverbs from being split.

    Args:
        sentences: List of sentence strings to process.
        common_adverbs: Set of adverbs to protect from splitting.

    Returns:
        List of sentences with -que clitics split.
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
    """Build a FIFO lookup from normalised words to their values.

    Args:
        norms: List of normalised word forms.
        values: Parallel list of values to look up.

    Returns:
        Dict mapping normalised words to FIFO queues of values.
    """
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
    pos_mapping: Dict[str, str],
    common_adverbs: set[str],
    vergil_unmasked: set[str],
) -> List[str]:
    """Apply POS masking using FIFO alignment to XML POS tags.

    Words in the reference unmasked vocabulary stay as lowercased words.
    Everything else gets its UDPipe POS tag from pos_mapping.

    Args:
        quesplit_sentences: Que-split sentence strings.
        all_xml_norms: Flat list of normalised XML word forms.
        all_xml_pos: Parallel list of Pedecerto POS tags.
        pos_mapping: Mapping from Pedecerto POS to UDPipe POS tag.
        common_adverbs: (unused, kept for backwards compat)
        vergil_unmasked: Set of normalised words to keep unmasked.

    Returns:
        List of POS-masked sentence strings.
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
            if tok.startswith("-que"):
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
                # Strip CON clitic tag (e.g. "ADJqua CON" → "ADJqua")
                ped_pos = ped_pos.split()[0] if " " in ped_pos else ped_pos
                # Words in the reference unmasked vocab stay as words;
                # everything else gets its UDPipe POS tag.
                if norm in vergil_unmasked:
                    masked.append(norm)
                else:
                    ud_pos = pos_mapping.get(ped_pos, ped_pos)
                    masked.append(ud_pos)
            else:
                mismatches += 1
                masked.append(norm)

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
    """Build sentence-based metrical output using FIFO alignment.

    Args:
        quesplit_sentences: Que-split sentence strings.
        all_xml_norms: Flat list of normalised XML word forms.
        all_xml_numbers: Parallel list of metrical number strings.

    Returns:
        Tuple of (numbered_sentences, mismatch_count).
    """
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
            if tok.startswith("-que"):
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
    """Write lines to a file, one per line.

    Args:
        path: Output file path.
        lines: List of strings to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def append_eos(lines: List[str]) -> List[str]:
    """Append <EOS> to each line.

    Args:
        lines: List of sentence strings.

    Returns:
        New list with <EOS> appended to each line.
    """
    return [f"{line} <EOS>" if line and not line.endswith("<EOS>") else line for line in lines]


def write_metrical_lines(path: Path, line_numbers: List[List[str]]) -> None:
    """Write one metrical sentence per hexameter line, ending with <EOL>.

    Args:
        path: Output file path.
        line_numbers: Per-line lists of metrical number strings.
    """
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
    pos_mapping: Dict[str, str],
    common_adverbs: set[str],
    unmasked_vocab: set[str],
    out_processed: Path,
    out_metrical_lines: Path,
    out_metrical_sent: Path,
    out_lexical: Path,
    verbose: bool = True,
) -> None:
    """Process a single generated cento XML file.

    Produces plain text, sentence-split, que-split, POS-masked,
    and metrical output files.

    Args:
        xml_path: Path to the generated cento XML file.
        pos_mapping: Pedecerto POS to (ud_pos, should_mask) mapping.
        common_adverbs: Set of adverbs for que-splitting protection.
        unmasked_vocab: Reference unmasked words (stay as words).
        out_processed: Directory for processed output files.
        out_metrical_lines: Directory for line-based metrical output.
        out_metrical_sent: Directory for sentence-based metrical output.
        out_lexical: Directory for lexical (masked) output.
        verbose: If True, print progress messages.
    """
    stem = xml_path.stem

    if verbose:
        print(f"  Processing {stem}...")

    # 1. Extract data from XML
    plain_lines, line_numbers, line_words = extract_xml_data(xml_path)

    # 2. Write plain text
    write_lines(out_processed / f"{stem}.txt", plain_lines)

    # 3. Strip parentheses for sentence splitting
    text_no_parens = strip_parens("\n".join(plain_lines))

    # 4. Sentence splitting
    sentences = sentence_split(text_no_parens)
    write_lines(out_processed / f"{stem}_sentences.txt", sentences)

    # 5. Que-splitting
    quesplit = que_split_sentences(sentences, common_adverbs)
    write_lines(out_processed / f"{stem}_sentences.quesplit.txt", quesplit)

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

    # 7. POS masking (add <EOS> to match existing pipeline format)
    masked = mask_sentences_fifo(quesplit, all_xml_norms, all_xml_pos, pos_mapping, common_adverbs, unmasked_vocab)
    write_lines(out_processed / f"{stem}_sentences.quesplit.masked.txt", append_eos(masked))
    write_lines(out_lexical / f"{stem}_sentences.quesplit.masked.txt", append_eos(masked))

    # 8. Line-based metrical numbers (no <EOS> — one sentence per line)
    write_metrical_lines(out_metrical_lines / f"{stem}.mapped_lines.txt", line_numbers)

    # 9. Sentence-based metrical numbers (add <EOS> to match existing pipeline format)
    sent_met, met_mismatches = metrical_sentences_fifo(
        quesplit, all_xml_norms, all_xml_numbers
    )
    write_lines(out_metrical_sent / f"{stem}_sentences.metrical.txt", append_eos(sent_met))

    if verbose:
        print(f"    {len(plain_lines)} lines, {len(sentences)} sentences, {met_mismatches} metrical mismatches")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir", type=str, required=True,
        help="Path to the generated cento directory (e.g. ../data/generated-compact/exact)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Process only the first N files (0 = all)",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    # Derive output directory names from the source directory name
    # e.g. "exact" -> "generated_exact", "loose" -> "generated_loose"
    dir_name = source_dir.name
    tag = f"generated_{dir_name}"

    out_processed = BASE_DIR / "processed" / tag
    out_metrical_lines = BASE_DIR / "metrical_model_lines" / tag
    out_metrical_sent = BASE_DIR / "metrical_model" / tag
    out_lexical = BASE_DIR / "lexical_model" / tag

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

    # Load reference unmasked vocabulary (words that stay as words)
    if not UNMASKED_VOCAB_PATH.exists():
        print(f"Unmasked vocab file not found: {UNMASKED_VOCAB_PATH}", file=sys.stderr)
        print("Run scripts/extract_unmasked_vocab.py first.", file=sys.stderr)
        return 1
    unmasked_vocab = load_unmasked_vocab(UNMASKED_VOCAB_PATH)
    print(f"Loaded {len(unmasked_vocab)} reference unmasked words from {UNMASKED_VOCAB_PATH.name}")

    # Find source files
    source_files = sorted(source_dir.glob("cento_*.xml"))
    if args.limit > 0:
        source_files = source_files[: args.limit]

    if not source_files:
        print(f"No XML files found in {source_dir}", file=sys.stderr)
        return 1

    print(f"Processing {len(source_files)} generated centos from {source_dir.name}/")
    print(f"Output tag: {tag}")
    print()

    for d in [out_processed, out_metrical_lines, out_metrical_sent, out_lexical]:
        d.mkdir(parents=True, exist_ok=True)

    for xml_path in source_files:
        process_one_file(
            xml_path, pos_mapping, common_adverbs, unmasked_vocab,
            out_processed, out_metrical_lines, out_metrical_sent, out_lexical,
        )

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

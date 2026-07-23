#!/usr/bin/env python3
"""
Sentence-to-number mapping demo.

Maps sentences from the latin-masking _sentences.txt files to metrical
word numbers. This is demo/exploration code — not part of the core
metrical_numbering module.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

from metrical_numbering import _norm, process_line
from filter_hexameter import clean_xml


def read_sentences(sentences_path: Path) -> list[str]:
    """Read sentences file. Each non-empty line is one sentence.

    Args:
        sentences_path: Path to the _sentences.txt file.

    Returns:
        List of sentence strings.
    """
    with open(sentences_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def normalize_words(text: str) -> list[str]:
    """Normalize text into lowercase word tokens with v→u, j→i.

    Args:
        text: Input text with optional pipe caesura markers.

    Returns:
        List of normalized lowercase word tokens.
    """
    text = text.replace("|", " ")
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return [_norm(t) for t in tokens]


def load_hex_lines(xml_path: Path) -> list:
    """Load hexameter lines from an XML file.

    Args:
        xml_path: Path to the Pedecerto XML file.

    Returns:
        List of BeautifulSoup <line> tags with meter="H".
    """
    with open(xml_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")
    return [el for el in soup.find_all("line") if el.get("meter") == "H"]


def build_xml_index(xml_lines: list) -> tuple[list[str], list[int]]:
    """Build flat (normalized_word, number) lists from XML lines.

    Uses process_line output directly, which handles all scansion rules
    (elision, que_fwd, PE, push_e). Lost words (PE targets, push_e) get 0.

    Args:
        xml_lines: List of BeautifulSoup <line> tags.

    Returns:
        Tuple of (texts, numbers) parallel lists.
    """
    texts: list[str] = []
    texts: list[str] = []
    numbers: list[int] = []
    for line_tag in xml_lines:
        for w in process_line(line_tag):
            texts.append(_norm(str(w["text"])))
            num = w["number"]
            if isinstance(num, int):
                numbers.append(num)
            else:
                numbers.append(0)
    return texts, numbers


def build_permutation(
    xml_texts: list[str], xml_numbers: list[int], sent_words: list[str]
) -> list[int]:
    """Build a permutation mapping sentence word indices to XML positions.

    Uses FIFO matching: for each word, pop the next available XML index.
    This naturally handles duplicates and reordering.

    Args:
        xml_texts: Normalized XML words.
        xml_numbers: Numbers for each XML word.
        sent_words: Normalized sentence words to match.

    Returns:
        List of XML indices (one per sentence word). -1 = no match.
    """
    index_map: dict[str, list[int]] = defaultdict(list)
    for i, w in enumerate(xml_texts):
        index_map[w].append(i)

    # Reverse so we can use O(1) pop() from the end
    for val in index_map:
        index_map[val].reverse()

    permutation: list[int] = []
    for sw in sent_words:
        if index_map.get(sw):
            permutation.append(index_map[sw].pop())
        else:
            permutation.append(-1)

    return permutation


def verify_permutation(
    xml_texts: list[str], sent_words: list[str], permutation: list[int]
) -> list[str]:
    """Verify that the permutation produces correct words.

    Args:
        xml_texts: Normalized XML words.
        sent_words: Normalized sentence words.
        permutation: Mapping from sentence indices to XML positions.

    Returns:
        List of error descriptions. Empty list means all valid.
    """
    errors: list[str] = []
    for i, (sw, xml_pos) in enumerate(zip(sent_words, permutation)):
        if xml_pos < 0:
            errors.append(f"  [{i}] '{sw}' → no match")
        elif xml_texts[xml_pos] != sw:
            errors.append(
                f"  [{i}] '{sw}' → '{xml_texts[xml_pos]}' at pos {xml_pos}"
            )
    return errors


def sentences_to_numbered(
    xml_lines: list,
    sentences_path: Path,
) -> list[str]:
    """Pair each sentence from sentences.txt with its numbered form.

    Uses FIFO permutation matching to map sentence words to XML positions.
    PE target words get 0. Returns one string per sentence with <EOL> and
    <EOS> tokens preserved.

    Args:
        xml_lines: List of BeautifulSoup <line> tags.
        sentences_path: Path to the _sentences.txt file.

    Returns:
        List of numbered sentence strings.
    """
    xml_texts, xml_numbers = build_xml_index(xml_lines)
    sentences_raw = read_sentences(sentences_path)

    # Flatten sentence words, tracking <EOL>/<EOS> positions
    flat_words: list[str] = []
    eol_after: set[int] = set()
    eos_after: list[int] = []

    for sent in sentences_raw:
        for tok in sent.split():
            if tok == "<EOL>":
                eol_after.add(len(flat_words) - 1)
            else:
                w = _norm(re.sub(r"[^a-zA-Z]", "", tok))
                if w:
                    flat_words.append(w)
        eos_after.append(len(flat_words) - 1)

    # Build and verify permutation
    permutation = build_permutation(xml_texts, xml_numbers, flat_words)
    errors = verify_permutation(xml_texts, flat_words, permutation)
    if errors:
        print(f"WARNING: {len(errors)} permutation mismatches:")
        for e in errors[:10]:
            print(e)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    # Build flat output
    flat_parts: list[str] = []
    for i, xml_pos in enumerate(permutation):
        if xml_pos >= 0:
            flat_parts.append(str(xml_numbers[xml_pos]))
        else:
            flat_parts.append("0")
        if i in eol_after:
            flat_parts.append("<EOL>")
        if i in eos_after:
            flat_parts.append("<EOS>")

    # Split into per-sentence strings at <EOS>
    result: list[str] = []
    current: list[str] = []
    for part in flat_parts:
        current.append(part)
        if part == "<EOS>":
            result.append(" ".join(current))
            current = []
    if current:
        result.append(" ".join(current))

    return result


def corpus_to_string(
    xml_lines: list,
    sentences_path: Path,
) -> str:
    """Convert XML lines to a single numbered string in XML line order.

    Output: space-separated word numbers, <EOL> after each line's last word,
    <EOS> after each sentence's last word. Lost PE words are omitted.

    Uses the global permutation to find which XML word ends each sentence,
    then places <EOS> at that exact position.

    Args:
        xml_lines: List of BeautifulSoup <line> tags.
        sentences_path: Path to the _sentences.txt file.

    Returns:
        A single string of space-separated numbers with <EOL> and <EOS> tokens.
    """
    xml_texts, xml_numbers = build_xml_index(xml_lines)
    sentences_raw = read_sentences(sentences_path)

    # Flatten sentence words and track EOS positions
    flat_sent_words: list[str] = []
    eos_after_idx: list[int] = []  # sentence word index after which <EOS> goes

    for sent in sentences_raw:
        for tok in sent.split():
            if tok != "<EOL>":
                w = _norm(re.sub(r"[^a-zA-Z]", "", tok))
                if w:
                    flat_sent_words.append(w)
        eos_after_idx.append(len(flat_sent_words) - 1)

    # Build permutation: sentence word → XML position
    permutation = build_permutation(xml_texts, xml_numbers, flat_sent_words)

    # Find which XML positions are sentence-ending
    eos_xml_positions: set[int] = set()
    for si in eos_after_idx:
        if si < len(permutation) and permutation[si] >= 0:
            eos_xml_positions.add(permutation[si])

    # Build output in XML order: numbers + <EOL> + <EOS>
    parts: list[str] = []
    xml_pos = 0
    for line_tag in xml_lines:
        words = process_line(line_tag)
        for w in words:
            if w["number"] is not None:
                parts.append(str(w["number"]))
            if xml_pos in eos_xml_positions:
                parts.append("<EOS>")
            xml_pos += 1
        parts.append("<EOL>")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main: generate demo output
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    xml_path = Path("ausonius_raw/cento_nuptialis.xml")
    sentences_path = Path("question_text_processed/cento_nuptialis_sentences.txt")

    hex_lines = load_hex_lines(xml_path)
    raw_sents = read_sentences(sentences_path)
    numbered = sentences_to_numbered(hex_lines, sentences_path)

    # Token count verification
    mismatches = 0
    for i, (raw, nums) in enumerate(zip(raw_sents, numbered)):
        raw_words = len(normalize_words(raw.replace("<EOL>", " ")))
        num_parts = nums.split()
        num_words = sum(1 for p in num_parts if p not in ("<EOL>", "<EOS>"))
        raw_eols = raw.count("<EOL>")
        num_eols = num_parts.count("<EOL>")
        if raw_words != num_words or raw_eols != num_eols:
            mismatches += 1
            print(f"  Sentence {i+1}: raw={raw_words} num={num_words} "
                  f"(eol: {raw_eols}/{num_eols}) | {raw[:60]}")

    # Write output
    with open("cento_sentences_numbered.txt", "w") as out:
        for raw, nums in zip(raw_sents, numbered):
            out.write(raw + "\n")
            out.write(nums + "\n")
            out.write("-" * 80 + "\n")

    print(f"Written {len(raw_sents)} sentence pairs")
    print(f"Token mismatches: {mismatches}")

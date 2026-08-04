#!/usr/bin/env python3
"""
Metrical numbering for hypotactic JSON format.

Converts word syllable data from the hypotactic corpus JSON files into the
same prime-encoded integers used by metrical_numbering.py for Pedecerto XML.

Syllable length mapping:
  long   → L (prime 2)
  short  → S (prime 3)
  elided → E (prime 5) or PE/Q depending on context

Rules (matching metrical_numbering.py):
  1. Elided "que" syllable → que_fwd: remove que, prepend Q to next word.
  2. Elided "est" (single word) → PE target: est gets 0, previous word gets PE.
  3. Elided last syllable on multi-syllable word → append E.
  4. Elided single-syllable word (not est, not que) → push_e: word gets 0, E goes to next.

Public API:
  process_line(line_dict) → list of word dicts
  load_book(json_path, author, work, book) → list of line dicts
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from metrical_numbering import PRIME, WordResult, word_to_number


# ---------------------------------------------------------------------------
# Syllable helpers
# ---------------------------------------------------------------------------

def _syl_length(syl: dict[str, str]) -> str:
    """Get normalised length from a syllable dict."""
    return (syl.get("length") or "").strip().lower()


def _strip_diacritics(text: str) -> str:
    """Remove diacritics/macrons by decomposing Unicode and stripping marks."""
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-zA-Z]", "", stripped)


def _syl_text(syl: dict[str, str]) -> str:
    """Get cleaned text from a syllable dict (strip diacritics and punctuation)."""
    return _strip_diacritics(syl.get("text", ""))


def _word_text(word: dict[str, Any]) -> str:
    """Get cleaned text from a word dict."""
    return _strip_diacritics(word.get("text", ""))


def _word_syllables(word: dict[str, Any]) -> list[dict[str, str]]:
    """Get syllable list from a word dict."""
    return word.get("syllables") or []


# ---------------------------------------------------------------------------
# Line processing
# ---------------------------------------------------------------------------

def process_line(line_dict: dict[str, Any]) -> list[WordResult]:
    """Process a single line dict and return word data.

    Same output format as metrical_numbering.process_line.

    Args:
        line_dict: A line dict from the hypotactic JSON.

    Returns:
        List of dicts with keys: text, syllables, added, final_syllables, number.
    """
    # Collect all words from all segments
    all_words: list[dict[str, Any]] = []
    for seg in (line_dict.get("segments") or []):
        for w in (seg.get("words") or []):
            all_words.append(w)

    results: list[WordResult] = []

    for i, w in enumerate(all_words):
        text = _word_text(w)
        syls = _word_syllables(w)

        # Convert syllables to L/S, detect special cases
        base: list[str] = []
        last_syl_text = ""
        has_elided = False

        for s in syls:
            length = _syl_length(s)
            st = _syl_text(s)

            if length == "elided":
                has_elided = True
                last_syl_text = st
                continue  # don't add to base yet

            if length == "long":
                base.append("L")
            elif length == "short":
                base.append("S")
            # skip empty/unknown

            last_syl_text = st

        # Special case: est with elided syllable → PE target
        if text.lower() == "est" and has_elided:
            results.append({
                "text": text,
                "sy_raw": "",
                "syllables": [],
                "added": ["lost"],
                "final_syllables": [],
                "number": 0,
            })
            continue

        added: list[str] = []
        next_word = all_words[i + 1] if i + 1 < len(all_words) else None

        if has_elided:
            # Check if elided syllable is "que" → que_fwd
            if last_syl_text.lower() == "que":
                added.append("que_fwd")
                # Don't add E — the que is removed, Q goes to next word
            elif len(base) == 0:
                # Single-syllable word fully elided → push_e
                added.append("push_e")
                results.append({
                    "text": text,
                    "sy_raw": "",
                    "syllables": base,
                    "added": ["push_e"],
                    "final_syllables": [],
                    "number": 0,
                })
                continue
            else:
                # Multi-syllable word with elision → append E
                base.append("E")

        # Check if NEXT word is PE target (est with elided syl)
        if next_word is not None:
            next_syls = _word_syllables(next_word)
            next_text = _word_text(next_word)
            next_is_pe = (
                next_text.lower() == "est"
                and any(_syl_length(s) == "elided" for s in next_syls)
            )
            if next_is_pe:
                added.append("PE")

        final = base + [s for s in added if s in PRIME]
        number = word_to_number(final) if final else 1

        results.append({
            "text": text,
            "sy_raw": "",
            "syllables": base,
            "added": added,
            "final_syllables": final,
            "number": number,
        })

    # Second pass: que_fwd and push_e propagation
    for i, r in enumerate(results):
        if "que_fwd" in r["added"]:
            for j in range(i + 1, len(results)):
                if results[j]["final_syllables"]:
                    results[j]["final_syllables"] = ["Q"] + results[j]["final_syllables"]
                    results[j]["number"] = word_to_number(results[j]["final_syllables"])
                    results[j]["added"].append("que_cluster")
                    break

        elif "push_e" in r["added"]:
            for j in range(i + 1, len(results)):
                if results[j]["final_syllables"]:
                    results[j]["final_syllables"] = results[j]["final_syllables"] + ["E"]
                    results[j]["number"] = word_to_number(results[j]["final_syllables"])
                    results[j]["added"].append("e_from_prev")
                    break

    return results


# ---------------------------------------------------------------------------
# Book loading
# ---------------------------------------------------------------------------

def load_book(json_path: Path, author: str, work: str, book: str) -> list[dict[str, Any]]:
    """Load hexameter lines from a hypotactic JSON file.

    Args:
        json_path: Path to the author JSON file (e.g. vergil.json).
        author: Author name key.
        work: Work name key.
        book: Book name key.

    Returns:
        List of line dicts with metre == "hexameter".
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    book_data = data[author][work][book]
    # book_data is a list with one entry containing "poem content"
    if isinstance(book_data, list):
        poems = book_data
    else:
        poems = [book_data]

    lines: list[dict[str, Any]] = []
    for poem in poems:
        for line in poem.get("poem content", []):
            if line.get("metre", "").lower() == "hexameter":
                lines.append(line)

    return lines

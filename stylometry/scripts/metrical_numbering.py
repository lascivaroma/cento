#!/usr/bin/env python3
"""
Metrical scansion to unique number conversion.

Converts each word's syllable pattern into a unique integer using prime encoding:
  L (long)     = 2
  S (short)    = 3
  E (elided)   = 5
  PE (prodel.) = 7
  Q (que)      = 11

Rules:
  1. Each syllable from the Pedecerto scansion (sy attribute) is mapped:
     A, T, X → L (long)
     b, c    → S (short)
  2. If next word has mf="PE" (prodelision), this word gets PE.
  3. If word ends in -que, next starts with vowel, and mf="SY" → que_fwd
     (word keeps base syllables, next word gets Q prefix).
  4. mf="SY" on a word → append E (elision).
  5. Lost words (PE targets) are omitted from output.

Public API:
  process_line(line_tag) → list of word dicts with syllable/number data
  word_to_number(syllables) → unique integer for a syllable sequence
  parse_sy(sy) → list of L/S from a Pedecerto sy attribute
  _norm(word) → lowercase + v→u, j→i normalization
"""

from __future__ import annotations

import re
from math import prod
from typing import TypedDict

from bs4 import Tag


class WordResult(TypedDict):
    """Result dict from process_line for a single word."""

    text: str
    sy_raw: str
    syllables: list[str]
    added: list[str]
    final_syllables: list[str]
    number: int


# ---------------------------------------------------------------------------
# Prime mapping
# ---------------------------------------------------------------------------
PRIME = {"L": 2, "S": 3, "E": 5, "PE": 7, "Q": 11}


def word_to_number(syllables: list[str]) -> int:
    """Convert a list of syllable type strings to a unique integer.

    Uses prime encoding where each syllable type maps to a unique prime.
    The product of primes is unique for any multiset of syllable types
    (by the fundamental theorem of arithmetic).

    Args:
        syllables: List of syllable type strings (e.g., ["L", "S", "E"]).

    Returns:
        The unique integer for the syllable multiset. Returns 1 for empty lists.
    """
    if not syllables:
        return 1
    return prod(PRIME[s] for s in syllables)


# ---------------------------------------------------------------------------
# Syllable parsing
# ---------------------------------------------------------------------------

def parse_sy(sy: str) -> list[str]:
    """Parse a Pedecerto sy attribute into a list of L/S strings.

    The sy attribute encodes metrical positions like '1A1b1c2A'.
    Each token maps to one syllable:
      A, T, X → L (long: arsis, thesis in spondee, or final)
      b, c    → S (short: thesis biceps in dactyl)

    Args:
        sy: The Pedecerto sy attribute string.

    Returns:
        List of "L" and "S" strings, one per syllable position.
    """
    if not sy:
        return []

    tokens = re.findall(r"[0-9]+([A-Za-z])", sy)
    result = []
    for t in tokens:
        if t in ("A", "T", "X"):
            result.append("L")
        elif t in ("b", "c"):
            result.append("S")
    return result


def word_text(word_tag: Tag) -> str:
    """Get cleaned text of a word tag, stripping all non-alpha characters.

    Args:
        word_tag: A BeautifulSoup word tag element.

    Returns:
        The cleaned text with only alphabetic characters.
    """
    return re.sub(r"[^a-zA-Z]", "", word_tag.get_text(strip=True))


def ends_with_que(text: str) -> bool:
    """Check if word ends with 'que' (case-insensitive Latin).

    Args:
        text: The word text to check.

    Returns:
        True if the word ends with 'que'.
    """
    return text.lower().endswith("que")


def is_vowel_start(text: str) -> bool:
    """Check if word starts with a vowel or h.

    Args:
        text: The word text to check.

    Returns:
        True if the word starts with a, e, i, o, u, or h.
    """
    if not text:
        return False
    return text[0].lower() in "aeiouh"


# ---------------------------------------------------------------------------
# Line processing
# ---------------------------------------------------------------------------

def process_line(line_tag: Tag) -> list[WordResult]:
    """Process a single <line> element and return word data.

    Only processes words that have actual scansion (non-empty sy attribute).
    Lost words (PE targets, elided single-syllable) get number=0.

    Rules:
      - PE takes priority: if next word has mf="PE", this word gets PE.
      - que_fwd: -que word with mf="SY" + next word starts with vowel →
        -que word keeps base syllables, next word gets Q prefix.
      - Elision: mf="SY" on a multi-syllable word → append E.
      - Elided single-syllable word (mf="SY", no scansion) → number 0,
        push E to next word.
      - PE target (mf="PE", no scansion) → number 0.

    Args:
        line_tag: A BeautifulSoup <line> tag element.

    Returns:
        List of dicts with keys: text, sy_raw, syllables, added,
        final_syllables, number (int).
    """
    words = line_tag.find_all("word")
    results: list[WordResult] = []

    for i, w in enumerate(words):
        text = word_text(w)
        sy_raw = str(w.get("sy", "") or "")
        mf = str(w.get("mf", "") or "")
        base_syllables = parse_sy(sy_raw)

        # Skip words with no scansion (caesurae, etc.)
        # but keep PE targets and elided words (SY with no scansion)
        if not base_syllables and mf not in ("PE", "SY"):
            continue

        added: list[str] = []
        next_word = words[i + 1] if i + 1 < len(words) else None
        next_text = word_text(next_word) if next_word is not None else ""
        next_mf = str(next_word.get("mf", "") or "") if next_word is not None else ""

        # PE target — lost word, number 0 (same as push_e)
        if mf == "PE":
            results.append({
                "text": text,
                "sy_raw": sy_raw,
                "syllables": [],
                "added": ["lost"],
                "final_syllables": [],
                "number": 0,
            })
            continue

        # Elided word with no scansion (e.g. "tu", "se") — number 0, push E to next
        if mf == "SY" and not base_syllables:
            results.append({
                "text": text,
                "sy_raw": sy_raw,
                "syllables": [],
                "added": ["push_e"],
                "final_syllables": [],
                "number": 0,
            })
            continue

        # Check if NEXT word has mf="PE" → this word gets PE
        # (prodelision: the next word's initial vowel is absorbed)
        if next_mf == "PE":
            added.append("PE")

        # Que-elision: word ends in -que, next starts with vowel, and mf="SY"
        # The -que word keeps its base syllables; consonantal cluster moves to next word (Q)
        elif (
            next_word is not None
            and ends_with_que(text)
            and is_vowel_start(next_text)
            and mf == "SY"
        ):
            added.append("que_fwd")

        # Elision: mf="SY" means the word has an elided syllable
        elif mf == "SY":
            added.append("E")

        # Otherwise: rely on the scansion as-is. Elided syllables simply
        # don't appear in the sy attribute, so no E marking is needed.

        final_syllables = base_syllables + [s for s in added if s in PRIME]
        number = word_to_number(final_syllables) if final_syllables else 1

        results.append({
            "text": text,
            "sy_raw": sy_raw,
            "syllables": base_syllables,
            "added": added,
            "final_syllables": final_syllables,
            "number": number,
        })

    # Second pass: handle que_fwd and push_e
    for i, r in enumerate(results):
        if "que_fwd" in r["added"]:
            for j in range(i + 1, len(results)):
                results[j]["final_syllables"] = ["Q"] + results[j]["final_syllables"]
                results[j]["number"] = word_to_number(results[j]["final_syllables"])
                results[j]["added"].append("que_cluster")
                break

        elif "push_e" in r["added"]:
            # Append E to the next word's syllables
            for j in range(i + 1, len(results)):
                if results[j].get("final_syllables"):
                    results[j]["final_syllables"] = results[j]["final_syllables"] + ["E"]
                    results[j]["number"] = word_to_number(results[j]["final_syllables"])
                    results[j]["added"].append("e_from_prev")
                    break

    return results


def _norm(word: str) -> str:
    """Normalize a single word: lowercase, v→u, j→i.

    Args:
        word: The word to normalize.

    Returns:
        The normalized lowercase word with v→u and j→i substitutions.
    """
    return word.lower().replace("v", "u").replace("j", "i")




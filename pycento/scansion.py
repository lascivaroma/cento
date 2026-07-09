"""Wires up the (locally-built) latin_scansion/pynini FST engine to answer a
narrow question: after gluing two independently-chosen Virgil segments
together, is the resulting text still a well-formed dactylic hexameter?

We do NOT need true macronization (a full vowel-quantity dictionary) for
this. We already know, from our own per-syllable `long`/`short`/`anceps`/
`end` annotations, which syllables are heavy -- that IS the information a
macron encodes for an open syllable (a closed syllable's weight is already
determined by its trailing consonants, which the engine infers from plain
spelling with no macron needed). So we reconstruct a "just enough macronized"
string straight from our own data and hand it to latin_scansion's own
grammar, which then freshly determines weight/elision right at the new
word boundary (the one place our old, pre-merge annotations don't apply
anymore) while trusting our already-known weights everywhere else.

Requires a compiled grammar archive (grammars/all.far) -- see
scripts/fetch_latin_scansion.sh and the project README for how to build one
locally (thrax + pynini, no PyPI wheel for thrax). Not committed to the repo
(it's a local build artifact); point CENTO_SCANSION_FAR at one if it's not
at the default vendor/latin_scansion/grammars/all.far location.
"""

import functools
import os
import os.path as op
import re
from typing import List

from pycento.data import Word

# Syllable text in the gold data sometimes carries editorial marks that
# aren't part of the Latin spelling: leading quotation marks (marking where
# a cento quotation starts, e.g. "'ac") and trailing sentence punctuation
# (e.g. "bant,", "dit."). Strip both edges down to plain letters before
# macron-processing -- same class of fix as the punctuation-stripping done
# for the PaPie tagger input in preprocess/annotate_*.py.
_EDGE_NON_LETTER = re.compile(r"^[^a-zA-Zāēīōūȳ]+|[^a-zA-Zāēīōūȳ]+$")

_ROOT = op.dirname(op.dirname(op.abspath(__file__)))
_FAR_ENV = "CENTO_SCANSION_FAR"
_DEFAULT_FAR = op.join(_ROOT, "vendor", "latin_scansion", "grammars", "all.far")

_HEAVY_LENGTHS = {"long", "anceps", "end"}
_VOWELS = "aeiouyAEIOUY"
_MACRON = {
    "a": "ā", "e": "ē", "i": "ī", "o": "ō", "u": "ū", "y": "ȳ",
    "A": "Ā", "E": "Ē", "I": "Ī", "O": "Ō", "U": "Ū", "Y": "Ȳ",
}
# Common diphthong digraphs -- inherently heavy on their own, so a macron on
# either letter would be wrong (and unnecessary): the engine's PRONOUNCE
# grammar already recognizes these.
_DIPHTHONGS = ("ae", "oe", "au", "eu", "ei", "ui")


class ScansionUnavailable(Exception):
    """Raised when the compiled grammar archive can't be found."""


def _macronize_syllable(text: str, heavy: bool) -> str:
    if not text:
        return ""
    text = _EDGE_NON_LETTER.sub("", text)
    if not heavy or not text:
        return text
    lower = text.lower()
    if any(d in lower for d in _DIPHTHONGS):
        return text  # diphthong nucleus -- already inherently heavy, no macron needed
    for i in range(len(text) - 1, -1, -1):
        if text[i] in _VOWELS:
            return text[:i] + _MACRON.get(text[i], text[i]) + text[i + 1:]
    return text  # no vowel found (shouldn't happen for a real syllable)


def macronize_word(word: Word) -> str:
    """Reconstruct word.text with macrons over every syllable our own data
    marks as heavy (long/anceps/end) -- including elided syllables' plain
    text (left unmacronized and un-dropped: we want the FULL spelling so the
    engine can decide elision fresh, not have it pre-baked in by us).

    Some gold-data syllables have no recorded text at all (a self-closing
    `<s met="long"/>` with no text content, e.g. one syllable of "dies" in
    data/gold/cento.xml) -- silently skipping those would truncate the word
    ("dies" -> "di"). If any syllable is missing text, fall back to
    word.text verbatim (unmacronized) rather than emit a corrupted spelling.
    """
    if not word.syllables or any(not syll.text for syll in word.syllables):
        return word.text or ""
    return "".join(
        _macronize_syllable(syll.text, syll.length in _HEAVY_LENGTHS)
        for syll in word.syllables
    )


def macronize_words(words: List[Word]) -> str:
    return " ".join(macronize_word(w) for w in words if w.text)


@functools.lru_cache(maxsize=1)
def _load_rules(far_path: str = None):
    far_path = far_path or os.environ.get(_FAR_ENV, _DEFAULT_FAR)
    if not op.exists(far_path):
        raise ScansionUnavailable(
            f"Compiled scansion grammar not found at {far_path!r}. Run "
            f"scripts/fetch_latin_scansion.sh, build thrax + pynini (see "
            f"README's Installation section), then "
            f"`make -j -C vendor/latin_scansion/grammars`. Or set "
            f"{_FAR_ENV} to point at an already-compiled all.far."
        )
    import pynini

    with pynini.Far(far_path, "r") as far:
        return (
            far["NORMALIZE"], far["PRONOUNCE"], far["VARIABLE"],
            far["SYLLABLE"], far["WEIGHT"], far["HEXAMETER"],
        )


def scan_text(text: str):
    """Returns a latin_scansion Verse proto for `text`. Raises
    ScansionUnavailable if the grammar archive isn't available."""
    from latin_scansion import scan_verse

    rules = _load_rules()
    return scan_verse(*rules, text)


def is_valid_hexameter(text: str) -> bool:
    """True iff `text` scans as a well-formed dactylic hexameter (the
    HEXAMETER grammar already encodes the anceps-final-foot allowance and
    dactyl/spondee substitution rules, so this is the complete validity
    signal -- no need to separately re-count morae).

    Checks BOTH `not verse.defective` AND `verse.foot` non-empty: a failure
    at the earlier NORMALIZE stage (e.g. a character the grammar doesn't
    recognize) returns early with `defective` left at its proto default of
    False and an empty `foot` list -- that reads as "valid" if you only
    check `defective`, so both must be checked.
    """
    verse = scan_text(text)
    return not verse.defective and len(verse.foot) > 0

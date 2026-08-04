"""
latin_elision.py

Detects elision and prodelision between two consecutive words in
Latin verse (dactylic hexameter, elegiac couplets, etc.).
"""
import os.path
import re
import unicodedata
from typing import NamedTuple

VOWELS = set("aeiouy")  # y appears in Greek loanwords, e.g. "lyra"
PRODELISION_WORDS = {"es", "est"}  # short forms of *sum* that elide themselves

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "stylometry", "vergil_vj_vocab.txt")) as f:
    VJ_WORDS = set([l.strip() for l in f.read().splitlines()])

def _clean(word: str) -> str:
    """Lowercase a word and strip punctuation, whitespace, and
    diacritics (macrons/breves) -- none of these affect elision."""
    decomposed = unicodedata.normalize("NFD", word)
    no_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z]", "", no_marks.lower())


def _starts_with_vowel_sound(w: str) -> bool:
    """Does cleaned word `w` expose a vowel sound at its start?"""
    if not w:
        return False
    if w in VJ_WORDS:
        return False
    # Word-initial i/u before another vowel is usually consonantal
    # (semivowel): "iam" ~ "yam", "video"/"uideo" ~ "wideo".
    if w[0] in ("i", "u") and len(w) > 1 and w[1] in VOWELS:
        if len(w) > 2 and w[2] in VOWELS: # uuam starts with vowel
            return True
        else:
            return False
    if w[0] == "h":  # h is phonetically silent
        return len(w) > 1 and w[1] in VOWELS
    return w[0] in VOWELS


def _ends_in_vowel_diphthong_or_m(w: str) -> bool:
    """Does cleaned word `w` end in a vowel, diphthong, or vowel + m?"""
    if not w:
        return False
    if w[-1] in VOWELS:
        return True
    return w[-1] == "m" and len(w) > 1 and w[-2] in VOWELS


class ElisionResult(NamedTuple):
    word1_elided: bool      # word1 loses its final syllable
    word2_prodelided: bool  # word2 ("es"/"est") loses its own leading e-

    def __bool__(self) -> bool:
        """True if *anything* elides at this word boundary, regardless
        of which word loses the syllable -- handy when you just need
        to know whether to drop a syllable while counting a line."""
        return self.word1_elided or self.word2_prodelided


def check_elision(word1: str, word2: str) -> ElisionResult:
    """
    Check the word-boundary between `word1` and `word2` for elision.

    Returns ElisionResult(word1_elided, word2_prodelided):

      * word1_elided      -- True for the ordinary case: word1's final
                              syllable drops (e.g. "multum ille").
      * word2_prodelided  -- True when word2 is "es"/"est" and it is
                              THAT word which drops its own e- instead
                              (e.g. "dictum est" -> "dictumst").

    The two are mutually exclusive -- a boundary is an ordinary
    elision, a prodelision, or neither, never both. The result is
    also truthy/falsy on its own, so `if check_elision(w1, w2):` asks
    "does a syllable drop here at all, on either side?".

        check_elision("multum", "ille")     -> (True,  False)
        check_elision("dictum", "est")      -> (False, True)
        check_elision("terris", "iactatus") -> (False, False)
    """
    w1, w2 = _clean(word1), _clean(word2)
    if not w1 or not w2:
        return ElisionResult(False, False)

    clash = _ends_in_vowel_diphthong_or_m(w1) and _starts_with_vowel_sound(w2)
    if not clash:
        return ElisionResult(False, False)

    if w2 in PRODELISION_WORDS:
        return ElisionResult(False, True)

    return ElisionResult(True, False)


def elides(word1: str, word2: str) -> bool:
    """True if word1's final syllable is elided before word2."""
    return check_elision(word1, word2).word1_elided


def prodelides(word1: str, word2: str) -> bool:
    """True if word2 (a form of "es"/"est") drops its own leading e-
    because of word1 -- e.g. prodelides("dictum", "est") -> True."""
    return check_elision(word1, word2).word2_prodelided


if __name__ == "__main__":
    # (word1, word2, expected_result, note)
    cases = [
        ("multum", "ille", ElisionResult(True, False), "Aen. 1.3 -- ordinary elision"),
        ("monstrum", "horrendum", ElisionResult(True, False), "Aen. 3.658 -- h doesn't block elision"),
        ("horrendum", "informe", ElisionResult(True, False), "Aen. 3.658 -- same line"),
        ("informe", "ingens", ElisionResult(True, False), "Aen. 3.658 -- same line"),
        ("virumque", "cano", ElisionResult(False, False), "cano starts with a consonant"),
        ("Troiae", "qui", ElisionResult(False, False), "'qu' is a consonant, not a vowel"),
        ("dictum", "est", ElisionResult(False, True), "prodelision: 'est' loses its own e-"),
        ("terris", "iactatus", ElisionResult(False, False), "'terris' ends in a consonant"),
        ("bella", "es", ElisionResult(False, True), "prodelision also triggers on 'es'"),
        ("amat", "est", ElisionResult(False, False), "amat ends in a consonant -> no clash at all"),
        ("bella", "et", ElisionResult(True, False), "illustrative: -a before vowel"),
        ("atque", "iam", ElisionResult(False, False), "illustrative: 'iam' is consonant-initial"),
        ("puella", "hic", ElisionResult(True, False), "illustrative: silent h before vowel"),
        ("Aeneas", "", ElisionResult(False, False), "empty word2 is handled gracefully"),
        ("manum", "uuam", ElisionResult(True, False), "Triple should go through"),
    ]

    w1_width = max(len(c[0]) for c in cases)
    w2_width = max(len(c[1]) for c in cases)
    all_ok = True
    for w1, w2, expected, note in cases:
        result = check_elision(w1, w2)
        ok = result == expected
        all_ok &= ok
        mark = "OK" if ok else "FAIL"
        print(f"{w1:<{w1_width}} + {w2:<{w2_width}} -> {str(result):<28} "
              f"(expected {str(expected):<28}) [{mark}]  {note}")

    print("\nAll tests passed!" if all_ok else "\nSome tests FAILED.")
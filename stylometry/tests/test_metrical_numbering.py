"""Tests for metrical_numbering module.

Ground truth taken from the verified metrical_demo_output.txt of cento_nuptialis.
"""

import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# Add scripts/ to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from metrical_numbering import (  # noqa: E402
    parse_sy,
    word_to_number,
    word_text,
    ends_with_que,
    is_vowel_start,
    process_line,
)
from sentence_mapping import (  # noqa: E402
    load_hex_lines,
    corpus_to_string,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_cento_lines():
    """Load all hexameter lines from cento_nuptialis.xml."""
    return load_hex_lines(Path(__file__).parent.parent / "raw" / "question" / "cento_nuptialis.xml")


def line_numbers(line_tag) -> list[tuple[str, object]]:
    """Return (word_text, number) pairs for a line."""
    return [(str(w["text"]), w["number"]) for w in process_line(line_tag)]


# ---------------------------------------------------------------------------
# parse_sy
# ---------------------------------------------------------------------------

class TestParseSy:
    def test_empty(self):
        assert parse_sy("") == []

    def test_single_long(self):
        assert parse_sy("1A") == ["L"]

    def test_single_short(self):
        assert parse_sy("4c") == ["S"]

    def test_mixed(self):
        assert parse_sy("1A1b1c2A") == ["L", "S", "S", "L"]

    def test_arsis_thesis_final(self):
        # A=long, T=long, X=long
        assert parse_sy("6A6X") == ["L", "L"]

    def test_biceps(self):
        assert parse_sy("1b1c") == ["S", "S"]

    def test_complex(self):
        assert parse_sy("4A4b4c5A5b5c") == ["L", "S", "S", "L", "S", "S"]


# ---------------------------------------------------------------------------
# word_to_number
# ---------------------------------------------------------------------------

class TestWordToNumber:
    def test_empty(self):
        assert word_to_number([]) == 1

    def test_single_long(self):
        assert word_to_number(["L"]) == 2

    def test_single_short(self):
        assert word_to_number(["S"]) == 3

    def test_long_short(self):
        assert word_to_number(["L", "S"]) == 6

    def test_long_long_short(self):
        assert word_to_number(["L", "L", "S"]) == 12

    def test_order_independent(self):
        """Same multiset gives same number regardless of order."""
        assert word_to_number(["L", "S", "L"]) == word_to_number(["L", "L", "S"])

    def test_elision(self):
        assert word_to_number(["L", "E"]) == 10

    def test_prodelision(self):
        assert word_to_number(["L", "L", "PE"]) == 28

    def test_que_cluster(self):
        assert word_to_number(["Q", "L", "L", "S", "S"]) == 396

    def test_unique_per_multiset(self):
        """Different multisets give different numbers."""
        a = word_to_number(["L", "S"])
        b = word_to_number(["L", "L"])
        c = word_to_number(["S", "S"])
        assert len({a, b, c}) == 3


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_ends_with_que_true(self):
        assert ends_with_que("laetasque")
        assert ends_with_que("Fortunamque")
        assert ends_with_que("atque")

    def test_ends_with_que_false(self):
        assert ends_with_que("cuique") is not False  # cuique DOES end in que
        assert not ends_with_que("uirum")
        assert not ends_with_que("est")

    def test_is_vowel_start(self):
        assert is_vowel_start("animis")
        assert is_vowel_start("haec")
        assert not is_vowel_start("mentes")

    def test_word_text_strips_punctuation(self):
        soup = BeautifulSoup("<word>Nauam,</word>", "xml")
        tag = soup.find("word")
        assert tag is not None
        assert word_text(tag) == "Nauam"


# ---------------------------------------------------------------------------
# process_line — verified cento_nuptialis lines
# ---------------------------------------------------------------------------

class TestProcessLineCento:
    """Test against verified output from metrical_demo_output.txt."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.lines = load_cento_lines()

    # Line 1: elision (Accipite), que_fwd (laetasque → aduertite)
    def test_line_1(self):
        pairs = line_numbers(self.lines[0])
        expected = [
            ("Accipite", 90),       # L,S,S,E = 2·3·3·5
            ("haec", 2),            # L
            ("animis", 18),         # S,S,L = 3·3·2
            ("laetasque", 4),       # L,L (que_fwd, no E)
            ("aduertite", 396),     # Q,L,L,S,S = 11·2·2·3·3
            ("mentes", 4),          # L,L
        ]
        assert pairs == expected

    # Line 2: two elisions (Ambo, ambo)
    def test_line_2(self):
        pairs = line_numbers(self.lines[1])
        expected = [
            ("Ambo", 10),           # L,E = 2·5
            ("animis", 18),         # S,S,L
            ("ambo", 10),           # L,E
            ("insignes", 8),        # L,L,L
            ("praestantibus", 36),  # L,L,S,S
            ("armis", 4),           # L,L
        ]
        assert pairs == expected

    # Line 3: no elisions, no special features
    def test_line_3(self):
        pairs = line_numbers(self.lines[2])
        expected = [
            ("Ambo", 4),            # L,L
            ("florentes", 8),       # L,L,L
            ("genus", 9),           # S,S
            ("insuperabile", 324),  # L,S,S,L,S,S
            ("bello", 4),           # L,L
        ]
        assert pairs == expected

    # Line 8: uirtusque (no que_fwd — not SY, not before vowel)
    def test_line_8_uirtusque_no_que_fwd(self):
        pairs = line_numbers(self.lines[7])
        # uirtusque has sy="2T3A3b", mf="" → L,L,S, no que_fwd
        uirtusque = [p for p in pairs if p[0] == "uirtusque"]
        assert uirtusque == [("uirtusque", 12)]  # L,L,S = 2·2·3

    # Line 10: cuique gets que_fwd (has mf="SY")
    def test_line_10_cuique_que_fwd(self):
        pairs = line_numbers(self.lines[9])
        cuique = [p for p in pairs if p[0] == "cuique"]
        exorsa = [p for p in pairs if p[0] == "exorsa"]
        assert cuique == [("cuique", 2)]       # L (que_fwd, no E)
        assert exorsa == [("exorsa", 132)]     # Q,L,L,S = 11·2·2·3

    # Line 13: atque uiri — no que_fwd, no elision (u is consonantal)
    def test_line_13_atque_no_elision(self):
        pairs = line_numbers(self.lines[12])
        atque = [p for p in pairs if p[0] == "atque"]
        assert atque == [("atque", 6)]  # L,S = 2·3, no E, no que_fwd

    # Line 3: insuperabile — long word with mixed syllables
    def test_line_3_insuperabile(self):
        pairs = line_numbers(self.lines[2])
        insuperabile = [p for p in pairs if p[0] == "insuperabile"]
        assert insuperabile == [("insuperabile", 324)]  # L,S,S,L,S,S


# ---------------------------------------------------------------------------
# line_to_numbers
# ---------------------------------------------------------------------------

class TestLineToNumbers:
    @pytest.fixture(autouse=True)
    def load(self):
        self.lines = load_cento_lines()

    def test_line_1_returns_numbers(self):
        nums = [w["number"] for w in process_line(self.lines[0])]
        assert nums == [90, 2, 18, 4, 396, 4]

    def test_line_2_returns_numbers(self):
        nums = [w["number"] for w in process_line(self.lines[1])]
        assert nums == [10, 18, 10, 8, 36, 4]

    def test_line_3_returns_numbers(self):
        nums = [w["number"] for w in process_line(self.lines[2])]
        assert nums == [4, 8, 9, 324, 4]

    def test_returns_list_of_ints(self):
        """All values should be int (including 0 for lost words)."""
        for line in self.lines[:20]:
            for w in process_line(line):
                assert isinstance(w["number"], int)


# ---------------------------------------------------------------------------
# corpus_to_string
# ---------------------------------------------------------------------------

class TestCorpusToString:
    def test_basic(self):
        lines = load_cento_lines()
        sentences_path = Path(__file__).parent.parent / "processed" / "question" / "cento_nuptialis_sentences.txt"
        result = corpus_to_string(lines[:5], sentences_path)
        # Should contain numbers, <EOL>, and <EOS>
        assert "<EOL>" in result
        assert "<EOS>" in result
        # First word number should be 90 (Accipite: L,S,S,E)
        assert result.startswith("90")

    def test_lost_words_omitted(self):
        """Lines with PE targets should not produce None in output."""
        lines = load_cento_lines()
        sentences_path = Path(__file__).parent.parent / "processed" / "question" / "cento_nuptialis_sentences.txt"
        result = corpus_to_string(lines, sentences_path)
        assert "None" not in result

    def test_line_1_content(self):
        """First line should produce 90 2 18 4 396 4 <EOL>."""
        lines = load_cento_lines()
        sentences_path = Path(__file__).parent.parent / "processed" / "question" / "cento_nuptialis_sentences.txt"
        result = corpus_to_string(lines[:1], sentences_path)
        # The first line's numbers, followed by <EOL>
        assert result.startswith("90 2 18 4 396 4 <EOL>")

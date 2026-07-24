"""Tests for hexameter extraction."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_hexameter import is_valid_hexameter, find_hexameter_stretches
from xml_utils import clean_xml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_xml(path: Path) -> list:
    """Parse an XML file and return list of line tags."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    content = clean_xml(content)
    soup = BeautifulSoup(content, "xml")
    return soup.find_all("line")


# ---------------------------------------------------------------------------
# is_valid_hexameter
# ---------------------------------------------------------------------------

class TestIsValidHexameter:
    """Test hexameter line validation."""

    @pytest.fixture(autouse=True)
    def load(self):
        xml_path = Path(__file__).parent.parent / "raw" / "ausonius" / "mosella.xml"
        self.lines = _parse_xml(xml_path)

    def test_valid_hexameter(self):
        # Mosella line 1 should be valid hexameter
        line = self.lines[0]
        assert line.get("meter") == "H"
        assert is_valid_hexameter(line)

    def test_not_scanned_rejected(self):
        # Find a line with pattern="not scanned"
        for line in self.lines:
            if line.get("pattern") == "not scanned":
                assert not is_valid_hexameter(line)
                return
        pytest.skip("No 'not scanned' lines found in mosella")

    def test_no_meter_rejected(self):
        # Find a line without meter="H"
        for line in self.lines:
            if line.get("meter") != "H":
                assert not is_valid_hexameter(line)
                return
        pytest.skip("All lines in mosella are meter=H")

    def test_no_words_rejected(self):
        """A line with no words should be rejected."""
        soup = BeautifulSoup('<line meter="H" pattern="DDSS"></line>', "xml")
        line = soup.find("line")
        assert not is_valid_hexameter(line)

    def test_no_sy_rejected(self):
        """A line where no words have sy= should be rejected."""
        soup = BeautifulSoup('<line meter="H" pattern="DDSS"><word>test</word></line>', "xml")
        line = soup.find("line")
        assert not is_valid_hexameter(line)

    def test_words_with_sy_accepted(self):
        """A line with words that have sy= should be accepted."""
        soup = BeautifulSoup('<line meter="H" pattern="DDSS"><word sy="1A">test</word></line>', "xml")
        line = soup.find("line")
        assert is_valid_hexameter(line)


# ---------------------------------------------------------------------------
# find_hexameter_stretches
# ---------------------------------------------------------------------------

class TestFindHexameterStretches:
    """Test continuous hexameter stretch detection."""

    _name_counter = 0

    def _make_line(self, meter: str = "H", pattern: str = "DDSS", has_sy: bool = True):
        """Create a line tag for testing (with name= so it's a verse line)."""
        TestFindHexameterStretches._name_counter += 1
        name = TestFindHexameterStretches._name_counter
        sy = ' sy="1A"' if has_sy else ""
        soup = BeautifulSoup(
            f'<line name="{name}" meter="{meter}" pattern="{pattern}"><word{sy}>x</word></line>',
            "xml",
        )
        return soup.find("line")

    def test_single_stretch(self):
        lines = [self._make_line() for _ in range(15)]
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 1
        assert len(stretches[0]) == 15

    def test_two_stretches(self):
        lines = [self._make_line() for _ in range(12)]
        lines.append(self._make_line(meter="P"))  # break
        lines.extend([self._make_line() for _ in range(10)])
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 2
        assert len(stretches[0]) == 12
        assert len(stretches[1]) == 10

    def test_too_short_rejected(self):
        lines = [self._make_line() for _ in range(5)]
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 0

    def test_boundary_exactly_10(self):
        lines = [self._make_line() for _ in range(10)]
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 1
        assert len(stretches[0]) == 10

    def test_boundary_9_rejected(self):
        lines = [self._make_line() for _ in range(9)]
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 0

    def test_lacunose_not_scanned_keeps_stretch_alive(self):
        """meter=H lines with pattern='not scanned' keep the stretch alive
        but are stripped from the output."""
        lines = [self._make_line() for _ in range(12)]
        lines.append(self._make_line(pattern="not scanned"))  # lacuna, meter=H
        lines.extend([self._make_line() for _ in range(12)])
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 1
        assert len(stretches[0]) == 24  # lacuna stripped

    def test_lacunose_no_sy_keeps_stretch_alive(self):
        """meter=H lines without sy= keep the stretch alive
        but are stripped from the output."""
        lines = [self._make_line() for _ in range(12)]
        lines.append(self._make_line(has_sy=False))  # lacuna, meter=H
        lines.extend([self._make_line() for _ in range(12)])
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 1
        assert len(stretches[0]) == 24  # lacuna stripped

    def test_elegiac_pattern(self):
        """Elegiac couplets (H,P,H,P) should not form stretches."""
        lines = []
        for _ in range(10):
            lines.append(self._make_line(meter="H"))
            lines.append(self._make_line(meter="P"))
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 0

    def test_non_verse_elements_skipped(self):
        """Elements without name= are structural markers, not breaks."""
        lines = [self._make_line() for _ in range(5)]
        # Insert a structural marker (no name attribute)
        soup = BeautifulSoup('<line meter=""><word>x</word></line>', "xml")
        lines.append(soup.find("line"))
        lines.extend([self._make_line() for _ in range(5)])
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 1
        assert len(stretches[0]) == 10

    def test_non_hexameter_verse_breaks_stretch(self):
        """A verse line with meter!=H (e.g. pentameter) breaks a stretch."""
        lines = [self._make_line() for _ in range(12)]
        lines.append(self._make_line(meter="X"))  # verse line, not hexameter
        lines.extend([self._make_line() for _ in range(12)])
        stretches = find_hexameter_stretches(lines, min_stretch=10)
        assert len(stretches) == 2

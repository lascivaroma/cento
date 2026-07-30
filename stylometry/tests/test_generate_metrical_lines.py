import importlib.util
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "generate_metrical_lines.py"
SPEC = importlib.util.spec_from_file_location("generate_metrical_lines", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProcessLinesToFileTests(unittest.TestCase):
    """Tests for process_lines_to_file."""

    def test_single_line_produces_eol(self) -> None:
        """Each sentence should end with <EOL>."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = Path(f.name)

        try:
            count = MODULE.process_lines_to_file(
                [["6", "18", "6", "4"]],
                path,
            )
            self.assertEqual(count, 1)
            lines = path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].endswith("<EOL>"))
            self.assertEqual(lines[0], "6 18 6 4 <EOL>")
        finally:
            path.unlink()

    def test_multiple_lines_each_end_with_eol(self) -> None:
        """Every sentence should end with <EOL>, no <EOS> tokens."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = Path(f.name)

        try:
            count = MODULE.process_lines_to_file(
                [["6", "18"], ["36", "4"], ["18", "10", "10"]],
                path,
            )
            self.assertEqual(count, 3)
            lines = path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 3)
            for line in lines:
                self.assertTrue(line.endswith("<EOL>"))
                self.assertNotIn("<EOS>", line)
        finally:
            path.unlink()

    def test_empty_line_skipped(self) -> None:
        """Empty token lists should be skipped."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = Path(f.name)

        try:
            count = MODULE.process_lines_to_file(
                [["6", "18"], [], ["36", "4"]],
                path,
            )
            # count reflects input length, but empty lines produce no output
            self.assertEqual(count, 3)
            lines = path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2)
        finally:
            path.unlink()


class NormTokenTests(unittest.TestCase):
    """Tests for _norm_token normalisation."""

    def test_strips_diacritics(self) -> None:
        self.assertEqual(MODULE._norm_token("arma"), "arma")

    def test_lowercase(self) -> None:
        self.assertEqual(MODULE._norm_token("ArMa"), "arma")


if __name__ == "__main__":
    unittest.main()

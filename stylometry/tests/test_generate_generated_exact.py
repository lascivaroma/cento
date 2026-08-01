import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "generate_generated_exact.py"
SPEC = importlib.util.spec_from_file_location("generate_generated_exact", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PosMappingTests(unittest.TestCase):
    def test_load_pos_mapping(self) -> None:
        path = REPO_ROOT / "pos_mapping.tsv"
        mapping = MODULE.load_pos_mapping(path)
        self.assertIn("NOMcom", mapping)
        self.assertEqual(mapping["NOMcom"], ("NOUN", True))
        self.assertEqual(mapping["PRE"], ("ADP", False))

    def test_content_words_are_masked(self) -> None:
        path = REPO_ROOT / "pos_mapping.tsv"
        mapping = MODULE.load_pos_mapping(path)
        for pos in ["NOMcom", "NOMpro", "VER", "ADJqua"]:
            _, should_mask = mapping[pos]
            self.assertTrue(should_mask, f"{pos} should be masked")

    def test_function_words_are_not_masked(self) -> None:
        path = REPO_ROOT / "pos_mapping.tsv"
        mapping = MODULE.load_pos_mapping(path)
        for pos in ["PRE", "CONcoo", "CONsub", "PROper", "PROdem"]:
            _, should_mask = mapping[pos]
            self.assertFalse(should_mask, f"{pos} should not be masked")


class StripParensTests(unittest.TestCase):
    def test_removes_parentheses(self) -> None:
        self.assertEqual(MODULE.strip_parens("hello (world) test"), "hello world test")

    def test_removes_brackets(self) -> None:
        self.assertEqual(MODULE.strip_parens("hello [world] test"), "hello world test")

    def test_handles_unmatched(self) -> None:
        self.assertEqual(MODULE.strip_parens("hello (world test"), "hello world test")

    def test_no_parens(self) -> None:
        self.assertEqual(MODULE.strip_parens("hello world"), "hello world")


class NormTokenTests(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(MODULE._norm_token("Arma"), "arma")

    def test_strips_punctuation(self) -> None:
        self.assertEqual(MODULE._norm_token("arma,"), "arma")

    def test_strips_diacritics(self) -> None:
        self.assertEqual(MODULE._norm_token("arma"), "arma")


class WriteLinesTests(unittest.TestCase):
    def test_write_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            MODULE.write_lines(path, ["line1", "line2", "line3"])
            lines = path.read_text().strip().split("\n")
            self.assertEqual(lines, ["line1", "line2", "line3"])


class WriteMetricalLinesTests(unittest.TestCase):
    def test_write_metrical_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            MODULE.write_metrical_lines(path, [["2", "18", "4"], ["36", "54"]])
            lines = path.read_text().strip().split("\n")
            self.assertEqual(lines, ["2 18 4 <EOL>", "36 54 <EOL>"])

    def test_skips_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            MODULE.write_metrical_lines(path, [["2", "18"], []])
            lines = path.read_text().strip().split("\n")
            self.assertEqual(lines, ["2 18 <EOL>"])


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "check_segment_positions.py"
SPEC = importlib.util.spec_from_file_location("check_segment_positions", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ExtractTextTests(unittest.TestCase):
    def test_bare_syllables_are_joined_into_words(self) -> None:
        xml = """
        <root>
          <l>
            <s>om</s>
            <s>nis</s>
            <w form="ut"><s>ut</s></w>
          </l>
        </root>
        """
        elem = ET.fromstring(xml)
        self.assertEqual(MODULE.extract_text_from_element(elem), "omnis ut")

    def test_source_excerpt_is_wrapped_with_angle_brackets(self) -> None:
        source = "non absunt; illic saltus ac lustra ferarum"
        segment = "non absunt"
        self.assertEqual(
            MODULE.format_source_entry(source, segment, "urn:cts:latinLit:phi0690.phi003:1.74", 1),
            "A 1.74: <<non absunt>>; illic saltus ac lustra ferarum",
        )

    def test_source_excerpt_can_be_wrapped_in_the_middle_of_the_line(self) -> None:
        source = "hinc Gaetulae urbes, genus insuperabile bello,"
        segment = "genus insuperabile bello"
        self.assertEqual(
            MODULE.format_source_entry(source, segment, "urn:cts:latinLit:phi0690.phi001:1.2", 2),
            "E 1.2: hinc Gaetulae urbes, <<genus insuperabile bello>>,",
        )

    def test_source_label_falls_back_to_source_number(self) -> None:
        self.assertEqual(
            MODULE.format_source_label(None, 2),
            "Source 2",
        )


if __name__ == "__main__":
    unittest.main()

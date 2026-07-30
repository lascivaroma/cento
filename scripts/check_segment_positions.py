#!/usr/bin/env python3
"""Report cento segments that are misplaced relative to their source lines.

The script parses data/gold/cento.xml, looks up each `<seg>` against the PHI
XML files in data/gold/metric, and flags a segment when either:

1. it starts a cento line but does not start the corresponding PHI line, or
2. it is a later segment in the cento line but does start the corresponding PHI
   line (suggesting it was reused from the beginning of its original verse).

The output is written as a plain text report where each cento line is shown with
its own text and the full source line(s) it came from, separated by lines of
`---`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def normalize_text(text: str) -> str:
    """Lowercase and remove punctuation so we can compare segments robustly."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def extract_text_from_element(elem: ET.Element) -> str:
    """Return the surface text of a segment or verse as plain word forms."""
    parts: List[str] = []
    current_syllables: List[str] = []

    def local_name(tag: str) -> str:
        return tag.split("}", 1)[1] if "}" in tag else tag

    def flush_current_word() -> None:
        nonlocal current_syllables
        if current_syllables:
            parts.append("".join(current_syllables))
            current_syllables = []

    def visit(node: ET.Element) -> None:
        nonlocal current_syllables
        name = local_name(node.tag)
        if name == "w":
            form = node.attrib.get("form", "")
            if form:
                flush_current_word()
                parts.append(form)
                return
            for child in node:
                visit(child)
            flush_current_word()
            return

        if name == "s":
            if node.text and node.text.strip():
                current_syllables.append(node.text.strip())
            return

        if name == "pc":
            flush_current_word()
            if node.text and node.text.strip():
                parts.append(node.text.strip())
            return

        for child in node:
            visit(child)
        if name != "w":
            flush_current_word()

    visit(elem)
    flush_current_word()
    return " ".join(part for part in parts if part)


def format_source_label(source_urn: str | None, source_index: int) -> str:
    """Render a human-readable source label from a CTS URN."""
    if source_urn:
        match = re.search(r"phi0?(\d+):(.*)", source_urn)
        if match:
            work_code = {1: "E", 2: "G", 3: "A"}.get(int(match.group(1)), match.group(1))
            reference = match.group(2)
            return f"{work_code} {reference}"
    return f"Source {source_index}"


def format_source_entry(source_text: str, segment_text: str, source_urn: str | None, source_index: int) -> str:
    """Return the displayed source line with the matching excerpt wrapped in << >>."""
    label = format_source_label(source_urn, source_index)
    if not source_text:
        return f"{label}: (no source line found)"

    segment_words = re.findall(r"[A-Za-z0-9]+", segment_text.lower())
    if not segment_words:
        return f"{label}: {source_text}"

    source_matches = list(re.finditer(r"[A-Za-z0-9]+", source_text))
    if not source_matches:
        return f"{label}: {source_text}"

    source_words = [match.group(0).lower() for match in source_matches]
    segment_length = len(segment_words)

    match_span: Tuple[int, int] | None = None
    for start_idx in range(len(source_words) - segment_length + 1):
        candidate_words = source_words[start_idx : start_idx + segment_length]
        mismatches = sum(1 for left, right in zip(candidate_words, segment_words) if left != right)
        if mismatches <= 1:
            start_char = source_matches[start_idx].start()
            end_char = source_matches[start_idx + segment_length - 1].end()
            match_span = (start_char, end_char)
            break

    if match_span is None:
        return f"{label}: {source_text}"

    start_char, end_char = match_span
    excerpt = source_text[start_char:end_char]
    return (
        f"{label}: {source_text[:start_char]}"
        f"<<{excerpt}>>{source_text[end_char:]}"
    )


def load_source_lines(metric_dir: Path) -> Dict[str, str]:
    """Load all PHI verse lines from the metric XML files into a dict by URN."""
    source_lines: Dict[str, str] = {}
    for xml_path in sorted(metric_dir.glob("*.xml")):
        if xml_path.name.endswith("-annotated.xml"):
            continue
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for line_elem in root.findall(".//tei:l", NS):
            urn = line_elem.attrib.get("n")
            if urn:
                source_lines[urn] = extract_text_from_element(line_elem)
    return source_lines


def iter_cento_lines(cento_path: Path) -> List[Tuple[int, str, List[Tuple[str, str]]]]:
    """Yield (cento_line_num, cento_text, [(source_urn, segment_text), ...])."""
    tree = ET.parse(cento_path)
    root = tree.getroot()
    rows: List[Tuple[int, str, List[Tuple[str, str]]]] = []

    for line_elem in root.findall(".//tei:l", NS):
        line_num = line_elem.attrib.get("n")
        if line_num is None:
            continue
        try:
            line_num_int = int(line_num)
        except ValueError:
            continue

        segments: List[Tuple[str, str]] = []
        for seg in line_elem.findall("tei:seg", NS):
            source_urn = seg.attrib.get("source", "")
            if not source_urn:
                continue
            segments.append((source_urn, extract_text_from_element(seg)))

        rows.append((line_num_int, extract_text_from_element(line_elem), segments))

    return rows


def build_report_lines(
    cento_path: Path,
    source_lines: Dict[str, str],
) -> List[str]:
    """Build the text report for all cento lines."""
    blocks: List[str] = []
    for line_num, cento_text, segments in iter_cento_lines(cento_path):
        issues: List[str] = []
        source_entries: List[str] = []

        for idx, (source_urn, segment_text) in enumerate(segments, start=1):
            source_text = source_lines.get(source_urn, "")
            source_norm = normalize_text(source_text)
            segment_norm = normalize_text(segment_text)
            starts_source_line = bool(source_norm and source_norm.startswith(segment_norm))

            if idx == 1 and not starts_source_line:
                issues.append(f"segment {idx} does not start the PHI line")
            elif idx > 1 and starts_source_line:
                issues.append(f"segment {idx} looks out-of-position")

            source_entries.append(
                format_source_entry(source_text, segment_text, source_urn, idx)
            )

        while len(source_entries) < 2:
            source_entries.append(f"Source {len(source_entries) + 1}: —")

        if issues:
            blocks.append(f"[*] Cento line {line_num}: {cento_text}")
            blocks.extend(f"[*] {entry}" for entry in source_entries)
        else:
            blocks.append(f"Cento line {line_num}: {cento_text}")
            blocks.extend(source_entries)
        blocks.append("---")

    return blocks


def write_report(output_path: Path, report_lines: List[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines))
        if report_lines and report_lines[-1] != "":
            handle.write("\n")


def resolve_path(path_value: str, repo_root: Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cento",
        default="data/gold/cento.xml",
        help="Path to the cento XML file (default: data/gold/cento.xml)",
    )
    parser.add_argument(
        "--metric-dir",
        default="data/gold/metric",
        help="Directory containing the PHI XML files (default: data/gold/metric)",
    )
    parser.add_argument(
        "--output",
        default="stylometry/cento_segments.txt",
        help="Where to write the report (default: stylometry/cento_segments.txt)",
    )
    args = parser.parse_args()

    cento_path = resolve_path(args.cento, repo_root)
    metric_dir = resolve_path(args.metric_dir, repo_root)
    output_path = resolve_path(args.output, repo_root)

    if not cento_path.exists():
        print(f"Cento file not found: {cento_path}", file=sys.stderr)
        return 1
    if not metric_dir.exists():
        print(f"Metric directory not found: {metric_dir}", file=sys.stderr)
        return 1

    source_lines = load_source_lines(metric_dir)
    report_lines = build_report_lines(cento_path, source_lines)
    write_report(output_path, report_lines)

    print(f"Wrote {len(report_lines) // 3} blocks to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

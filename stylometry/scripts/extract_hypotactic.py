#!/usr/bin/env python3
"""Extract individual poem JSON files from hypotactic author files.

Reads author-level JSON files and writes one smaller JSON file per poem
into raw/vergil/ or raw/background/.

Usage:
    python extract_hypotactic.py /path/to/hypotactic_data_6_17_2025
"""

from __future__ import annotations

import json
from pathlib import Path

from corpus_utils import find_poems_in_doc, line_meter

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"

# Authors → target directory: {target_dir: {filename: [work_names]}}
AUTHORS = {
    "vergil": {
        "vergil": ["Aeneid", "Georgics"],
    },
    "background": {
        "ovid": ["Metamorphoses"],
        "lucan": ["Bellum Civile"],
        "silius": ["Punica"],
        "flaccus": ["Argonautica"],
    },
}


def _safe_name(s: str) -> str:
    """Lowercase, replace spaces/special chars with underscores."""
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def extract_poem(ctx: dict, lines: list[dict], out_dir: Path) -> Path:
    """Write a single poem as a small JSON file.

    Args:
        ctx: Context dict with author, work, book, poem_num keys.
        lines: List of line dicts from the source JSON.
        out_dir: Directory to write the output JSON file.

    Returns:
        Path to the written JSON file.
    """
    author = _safe_name(ctx.get("author", "unknown"))
    work = _safe_name(ctx.get("work", "unknown"))
    book = ctx.get("book", "")
    book_name = _safe_name(str(book)) if book else ""

    # Strip work name prefix from book to avoid doubling (e.g. "aeneid_aeneid_1" → "aeneid_1")
    if book_name.startswith(work + "_"):
        book_name = book_name[len(work) + 1:]

    if book_name:
        name = f"{author}_{work}_{book_name}"
    else:
        name = f"{author}_{work}"

    out_path = out_dir / f"{name}.json"

    # Filter to hexameter lines only
    hex_lines = [ln for ln in lines if line_meter(ln) == "hexameter"]

    data = {
        "author": ctx.get("author"),
        "work": ctx.get("work"),
        "book": book,
        "poem_num": ctx.get("poem_num"),
        "meter": "hexameter",
        "line_count": len(hex_lines),
        "lines": hex_lines,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return out_path


def main() -> int:
    """Extract poems from author JSON files into raw/vergil/ and raw/background/.

    Expects author-level JSON files in raw/hypotactic_source/ (one-time copy).
    After extraction, the source directory can be deleted to save space.

    Returns:
        0 on success, 1 if the source directory is missing.
    """
    source_dir = Path(__file__).resolve().parent.parent / "raw" / "hypotactic_source"
    if not source_dir.exists():
        print(f"ERROR: {source_dir} not found.")
        print("Copy the needed author JSONs there first:")
        print("  vergil.json, ovid.json, lucan.json, silius.json, flaccus.json")
        return 1

    for target_dir, author_map in AUTHORS.items():
        out_dir = RAW_DIR / target_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        for filename, works_list in author_map.items():
            json_path = source_dir / f"{filename}.json"
            if not json_path.exists():
                print(f"SKIP: {json_path} not found")
                continue

            with open(json_path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            for ctx, lines in find_poems_in_doc(doc):
                if ctx.get("work") not in works_list:
                    continue
                path = extract_poem(ctx, lines, out_dir)
                print(f"  {path.name} ({ctx.get('work')} {ctx.get('book')}): "
                      f"{sum(1 for ln in lines if line_meter(ln) == 'hexameter')} hex lines")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared extraction and output utilities for ``preprocess.py`` and ``preprocess_plays.py``.

This module provides functions for:

* Traversing JSON corpus documents and extracting poem/play metadata.
* Generating metronome strings from syllable-level data.
* Writing ``.txt`` and ``.json`` sidecar files for each poem or play chunk.

Typical usage::

    from libs.corpus_utils import find_poems_in_doc, write_poem_sidecar

    for ctx, lines in find_poems_in_doc(doc):
        write_poem_sidecar(ctx, lines, out_dir, source_file)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from naming import make_name

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Keys that may hold the line list inside a poem dict.
LINE_KEYS: Tuple[str, ...] = ("lines", "poem content", "poem_content", "content", "text")

#: Metadata keys extracted from poem dicts when present.
POEM_META_KEYS: Tuple[str, ...] = ("poem number", "poem title", "poem metre", "poem meter")


# ---------------------------------------------------------------------------
# Speaker detection
# ---------------------------------------------------------------------------

def work_has_speakers(lines: List[Dict[str, Any]], sample: int = 0) -> bool:
    """Check whether a work's lines contain speaker annotations.

    Scans lines for non-blank speaker fields in their segments.  By default
    (*sample*=0) checks ALL lines.  Set *sample* to a positive integer to
    limit checking to the first N lines (faster but may miss speakers in
    works with long prologues).

    This is used to distinguish plays (which have speakers) from standard
    poems (which do not).

    Args:
        lines: Line objects from a poem or play.
        sample: Number of leading lines to inspect (0 = all lines).

    Returns:
        True if any inspected line has a non-blank speaker in its first
        segment.
    """
    if sample > 0:
        lines = lines[:sample]
    for line in lines:
        segs = line.get("segments") or line.get("segment")
        if isinstance(segs, list) and segs:
            sp = segs[0].get("speaker")
            if sp and str(sp).strip():
                return True
    return False


# ---------------------------------------------------------------------------
# Poem extraction
# ---------------------------------------------------------------------------

def extract_lines(poem: Any) -> Optional[List[Dict[str, Any]]]:
    """Return the line list from a poem dict.

    Args:
        poem: A dict that may contain a line list under one of :data:`LINE_KEYS`.

    Returns:
        The list of line objects, or ``None`` if not found.
    """
    if not isinstance(poem, dict):
        return None
    for key in LINE_KEYS:
        if key in poem and isinstance(poem[key], list):
            return poem[key]
    return None


def extract_meta(poem: Dict[str, Any]) -> Dict[str, Any]:
    """Pull known metadata fields from a poem dict into a flat dict.

    Args:
        poem: A poem dict from the JSON corpus.

    Returns:
        A flat dict containing the extracted metadata.
    """
    meta: Dict[str, Any] = {}
    for key in POEM_META_KEYS:
        val = poem.get(key)
        if val is not None and str(val).strip():
            meta[key] = val
    if "poem number" in meta:
        raw = str(meta["poem number"]).strip()
        raw = raw.replace("/", "_")
        try:
            meta["poem number"] = int(raw)
        except (ValueError, TypeError):
            meta["poem number"] = raw
    return meta


def find_poems_in_doc(
    doc: Any,
) -> Iterable[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """Yield ``(context, lines)`` for every poem found in a JSON corpus document.

    The expected structure is one of::

        doc[author][work][book]["poems"] → list of poem dicts
        doc[author][work][book] → list of poem dicts
        doc[author][work] → list of poem dicts

    When ``book_key`` is ``"poems"`` and the work-level key ends with a
    number (e.g. ``"Elegies 1"``), the number is extracted as the *book*
    identifier and the remainder becomes the *work* name.

    Each yielded ``context`` dict contains:

    * ``author`` — author name
    * ``work`` — work name
    * ``book`` — book identifier (or ``None``)
    * ``poem_num`` — poem number from metadata or positional index
    * ``meter`` — poem-level meter from metadata (when available)
    * ``total_books`` — total number of books in this work
    * ``total_poems_in_book`` — total number of poems in this book

    Args:
        doc: A parsed JSON corpus document.

    Yields:
        Tuples of ``(context_dict, line_list)``.
    """
    if not isinstance(doc, dict):
        return

    for author, works in doc.items():
        if not isinstance(works, dict):
            continue
        for work, books in works.items():
            if isinstance(books, dict):
                total_books: int = len(books)
                for book_key, book_val in books.items():
                    if book_key == "poems":
                        _m = re.search(r"^(.*?)(\d+)$", work)
                        if _m:
                            base_work, book_num = _m.group(1).strip(), _m.group(2)
                            yield from _yield_from_container(
                                author, base_work, book_num, book_val, total_books
                            )
                        else:
                            yield from _yield_from_container(
                                author, work, None, book_val, total_books
                            )
                    else:
                        yield from _yield_from_container(
                            author, work, book_key, book_val, total_books
                        )
            elif isinstance(books, list):
                yield from _yield_from_container(author, work, None, books, 1)


def _yield_from_container(
    author: str,
    work: str,
    book_key: Optional[str],
    book_val: Any,
    total_books: int,
) -> Iterable[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """Yield poems from a book-level container (dict with ``"poems"`` key or a list).

    Args:
        author: Author name.
        work: Work name.
        book_key: Book identifier, or ``None`` if not applicable.
        book_val: Either a dict with a ``"poems"`` key or a list of poem dicts.
        total_books: Total number of books in this work.

    Yields:
        Tuples of ``(context_dict, line_list)``.
    """
    poems: Optional[List[Any]] = None

    if isinstance(book_val, dict) and isinstance(book_val.get("poems"), list):
        poems = book_val["poems"]
    elif isinstance(book_val, list):
        poems = book_val

    if poems is None:
        return

    total_poems: int = len(poems)

    for idx, poem in enumerate(poems, start=1):
        lines = extract_lines(poem)
        if lines is None:
            continue

        meta = extract_meta(poem) if isinstance(poem, dict) else {}

        poem_num = meta.get("poem number")
        if poem_num is None:
            poem_num = idx

        ctx: Dict[str, Any] = {
            "author": author,
            "work": work,
            "book": book_key,
            "poem_num": poem_num,
            "total_books": total_books,
            "total_poems_in_book": total_poems,
        }
        if "poem metre" in meta:
            ctx["meter"] = meta["poem metre"]
        elif "poem meter" in meta:
            ctx["meter"] = meta["poem meter"]

        yield ctx, lines


# ---------------------------------------------------------------------------
# Line-level helpers
# ---------------------------------------------------------------------------

def line_meter(line: Dict[str, Any]) -> str:
    """Get the meter of a line, normalised to lowercase.

    Args:
        line: A line object from the corpus.

    Returns:
        The meter string (e.g. ``"ia6"``, ``"hexameter"``), or ``""``.
    """
    _m = line.get("metre") or line.get("meter") or ""
    return str(_m).strip().lower()


def line_speaker(line: Dict[str, Any]) -> str:
    """Get the speaker from a line's first segment.

    Args:
        line: A line object from the corpus.

    Returns:
        The speaker name, or ``""`` if not present.
    """
    segs = line.get("segments") or line.get("segment")
    if isinstance(segs, list) and segs:
        sp = segs[0].get("speaker")
        if sp:
            return str(sp).strip()
    return ""


def line_text(line: Dict[str, Any]) -> str:
    """Extract the readable text from a line object.

    Tries, in order: ``text`` field, ``words`` list, ``segments`` → words,
    ``line`` / ``line text`` fallback fields.

    Args:
        line: A line object from the corpus.

    Returns:
        The reconstructed line text.
    """
    if isinstance(line.get("text"), str):
        # Collapse any embedded newlines / runs of whitespace (some corpus
        # line objects store the text field with one token per line).
        return re.sub(r"\s+", " ", line["text"]).strip()

    w = line.get("words") or line.get("word")
    if isinstance(w, list) and w:
        return re.sub(
            r"\s+",
            " ",
            " ".join(
                str(t.get("text") if isinstance(t, dict) else t) for t in w
            ),
        ).strip()

    segs = line.get("segments") or line.get("segment")
    if isinstance(segs, list) and segs:
        parts: List[str] = []
        for seg in segs:
            if isinstance(seg, dict):
                words = seg.get("words") or seg.get("tokens") or []
                if isinstance(words, list):
                    parts.append(
                        re.sub(
                            r"\s+",
                            " ",
                            " ".join(
                                str(ww.get("text") if isinstance(ww, dict) else ww)
                                for ww in words
                            ),
                        ).strip()
                    )
        if parts:
            return " ".join(p for p in parts if p)

    return re.sub(r"\s+", " ", line.get("line") or line.get("line text") or "").strip()


# ---------------------------------------------------------------------------
# Metronome generation
# ---------------------------------------------------------------------------

def syllable_symbol(syllable: Any) -> str:
    """Map a syllable dict to a metronome symbol.

    Args:
        syllable: A syllable dict with a ``length`` or ``weight`` field.

    Returns:
        ``"S"`` for long, ``"w"`` for short, ``""`` for elided/other.
    """
    if not isinstance(syllable, dict):
        return ""
    length = syllable.get("length") or syllable.get("weight") or ""
    length = str(length).strip().lower()
    if length.startswith("l"):
        return "S"
    if length.startswith("s"):
        return "w"
    return ""


def word_metronome(word: Any) -> str:
    """Build the metronome string for a single word.

    Args:
        word: A word dict with a ``syllables`` or ``sylls`` list.

    Returns:
        Metronome string (e.g. ``"SwS"``), or ``""`` if no syllables.
    """
    if not isinstance(word, dict):
        return ""
    syllables = word.get("syllables") or word.get("sylls") or []
    if not isinstance(syllables, list):
        return ""
    return "".join(syllable_symbol(s) for s in syllables if syllable_symbol(s))


def line_metronome_str(line: Dict[str, Any]) -> str:
    """Build the metronome string for a single line.

    Words are joined by ``'.'``.  Primary path is ``segments → words``;
    falls back to a top-level ``words`` list.

    Args:
        line: A line object from the corpus.

    Returns:
        Metronome string (e.g. ``"SwS.wS"``), or ``""``.
    """
    words: List[str] = []

    segs = line.get("segments") or line.get("segment")
    if isinstance(segs, list):
        for seg in segs:
            if isinstance(seg, dict):
                for word in seg.get("words") or seg.get("tokens") or []:
                    code = word_metronome(word)
                    if code:
                        words.append(code)

    if not words:
        fallback = line.get("words") or line.get("word")
        if isinstance(fallback, list):
            for word in fallback:
                code = word_metronome(word)
                if code:
                    words.append(code)

    return ".".join(words)


def lines_metronome(lines: List[Dict[str, Any]]) -> str:
    """Build the full metronome string for a list of lines.

    Line codes are joined by ``'|'`` and terminated with a trailing ``'|'``.

    Args:
        lines: Line objects from the corpus.

    Returns:
        Full metronome string (e.g. ``"SwS.wS|Sw.w|"``).
    """
    line_codes = [line_metronome_str(line) for line in lines]
    if not line_codes:
        return ""
    return "|".join(line_codes) + "|"


# ---------------------------------------------------------------------------
# Sidecar output
# ---------------------------------------------------------------------------

def write_poem_sidecar(
    ctx: Dict[str, Any],
    lines: List[Dict[str, Any]],
    out_dir: Path,
    source_file: str,
    speaker: Optional[str] = None,
    is_play: bool = False,
    section: Optional[int] = None,
) -> Path:
    """Write ``.txt`` and ``.json`` sidecars for a poem or play chunk.

    The text file contains one line per line object.  The JSON sidecar
    contains metadata (author, work, book, poem_num, name, txt_path,
    line_count, sentence_count, meter, metronome, source_file, and optionally speaker).

    Args:
        ctx: Context dict with ``author``, ``work``, ``book``, ``poem_num``,
            ``total_books``, ``total_poems_in_book``, and optionally ``meter``.
        lines: Line objects to write.
        out_dir: Output directory.
        source_file: Path to the source JSON file (recorded in the sidecar).
        speaker: Optional speaker name (used for play chunks).

    Returns:
        Path to the written ``.json`` sidecar file.
    """
    author: str = ctx.get("author") or "unknown"
    work: str = ctx.get("work") or ""
    book: str = ctx.get("book") or ""
    poem_num: Any = ctx.get("poem_num")

    name: str = make_name(
        author,
        work,
        book or None,
        poem_num=poem_num,
        is_play=is_play,
        section=section,
        total_books=ctx.get("total_books"),
        total_poems_in_book=ctx.get("total_poems_in_book"),
    )

    txt_path: Path = out_dir / f"{name}.txt"
    written_lines: List[str] = []
    with txt_path.open("w", encoding="utf-8") as tf:
        for ln in lines:
            text = line_text(ln)
            if text.strip():
                tf.write(text + "\n")
                written_lines.append(text)

    meta: Dict[str, Any] = {
        "author": author,
        "work": work,
        "book": book,
        "poem_num": poem_num,
        "name": name,
        "txt_path": txt_path.name,
        "line_count": len(written_lines),
        "sentence_count": ctx.get("sentence_count", 0),
        "meter": ctx.get("meter"),
        "metronome": lines_metronome(lines),
        "source_file": source_file,
    }
    if speaker:
        meta["speaker"] = speaker

    json_path: Path = out_dir / f"{name}.json"
    with json_path.open("w", encoding="utf-8") as jf:
        json.dump(meta, jf, ensure_ascii=False, indent=2)

    return json_path

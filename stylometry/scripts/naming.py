"""Naming conventions for the syntax-reboot pipeline output files.

Generates canonical filenames from author, work, book, and poem-number
components.  The naming logic follows a simple hierarchy::

    author_work                    (always)
    author_work_booknum            (if book is provided)
    author_work_booknum_poemnum    (if book has >1 poem)

For plays, *section* number is used in place of poem number.
"""

from __future__ import annotations

import re
from typing import Any, Optional


def sanitize(name: str) -> str:
    """Lowercase, replace non-alphanumeric with underscores, collapse repeats.

    Args:
        name: Raw name string.

    Returns:
        Sanitised, lowercased name with underscores.
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def concat_words(name: str) -> str:
    """Concatenate multi-word names into a single token.

    Underscores between letters are removed; underscores before digits
    are preserved.

    Examples:
        >>> concat_words("De Re Rustica")
        'dererustica'
        >>> concat_words("Aeneid 1")
        'aeneid_1'

    Args:
        name: Raw name string.

    Returns:
        Concatenated token.
    """
    s = sanitize(name)
    s = re.sub(r"([a-z])(\d)", r"\1_\2", s)
    result: list[str] = []
    for i, ch in enumerate(s):
        if ch == "_" and 0 < i < len(s) - 1:
            prev = s[i - 1]
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if prev.isalpha() and nxt.isalpha():
                continue
        result.append(ch)
    return "".join(result)


def strip_prefix(name: str) -> str:
    """Remove common prefixes like ``ps.`` or ``pseudo-`` from work names.

    Only strips ``pseudo`` when followed by a separator (space, hyphen,
    period, etc.) or when it appears inside a parenthetical annotation
    like ``(pseudo-Tibullus)``.  Does **not** strip ``pseudo`` when it is
    part of a word like ``Pseudolus``.

    Args:
        name: Raw work name.

    Returns:
        Work name with prefix removed.
    """
    name = name.lower()
    name = re.sub(r"\s*[\(\[]\s*(ps\.?|pseudo)[\s._-]+[^\)\]]*[\)\]]?", "", name)
    name = re.sub(r"^(ps\.?|pseudo)[\s._-]+", "", name)
    return name.strip()


def _extract_book_number(book_key: str) -> Optional[str]:
    """Extract the numeric suffix from a book key.

    Args:
        book_key: Book identifier (e.g. ``"Odes 1"``, ``"Argonautica 2"``).

    Returns:
        The numeric suffix, or ``None`` if not found.
    """
    m = re.search(r"(\d+)$", book_key)
    return m.group(1) if m else None


def make_name(
    author: str,
    work: str,
    book: Optional[str],
    poem_num: Optional[Any] = None,
    is_play: bool = False,
    section: Optional[int] = None,
    total_books: Optional[int] = None,
    total_poems_in_book: Optional[int] = None,
) -> str:
    """Generate a canonical filename for a poem or play section.

    Naming convention::

        author_work                    (always)
        author_work_booknum            (if book is provided)
        author_work_booknum_poemnum    (if book has >1 poem)

    For plays, *section* number is used in place of poem number.

    Args:
        author: Author name (e.g. ``"Vergil"``).
        work: Work name (e.g. ``"Aeneid"``).
        book: Book identifier (e.g. ``"Odes 1"``), or ``None`` if no book
            division exists.
        poem_num: Poem number from JSON metadata.
        is_play: If True, use section number instead of poem number.
        section: Section number (for plays).
        total_books: Total number of books in this work (unused).
        total_poems_in_book: Total number of poems in this book.

    Returns:
        Filename string without extension.
    """
    a: str = concat_words(author)
    w: str = concat_words(strip_prefix(work))
    base: str = f"{a}_{w}"

    if is_play:
        return f"{a}_{w}_{section}"

    # No book — include poem number if multiple poems
    if book is None:
        if total_poems_in_book is not None and total_poems_in_book > 1 and poem_num is not None:
            return f"{base}_{poem_num}"
        return base

    # Extract book number from the book key
    book_num: Optional[str] = _extract_book_number(book)

    # Determine if this book has multiple poems
    multi_poem: bool = total_poems_in_book is not None and total_poems_in_book > 1

    if book_num:
        # Book has a number — include it
        base_with_book: str = f"{base}_{book_num}"
        if multi_poem and poem_num is not None:
            return f"{base_with_book}_{poem_num}"
        return base_with_book
    else:
        # Book without a number (e.g. "poems")
        if multi_poem and poem_num is not None:
            return f"{base}_{poem_num}"
        return base

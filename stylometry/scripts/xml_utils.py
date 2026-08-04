#!/usr/bin/env python3
"""Shared XML utilities for Pedecerto files."""


def clean_xml(content: str) -> str:
    """Fix common XML issues in Pedecerto files.

    Removes <division> opening and closing tags while keeping everything
    else (including <line> elements).

    Args:
        content: Raw XML content string.

    Returns:
        Cleaned XML content with division tags removed.
    """
    output_lines = []

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip division opening and closing tags
        if stripped.startswith('<division') or stripped.startswith('</division'):
            continue

        output_lines.append(line)

    return '\n'.join(output_lines)

#!/usr/bin/env python3
"""Shared XML utilities for Pedecerto files."""


def clean_xml(content: str) -> str:
    """
    Fix common XML issues in Pedecerto files.

    Some files contain unescaped < and > characters in attribute values
    (e.g., division title attributes with <emph> tags).

    This function walks the file line by line, removing <division> opening
    and closing tags while keeping everything else (including <line> elements).
    Division opening tags are always on single lines (ending with ">).
    """
    output_lines = []

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip division opening and closing tags
        if stripped.startswith('<division') or stripped.startswith('</division'):
            continue

        output_lines.append(line)

    return '\n'.join(output_lines)

"""Fix malformed `title="..."` attributes in AVSON-epig.xml.

The source data embeds raw, unescaped HTML (e.g. <emph style="...">...</emph>)
inside the `title` attribute of <division> elements, which breaks XML parsing.
This strips the inner tags (keeping their text content) and escapes any
remaining XML-significant characters in the attribute value.
"""
import re
import sys
from xml.sax.saxutils import escape

# Each malformed title is confined to a single line ending in `">`, so match
# greedily to the last `">` on the line (the inner <emph style="..."> tags
# also contain `">` but never at the very end of the line).
TITLE_RE = re.compile(r'title="(.*)">$', re.MULTILINE)

# Matches inner HTML tags like <emph style="font-style:italic"> or </emph>
INNER_TAG_RE = re.compile(r'<[^<>]*>')


def fix_title(match: re.Match) -> str:
    raw_value = match.group(1)
    stripped = INNER_TAG_RE.sub("", raw_value)
    return f'title="{escape(stripped)}">'


def fix_file(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    fixed = TITLE_RE.sub(fix_title, content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(fixed)


def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        print("usage: fix_titles.py FILE [FILE ...]", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        fix_file(path)


if __name__ == "__main__":
    main()

"""Export the Cento Nuptialis as plain text: one line per verse, space-separated word forms, no punctuation."""

import os.path as op
from pycento.data import parse_cento

_ROOT = op.dirname(op.abspath(__file__))
_ALIGNED = op.join(_ROOT, "..", "data", "gold", "cento.xml")
_OUT = op.join(_ROOT, "cento_plain.txt")


def main():
    lines = parse_cento(_ALIGNED)
    with open(_OUT, "w", encoding="utf-8") as fh:
        for line in lines:
            words = [w.text for w in line.words if w.text and w.text.strip()]
            fh.write(" ".join(words) + "\n")
    print(f"Wrote {len(lines)} lines to {_OUT}")


if __name__ == "__main__":
    main()

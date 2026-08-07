#!/usr/bin/env python3
"""Extract unmasked vocabulary from reference corpora.

Scans all masked files in Vergil, Ausonius, and background corpora to
collect words that latin_masking keeps as words (not POS tags).  Writes
the sorted, deduplicated list to scripts/unmasked_vocab.txt.

Run this when the reference masked files change:
    PYTHONPATH=scripts python scripts/extract_unmasked_vocab.py
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REFERENCE_DIRS = [
    BASE_DIR / "lexical_model" / "vergil",
    BASE_DIR / "lexical_model" / "ausonius",
    BASE_DIR / "lexical_model" / "background",
]

OUTPUT_PATH = BASE_DIR / "scripts" / "unmasked_vocab.txt"

POS_TAGS = {
    "ADJ", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
    "PRON", "PROPN", "SCONJ", "VERB", "X",
}


def main() -> int:
    words: set[str] = set()
    file_count = 0

    for d in REFERENCE_DIRS:
        if not d.exists():
            print(f"  Skipping {d} (not found)")
            continue
        for path in sorted(d.glob("*masked*")):
            file_count += 1
            for line in path.read_text(encoding="utf-8").splitlines():
                for tok in line.split():
                    if tok.startswith("<") or tok == "-que":
                        continue
                    if tok in POS_TAGS:
                        continue
                    words.add(tok.lower())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")

    print(f"Scanned {file_count} masked files from {len(REFERENCE_DIRS)} corpora")
    print(f"Wrote {len(words)} unmasked words to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Clean all pipeline output directories, preserving structure and udpipe cache.

Removes all files from processed/, lexical_model/, and metrical_model/
subdirectories, but keeps the directory structure intact and preserves the
UDPipe cache in processed/udpipe_cache/.

Usage:
    python scripts/clean.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Directories to clean (remove contents but keep the directory)
CLEAN_DIRS = [
    BASE_DIR / "processed" / "ausonius",
    BASE_DIR / "processed" / "ausonius_hexameter",
    BASE_DIR / "processed" / "vergil",
    BASE_DIR / "processed" / "aeneid",
    BASE_DIR / "processed" / "background",
    BASE_DIR / "processed" / "question",
    BASE_DIR / "processed" / "question_hexameter",
    BASE_DIR / "lexical_model" / "ausonius",
    BASE_DIR / "lexical_model" / "vergil",
    BASE_DIR / "lexical_model" / "aeneid",
    BASE_DIR / "lexical_model" / "background",
    BASE_DIR / "lexical_model" / "question",
    BASE_DIR / "metrical_model" / "ausonius",
    BASE_DIR / "metrical_model" / "vergil",
    BASE_DIR / "metrical_model" / "aeneid",
    BASE_DIR / "metrical_model" / "background",
    BASE_DIR / "metrical_model" / "question",
]

# Directories to preserve
PRESERVE = {
    BASE_DIR / "processed" / "udpipe_cache",
}


def clean_directory(path: Path) -> int:
    """Remove all files and subdirectories inside path, keeping path itself.

    Returns the number of items removed.
    """
    if not path.exists():
        return 0

    removed = 0
    for item in sorted(path.iterdir()):
        if item.resolve() in {p.resolve() for p in PRESERVE}:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        removed += 1

    return removed


def main() -> None:
    print("Cleaning pipeline outputs...")
    print()

    total = 0
    for d in CLEAN_DIRS:
        n = clean_directory(d)
        if n:
            print(f"  {d.relative_to(BASE_DIR)}: {n} items removed")
        else:
            print(f"  {d.relative_to(BASE_DIR)}: (empty or missing)")
        total += n

    # Ensure directories exist for the pipeline
    for d in CLEAN_DIRS:
        d.mkdir(parents=True, exist_ok=True)

    print()
    print(f"Done. {total} items removed. UDPipe cache preserved.")
    if BASE_DIR / "processed" / "udpipe_cache":
        cache_files = list((BASE_DIR / "processed" / "udpipe_cache").iterdir())
        print(f"  udpipe_cache: {len(cache_files)} cached responses")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compare unmasked-word vocabularies across corpora.

Produces a text report with:
- Vocabulary sizes and overlaps
- Top-30 unmasked words per corpus as a frequency histogram (%)
- Spelling-only-in-one-corpus lists
- Potential near-miss spelling pairs across corpora

Usage:
    PYTHONPATH=scripts python scripts/compare_vocabs.py
    PYTHONPATH=scripts python scripts/compare_vocabs.py -o vocab_report.txt
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

CORPORA: Dict[str, Path] = {
    "generated_exact": BASE_DIR / "lexical_model" / "generated_exact",
    "generated_loose": BASE_DIR / "lexical_model" / "generated_loose",
    "vergil":          BASE_DIR / "lexical_model" / "vergil",
    "ausonius":        BASE_DIR / "lexical_model" / "ausonius",
}

MASKED_GLOB = "*masked*"

# POS tags that may appear unmasked (lowercase functional words kept by the
# masking pipeline).  Anything that is ALL-CAPS or Title-case single word is
# a POS tag and should be excluded.
_POS_TAGS = {
    "ADJ", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM", "PRON",
    "PROPN", "SCONJ", "VERB", "X",
}


def is_pos_tag(tok: str) -> bool:
    """Return True if tok looks like a POS tag rather than a real word."""
    return tok in _POS_TAGS


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect_unmasked(paths: List[Path]) -> Counter:
    """Collect lowercased unmasked word frequencies from masked files."""
    words: Counter = Counter()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            for tok in line.split():
                if tok.startswith("<") or tok == "-que":
                    continue
                if is_pos_tag(tok):
                    continue
                words[tok.lower()] += 1
    return words


def load_corpora() -> Dict[str, Tuple[List[Path], Counter]]:
    """Load all corpora, returning paths and word counters."""
    result: Dict[str, Tuple[List[Path], Counter]] = {}
    for name, directory in CORPORA.items():
        paths = sorted(directory.glob(MASKED_GLOB))
        freq = collect_unmasked(paths) if paths else Counter()
        result[name] = (paths, freq)
    return result


# ---------------------------------------------------------------------------
# Near-miss detection
# ---------------------------------------------------------------------------

def _edit_distance_1(a: str, b: str) -> bool:
    """Return True if a and b differ by exactly one edit (insert/delete/sub)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        return diffs == 1
    # Make a the shorter one
    if len(a) > len(b):
        a, b = b, a
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif not skipped:
            skipped = True
            j += 1  # skip one in b
        else:
            return False
    return True


def find_near_misses(
    vocabs: Dict[str, Set[str]],
    freqs: Dict[str, Counter],
    top_n: int = 30,
) -> List[Tuple[str, str, str, str, int, int]]:
    """Find edit-distance-1 word pairs across different corpora.

    Returns list of (word_a, corpus_a, word_b, corpus_b, count_a, count_b).
    """
    pairs: List[Tuple[str, str, str, str, int, int]] = []
    corp_names = list(vocabs.keys())
    for ca, cb in combinations(corp_names, 2):
        for wa in vocabs[ca]:
            if wa in vocabs[cb]:
                continue  # shared, not a near-miss
            for wb in vocabs[cb]:
                if wa in vocabs[ca] and wb in vocabs[cb] and _edit_distance_1(wa, wb):
                    pairs.append((wa, ca, wb, cb, freqs[ca][wa], freqs[cb][wb]))
    # Sort by combined frequency descending
    pairs.sort(key=lambda t: -(t[4] + t[5]))
    return pairs


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _bar(pct: float, width: int = 30) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def generate_report(corpora: Dict[str, Tuple[List[Path], Counter]]) -> str:
    lines: List[str] = []
    w = lines.append

    freqs = {name: freq for name, (_, freq) in corpora.items()}
    vocabs = {name: set(freq) for name, freq in freqs.items()}

    # ---- Summary ----
    w("=" * 72)
    w("UNMASKED-WORD VOCABULARY COMPARISON")
    w("=" * 72)
    w("")
    w(f"  {'Corpus':<20s} {'Files':>6s} {'Tokens':>10s} {'Vocab':>8s}")
    w(f"  {'-'*20} {'-'*6} {'-'*10} {'-'*8}")
    for name, (paths, freq) in corpora.items():
        total = sum(freq.values())
        w(f"  {name:<20s} {len(paths):>6,} {total:>10,} {len(freq):>8,}")
    w("")

    # ---- Overlaps ----
    names = list(vocabs.keys())
    all_union: Set[str] = set()
    for v in vocabs.values():
        all_union |= v
    w(f"  Union vocabulary: {len(all_union):,}")
    w("")
    w("  Pairwise overlap (shared unmasked words):")
    for ca, cb in combinations(names, 2):
        shared = vocabs[ca] & vocabs[cb]
        w(f"    {ca} ∩ {cb}: {len(shared):,}")
    all_three = vocabs[names[0]] & vocabs[names[1]] & vocabs[names[2]] & vocabs[names[3]]
    w(f"    All four: {len(all_three):,}")
    w("")

    # ---- Top 30 per corpus ----
    w("-" * 72)
    w("TOP 30 UNMASKED WORDS BY FREQUENCY")
    w("-" * 72)

    for name in names:
        freq = freqs[name]
        total = sum(freq.values())
        w("")
        w(f"  {name}  ({len(freq):,} types, {total:,} tokens)")
        w(f"  {'Rank':>4s}  {'Word':<20s} {'Count':>7s} {'Pct':>6s}  {'Histogram'}")
        w(f"  {'----':>4s}  {'----':<20s} {'-----':>7s} {'---':>6s}  {'---------'}")
        for rank, (word, count) in enumerate(freq.most_common(30), 1):
            pct = count / total * 100
            w(f"  {rank:>4d}  {word:<20s} {count:>7,} {pct:>5.1f}%  {_bar(pct)}")
    w("")

    # ---- Words unique to one corpus ----
    w("-" * 72)
    w("WORDS UNIQUE TO ONE CORPUS")
    w("-" * 72)
    for name in names:
        others = set()
        for other_name, v in vocabs.items():
            if other_name != name:
                others |= v
        only_here = vocabs[name] - others
        w("")
        w(f"  {name} only ({len(only_here):,} words):")
        for rank, (word, count) in enumerate(
            sorted(freqs[name].items(), key=lambda t: -t[1])
        ):
            if word not in only_here:
                continue
            if rank > 14:
                break
            w(f"    {word:<20s} {count:>6,}")
    w("")

    # ---- Cross-corpus presence matrix ----
    # Group into generated vs reference for cleaner comparison
    MIN_FREQ = 5  # minimum count to be considered "significant"
    w("-" * 72)
    w(f"SIGNIFICANT WORDS (freq >= {MIN_FREQ}) PRESENT IN SOME CORPORA BUT NOT OTHERS")
    w("-" * 72)
    w("")
    w("  Shows words that reach significance in at least one corpus but are")
    w("  entirely absent from another.  Useful for spotting vocabulary gaps")
    w("  that could bias stylometry.")
    w("")

    # Build merged groups
    gen_names = [n for n in names if n.startswith("generated")]
    ref_names = [n for n in names if not n.startswith("generated")]

    gen_merged: Counter = Counter()
    for n in gen_names:
        gen_merged += freqs[n]

    ref_merged: Counter = Counter()
    for n in ref_names:
        ref_merged += freqs[n]

    gen_vocab = set(gen_merged)
    ref_vocab = set(ref_merged)

    # Words in generated but not reference
    only_gen = {w for w in gen_vocab if w not in ref_vocab and gen_merged[w] >= MIN_FREQ}
    # Words in reference but not generated
    only_ref = {w for w in ref_vocab if w not in gen_vocab and ref_merged[w] >= MIN_FREQ}

    w(f"  Words in GENERATED (exact+loose) but not in REFERENCE (vergil+ausonius)")
    w(f"  ({len(only_gen)} words with freq >= {MIN_FREQ}):")
    w(f"  {'Word':<20s} {'Gen count':>10s}")
    w(f"  {'-'*20} {'-'*10}")
    for word in sorted(only_gen, key=lambda w: -gen_merged[w]):
        w(f"  {word:<20s} {gen_merged[word]:>10,}")
    w("")

    w(f"  Words in REFERENCE (vergil+ausonius) but not in GENERATED (exact+loose)")
    w(f"  ({len(only_ref)} words with freq >= {MIN_FREQ}):")
    w(f"  {'Word':<20s} {'Ref count':>10s}  {'Sources'}")
    w(f"  {'-'*20} {'-'*10}  {'-------'}")
    for word in sorted(only_ref, key=lambda w: -ref_merged[w]):
        sources = []
        for n in ref_names:
            if word in freqs[n]:
                sources.append(n)
        w(f"  {word:<20s} {ref_merged[word]:>10,}  {', '.join(sources)}")
    w("")

    # ---- Near-miss spelling pairs ----
    w("-" * 72)
    w("POTENTIAL NEAR-MISS SPELLING PAIRS (edit distance 1)")
    w("-" * 72)
    w("")
    near = find_near_misses(vocabs, freqs)
    if not near:
        w("  (none found)")
    else:
        shown = 0
        for wa, ca, wb, cb, ca_count, cb_count in near:
            if shown >= 40:
                break
            w(f"  {wa:<18s} [{ca:<18s}] {ca_count:>5,}  ~  "
              f"{wb:<18s} [{cb:<18s}] {cb_count:>5,}")
            shown += 1
    w("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=str, default="",
                        help="Write report to this file instead of stdout")
    args = parser.parse_args()

    corpora = load_corpora()
    report = generate_report(corpora)

    if args.output:
        out = Path(args.output)
        out.write_text(report, encoding="utf-8")
        print(f"Report written to {out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

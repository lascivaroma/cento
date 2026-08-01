"""How often is each Vergilian source verse reused across the generated
corpora, and does reuse cluster around particular metrical shapes?

Two distinct questions, both requested alongside the existing
plot_corpus_distributions.py distributions:

1. Poem-level: how many of the 1000 generated poems in each strategy have
   AT LEAST ONE source verse cited more than once WITHIN that poem (a
   stricter, binary version of plot_corpus_distributions.py's
   "repeated sources per cento" distribution, which counts *how many*
   distinct verses repeat per poem rather than whether any do).
2. Corpus-level: across all 1000 poems combined, which individual source
   verses (by CTS URN) get drawn most often, and in which line-level
   dactyl/spondee scan pattern(s) (the compact format's <line pattern=...>,
   already computed by pycento/serialize.py at generation time) do their
   citations occur? A verse cited often but always in the same scan
   context would suggest the metrical constraint itself is funneling
   generation toward a small repertoire; a verse cited often across many
   different scans would suggest plain popularity (e.g. a common short
   word pattern) instead.

Usage:
    python viz/segment_frequency.py [--out-dir viz] [--top 20]
"""

import argparse
import glob
import os.path as op
from collections import Counter

import matplotlib.pyplot as plt
import seaborn as sns
from lxml import etree

from pycento.data import parse_cento

_ROOT = op.dirname(op.abspath(op.join(__file__, "..")))
_CENTO_GOLD = op.join(_ROOT, "data", "gold", "cento.xml")
_GENERATED_DIR = op.join(_ROOT, "data", "generated-compact")

_COLOR_EXACT = "#2a78d6"
_COLOR_LOOSE = "#eb6834"
_STRATEGIES = [("exact", _COLOR_EXACT), ("loose", _COLOR_LOOSE)]
_LEGEND_LABELS = {"exact": "RQ2", "loose": "RQ3"}


def collect_citations(strategy):
    """(n_poems, n_poems_with_within_poem_repeat, Counter[source] -> total
    citations across all poems, dict[source] -> Counter[line pattern] for
    WHOLE-verse citations, dict[source] -> Counter[line pattern] for
    FRAGMENT (H1/H2, sharing the line with another segment) citations).

    A line's `pattern` attribute describes the WHOLE line, not any one
    segment within it. For a whole-verse (single-segment) line that's the
    same thing, so its scan is the verse's own genuine, fixed scansion. But
    for a fragment (one of two segments sharing a line), the reported
    pattern is really "this fragment glued to whatever random partner it
    got this time" -- the fragment's own syllables didn't rescan
    differently, the partner did. Keeping the two separate avoids reporting
    a verse as having "N different scans" when really only its fragment
    citations vary (with N-1 different random partners), while its
    whole-verse citations are perfectly consistent.
    """
    files = sorted(glob.glob(op.join(_GENERATED_DIR, strategy, "*.xml")))
    global_counts = Counter()
    whole_scans = {}
    frag_scans = {}
    n_with_repeat = 0
    for f in files:
        tree = etree.parse(f)
        per_poem = Counter()
        for line in tree.findall(".//line"):
            pattern = line.get("pattern")
            milestones = line.findall("./milestone")
            is_whole = len(milestones) == 1
            for m in milestones:
                source = m.get("source")
                per_poem[source] += 1
                global_counts[source] += 1
                bucket = whole_scans if is_whole else frag_scans
                bucket.setdefault(source, Counter())[pattern] += 1
        if any(c > 1 for c in per_poem.values()):
            n_with_repeat += 1
    return len(files), n_with_repeat, global_counts, whole_scans, frag_scans


def gold_citations():
    lines = parse_cento(_CENTO_GOLD)
    counts = Counter(seg.source for line in lines for seg in line.segments)
    return len(lines), sum(1 for c in counts.values() if c > 1), counts


def print_report(data, gold_n_lines, gold_n_repeated_verses, gold_counts, top_n):
    print("=" * 78)
    print("SEGMENT / SOURCE-VERSE REUSE")
    print("=" * 78)

    print(f"\n[gold] {gold_n_lines} lines, {len(gold_counts)} distinct verses cited, "
          f"{gold_n_repeated_verses} cited more than once (within the single gold poem)")

    for strategy, _ in _STRATEGIES:
        n_poems, n_with_repeat, global_counts, whole_scans, frag_scans = data[strategy]
        pct = 100 * n_with_repeat / n_poems
        print(f"\n[{strategy}] {n_with_repeat}/{n_poems} poems ({pct:.1f}%) have at least one "
              f"source verse cited more than once WITHIN that poem")
        print(f"[{strategy}] {len(global_counts)} distinct source verses drawn across all "
              f"{n_poems} poems combined, {sum(global_counts.values())} citations total")

        print(f"[{strategy}] top {top_n} most-cited source verses (corpus-wide), split into "
              f"whole-verse citations (this verse's own, genuinely fixed scan) vs fragment "
              f"citations (H1/H2, sharing the line with a random partner -- the reported "
              f"scan is the WHOLE line's, so it varies with the partner, not with this "
              f"verse's own syllables):")
        for source, count in global_counts.most_common(top_n):
            w, fr = whole_scans.get(source, Counter()), frag_scans.get(source, Counter())
            w_str = ", ".join(f"{p}×{c}" for p, c in w.most_common()) or "-"
            fr_str = ", ".join(f"{p}×{c}" for p, c in fr.most_common()) or "-"
            print(f"    {count:>5}x  {source:<45}")
            print(f"           whole ({sum(w.values())}x): {w_str}")
            print(f"           fragment ({sum(fr.values())}x): {fr_str}")


def plot_top_sources(data, out_path, top_n):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharex=False)
    for ax, (strategy, color) in zip(axes, _STRATEGIES):
        _, _, global_counts, whole_scans, frag_scans = data[strategy]
        top = global_counts.most_common(top_n)
        labels = [ref.split(":")[-1] for ref, _ in top]
        whole_counts = [sum(whole_scans.get(ref, Counter()).values()) for ref, _ in top]
        frag_counts = [sum(frag_scans.get(ref, Counter()).values()) for ref, _ in top]

        y = range(len(top))
        ax.barh(y, whole_counts, color=color, alpha=0.9, label="whole verse (1 scan)")
        ax.barh(y, frag_counts, left=whole_counts, color=color, alpha=0.35,
                label="fragment (scan varies with partner)")
        ax.set_yticks(list(y))
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Citations across all 1000 poems")
        ax.set_title(_LEGEND_LABELS[strategy])
        ax.legend(fontsize=7, loc="lower right")
        sns.despine(ax=ax)
    fig.suptitle(f"Top {top_n} most-reused source verses per strategy\n"
                 "(whole-verse citations always share one fixed scan; fragment citations don't)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    print(f"\nWrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default=op.dirname(op.abspath(__file__)))
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    sns.set_theme(style="whitegrid")

    data = {}
    for strategy, _ in _STRATEGIES:
        data[strategy] = collect_citations(strategy)

    gold_n_lines, gold_n_repeated, gold_counts = gold_citations()
    print_report(data, gold_n_lines, gold_n_repeated, gold_counts, args.top)
    plot_top_sources(data, op.join(args.out_dir, "top_reused_sources.png"), args.top)


if __name__ == "__main__":
    main()

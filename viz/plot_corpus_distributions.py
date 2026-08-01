"""Seaborn distribution plots for the 1000-poem generated corpora (exact & loose):

1. Words per cento (distribution across the 1000 generated poems per strategy).
2. Repeated sources per cento (how many Vergilian verses are cited more than
   once within the same poem, across the 1000 generated poems per strategy).
3. Sentence length per cento (mean words-per-sentence, sentences delimited by
   strong punctuation ". ; ? !" -- commas/colons don't end a sentence).

All plots overlay the gold Cento Nuptialis's own value as a dashed reference
line.

Usage:
    python viz/plot_corpus_distributions.py [--out-dir viz]
"""

import argparse
import glob
import os.path as op
import re
import statistics
from collections import Counter

import matplotlib.pyplot as plt
import seaborn as sns
from lxml import etree

from pycento.data import parse_cento

_ROOT = op.dirname(op.abspath(op.join(__file__, "..")))
_CENTO_GOLD = op.join(_ROOT, "data", "gold", "cento.xml")
_GENERATED_DIR = op.join(_ROOT, "data", "generated-compact")

# dataviz skill categorical palette, slots 1 (blue) / 2 (orange)
_COLOR_EXACT = "#2a78d6"
_COLOR_LOOSE = "#eb6834"
_COLOR_GOLD = "#0b0b0b"

_STRATEGIES = [("exact", _COLOR_EXACT), ("loose", _COLOR_LOOSE)]
_LEGEND_LABELS = {"exact": "RQ2", "loose": "RQ3"}

# "strong" sentence-ending punctuation; comma/colon are treated as weak
# (clause-internal) and do not close a sentence.
_STRONG_PUNCT = {".", "!", "?", ";"}
_TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")


def compact_sentence_lengths(path):
    """Words-per-sentence for one compact-format cento XML.

    Punctuation is attached to the closing word's text (e.g. "partem.",
    "exsequar:"); a sentence ends when that trailing punctuation contains a
    strong mark.
    """
    tree = etree.parse(path)
    lengths = []
    current = 0
    for w in tree.iter("word"):
        current += 1
        text = w.text or ""
        m = _TRAILING_PUNCT_RE.search(text)
        trailing = m.group() if m else ""
        if any(ch in _STRONG_PUNCT for ch in trailing):
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def poem_stats(path):
    """(n_words, n_repeated_sources, mean_sentence_length) for one compact-format cento XML."""
    tree = etree.parse(path)
    n_words = len(tree.findall(".//word"))
    sources = [m.get("source") for m in tree.findall(".//milestone")]
    counts = Counter(sources)
    n_repeated = sum(1 for c in counts.values() if c > 1)
    sentence_lengths = compact_sentence_lengths(path)
    mean_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else 0.0
    return n_words, n_repeated, mean_sentence_length


def collect(strategy):
    files = sorted(glob.glob(op.join(_GENERATED_DIR, strategy, "*.xml")))
    words, repeated, sentence_length = [], [], []
    for f in files:
        try:
            n_words, n_repeated, mean_sentence_length = poem_stats(f)
        except etree.XMLSyntaxError as e:
            print(f"  warning: failed to parse {f}: {e}")
            continue
        words.append(n_words)
        repeated.append(n_repeated)
        sentence_length.append(mean_sentence_length)
    return words, repeated, sentence_length


def gold_sentence_lengths():
    """Words-per-sentence for the gold cento, using its separate <pc> punctuation elements."""
    root = etree.parse(_CENTO_GOLD).getroot()
    lengths = []
    current = 0
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue  # skip comments/PIs
        tag = etree.QName(el).localname
        if tag == "w":
            current += 1
        elif tag == "pc":
            text = (el.text or "").strip()
            if any(ch in _STRONG_PUNCT for ch in text):
                if current:
                    lengths.append(current)
                current = 0
    if current:
        lengths.append(current)
    return lengths


def gold_reference():
    lines = parse_cento(_CENTO_GOLD)
    n_words = sum(len(l.words) for l in lines)
    sources = [seg.source for line in lines for seg in line.segments]
    counts = Counter(sources)
    n_repeated = sum(1 for c in counts.values() if c > 1)
    mean_sentence_length = statistics.mean(gold_sentence_lengths())
    return n_words, n_repeated, mean_sentence_length


def plot_words(data, gold_words, out_path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for strategy, color in _STRATEGIES:
        sns.histplot(
            data[strategy]["words"],
            stat="density",
            kde=True,
            color=color,
            label=_LEGEND_LABELS[strategy],
            element="step",
            fill=True,
            alpha=0.25,
            ax=ax,
        )
    ax.axvline(gold_words, color=_COLOR_GOLD, linestyle="--", linewidth=2,
               label=f"Ausonius' Cento ({gold_words})")
    ax.set_xlabel("Words per cento")
    ax.set_ylabel("Density")
    ax.legend()
    sns.despine(ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    print(f"Wrote {out_path}")


def plot_repeated_sources(data, gold_repeated, out_path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for strategy, color in _STRATEGIES:
        sns.histplot(
            data[strategy]["repeated"],
            stat="density",
            discrete=True,
            color=color,
            label=_LEGEND_LABELS[strategy],
            element="step",
            fill=True,
            alpha=0.25,
            ax=ax,
        )
    ax.axvline(gold_repeated, color=_COLOR_GOLD, linestyle="--", linewidth=2,
               label=f"Ausonius' Cento ({gold_repeated})")
    ax.set_xlabel("Repeated sources per cento")
    ax.set_ylabel("Density")
    ax.legend()
    sns.despine(ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    print(f"Wrote {out_path}")


def plot_sentence_length(data, gold_sentence_length, out_path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for strategy, color in _STRATEGIES:
        sns.histplot(
            data[strategy]["sentence_length"],
            stat="density",
            kde=True,
            color=color,
            label=_LEGEND_LABELS[strategy],
            element="step",
            fill=True,
            alpha=0.25,
            ax=ax,
        )
    ax.axvline(gold_sentence_length, color=_COLOR_GOLD, linestyle="--", linewidth=2,
               label=f"Ausonius' Cento ({gold_sentence_length:.1f})")
    ax.set_xlabel("Mean words per sentence (strong punctuation as boundary)")
    ax.set_ylabel("Density")
    ax.legend()
    sns.despine(ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default=op.dirname(op.abspath(__file__)))
    args = parser.parse_args()

    sns.set_theme(style="whitegrid")

    data = {}
    for strategy, _ in _STRATEGIES:
        words, repeated, sentence_length = collect(strategy)
        print(f"[{strategy}] {len(words)} poems parsed")
        data[strategy] = {"words": words, "repeated": repeated, "sentence_length": sentence_length}

    gold_words, gold_repeated, gold_sentence_length = gold_reference()
    print(f"[gold] words={gold_words} repeated_sources={gold_repeated} "
          f"mean_sentence_length={gold_sentence_length:.2f}")

    plot_words(data, gold_words, op.join(args.out_dir, "words_per_cento.png"))
    plot_repeated_sources(data, gold_repeated, op.join(args.out_dir, "repeated_sources_per_cento.png"))
    plot_sentence_length(data, gold_sentence_length, op.join(args.out_dir, "sentence_length_per_cento.png"))


if __name__ == "__main__":
    main()

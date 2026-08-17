"""POC: detect a 'strong 3rd foot caesura' = word break after exactly 10 morae.

Each token in a *.mapped_lines.txt line is a word prime-encoded per
metrical_numbering.py:
    L (long)     = 2   -> 2 morae
    S (short)    = 3   -> 1 mora
    E (elided)   = 5   -> 0 morae
    PE (prodel.) = 7   -> 0 morae
    Q (que)      = 11  -> 0 morae

So a word's morae = 2 * (exponent of prime 2) + 1 * (exponent of prime 3).
We walk the line summing morae per word and flag lines where the running total
lands exactly on 10 at a word boundary (a break after 10 morae = strong /
penthemimeral 3rd-foot caesura).
"""
from __future__ import annotations
from pathlib import Path


def morae(n: int) -> int:
    """Morae contributed by one token (0 tokens / elided / prodel. contribute 0)."""
    if n <= 1:
        return 0
    m = 0
    while n % 2 == 0:          # long syllables (L = prime 2) = 2 morae each
        m += 2
        n //= 2
    while n % 3 == 0:          # short syllables (S = prime 3) = 1 mora each
        m += 1
        n //= 3
    return m


def find_break_at(line_tokens: list[int], target: int = 10) -> tuple[bool, list[int]]:
    """Return (has_word_break_at_target, [cumulative morae after each word])."""
    cumulative: list[int] = []
    total = 0
    for n in line_tokens:
        total += morae(n)
        cumulative.append(total)
    # A break 'after X morae' exists if some prefix-sum == target AND it's not the
    # very last word (a caesura must have material after it).
    has_break = any(c == target and i < len(cumulative) - 1
                    for i, c in enumerate(cumulative))
    return has_break, cumulative


def parse_lines(path: Path) -> list[list[int]]:
    lines = []
    for raw in path.read_text().splitlines():
        tokens = [t for t in raw.split() if t and t != "<EOL>"]
        if tokens:
            lines.append([int(t) for t in tokens])
    return lines


def analyze(path: Path, label: str) -> None:
    lines = parse_lines(path)
    n_break = 0
    n_not24 = []
    for i, toks in enumerate(lines, 1):
        has, cum = find_break_at(toks)
        if cum and cum[-1] != 24:
            n_not24.append(i)
        if has:
            n_break += 1
    print(f"=== {label} ({path.name})")
    print(f"  lines analysed           : {len(lines)}")
    print(f"  lines with strong 3rd-foot caesura (break @10 morae): {n_break}")
    print(f"  percentage               : {n_break/len(lines)*100:.1f}%")
    print(f"  lines whose total != 24 (sanity, expect 0): {len(n_not24)} {n_not24[:10]}")
    print()
    return n_break, len(lines)


if __name__ == "__main__":
    analyze(Path("metrical_model_lines/question/cento_nuptialis.mapped_lines.txt"), "CENTO")

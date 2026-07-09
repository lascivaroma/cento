"""Generate random centos following scheme.json's EXACT morae sequences.

Walks scheme.json's "table" row by row (via pycento.scheme.iter_scheme_rows),
resolving each segment against data/segment_table.json by its exact
row-slice key. Two-segment (cross-line continuation) rows prefer a
pre-validated adjacent-Virgil-verse pair when one exists; otherwise two
candidates are drawn independently and the joint is re-scanned (see
pycento/generate.py's rescan_joint, which needs a locally-built
latin_scansion grammar archive -- see scripts/fetch_latin_scansion.sh; pass
--allow-unchecked-merges to skip re-validation, e.g. if that isn't set up).

Usage:
    python step-04-Generate-Centos-Sequence.py [--count N] [--works Aeneid ...]
    python step-04-Generate-Centos-Sequence.py --count 100 --allow-unchecked-merges

Output: data/generated-compact/exact/cento_{n:04d}.xml
"""

import argparse
import json
import os.path as op
import random

from pycento.generate import MergeStats, ResolvedSegment, assemble_lines, entry_to_words, resolve_merge_slot, work_of, write_poem
from pycento.scansion import ScansionUnavailable
from pycento.scheme import RowShape, iter_scheme_rows, render_row_key

_ROOT = op.dirname(op.abspath(__file__))


def _key(pattern, is_start) -> str:
    return json.dumps([0, list(pattern)] if is_start else [list(pattern)])


def _filter_by_work(candidates: list, works) -> list:
    if not works:
        return candidates
    return [e for e in candidates if work_of(e["id"]) in works]


class PoemFailed(Exception):
    pass


def generate_poem(rows: list, table: dict, works, allow_unchecked: bool, stats: MergeStats):
    used_refs: set = set()
    all_lines: list = []
    current_line: list = []

    def close_line():
        nonlocal current_line
        if current_line:
            all_lines.append(current_line)
        current_line = []

    for segs in rows:
        if len(segs) == 1:
            pattern, is_start = segs[0]
            candidates = _filter_by_work(table.get(_key(pattern, is_start), []), works)
            if not candidates:
                raise PoemFailed(f"no candidates for {_key(pattern, is_start)}")
            if is_start:
                close_line()
            pool = [e for e in candidates if e["id"] not in used_refs] or candidates
            entry = random.choice(pool)
            used_refs.add(entry["id"])
            current_line.append(ResolvedSegment(source=entry["id"], words=entry_to_words(entry), continued=False))
        else:
            (pattern_a, is_start_a), (pattern_b, is_start_b) = segs
            row_key = render_row_key(segs)
            pair_entries = table.get(row_key, [])
            a_candidates = _filter_by_work(table.get(_key(pattern_a, is_start_a), []), works)
            b_candidates = _filter_by_work(table.get(_key(pattern_b, is_start_b), []), works)

            result = resolve_merge_slot(pair_entries, a_candidates, b_candidates, used_refs, allow_unchecked, stats=stats)
            if result is None:
                raise PoemFailed(f"could not resolve merge slot for row {row_key}")
            words_a, words_b, ids = result
            used_refs.update(ids)

            if is_start_a:
                close_line()
            current_line.append(ResolvedSegment(source=ids[0], words=words_a, continued=False))
            close_line()  # segment B always starts the next line
            current_line.append(ResolvedSegment(source=ids[1], words=words_b, continued=True))

    close_line()
    return assemble_lines(all_lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--works", nargs="*", default=None, choices=["Aeneid", "Eclogues", "Georgics"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--allow-unchecked-merges", action="store_true",
                         help="Skip re-scanning merged joints (rescan_joint is not implemented yet).")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print("Loading scheme.json...")
    with open(op.join(_ROOT, "scheme.json"), encoding="utf-8") as fh:
        scheme_table = json.load(fh)["table"]
    rows = list(iter_scheme_rows(scheme_table))
    print(f"  {len(rows)} rows")

    print("Loading segment table...")
    with open(op.join(_ROOT, "data", "segment_table.json"), encoding="utf-8") as fh:
        table = json.load(fh)

    out_dir = op.join(_ROOT, "data", "generated-compact", "exact")

    print(f"\nGenerating {args.count} poems -> {out_dir}/")
    written, skipped = 0, 0
    stats = MergeStats()
    for n in range(1, args.count + 1):
        try:
            lines = generate_poem(rows, table, args.works, args.allow_unchecked_merges, stats)
        except PoemFailed as exc:
            print(f"  [SKIP] poem {n}: {exc}")
            skipped += 1
            continue
        except ScansionUnavailable as exc:
            print(f"\nSome continuation rows have no pre-validated adjacent-verse pair "
                  f"and would need a re-scanned merge, but the scansion grammar isn't "
                  f"available: {exc}\nPass --allow-unchecked-merges to generate anyway.")
            raise SystemExit(1)
        out_path = op.join(out_dir, f"cento_{n:04d}.xml")
        write_poem(lines, out_path)
        written += 1
        if n % 100 == 0:
            print(f"  {n}/{args.count}")

    print(f"Done. Generated {written}/{args.count} poems ({skipped} skipped) in {out_dir}/")
    print("Merge-slot resolution:")
    print(stats.summary())


if __name__ == "__main__":
    main()

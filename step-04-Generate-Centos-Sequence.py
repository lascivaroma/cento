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

from pycento.generate import (
    MergeStats,
    ResolvedSegment,
    assemble_lines,
    elision_ok,
    entry_to_words,
    first_defective_line,
    pick_candidate,
    rescan_joint,
    resolve_merge_slot,
    work_of,
    write_poem,
)
from pycento.scansion import ScansionUnavailable
from pycento.scheme import iter_scheme_rows, render_row_key

_ROOT = op.dirname(op.abspath(__file__))


def _key(pattern, is_start) -> str:
    return json.dumps([0, list(pattern)] if is_start else [list(pattern)])


def _filter_by_work(candidates: list, works) -> list:
    if not works:
        return candidates
    return [e for e in candidates if work_of(e["id"]) in works]


class PoemFailed(Exception):
    pass


def _pick_line_segment(candidates: list, used_refs: set, prev_words, allow_unchecked: bool,
                        stats: MergeStats, max_attempts: int = 30):
    """Draw a candidate for an ordinary single-segment row, validating the
    joint against the immediately preceding segment already placed in this
    cento line (if any).

    An ordinary same-line split (e.g. H1+H2 at the caesura) is two separate
    single-segment rows in sequence, not a 2-segment continuation row -- so
    nothing else ever validates the boundary between them, even though
    they're independently drawn from unrelated Virgil verses. Without this,
    a segment ending in a syllable marked "elided" in the gold data (elided
    against whatever originally followed it) can get glued to a new next
    segment that doesn't start with a vowel, silently un-eliding it.

    A candidate that fails elision or rescan is removed from the pool for
    the remaining attempts (falling back to the full pool once every
    candidate has been tried and failed), so retries explore new candidates
    instead of risking a repeat draw of the same bad one.

    Returns (entry, words), or (None, None) if no compatible candidate was
    found within `max_attempts` (or at all).
    """
    if prev_words is None:
        entry = pick_candidate(candidates, used_refs)
        return entry, entry_to_words(entry)

    failed: set = set()
    for _ in range(max_attempts):
        entry = pick_candidate(candidates, used_refs | failed)
        words = entry_to_words(entry)
        if stats is not None:
            stats.elision_checks += 1
        if not elision_ok(prev_words, words):
            if stats is not None:
                stats.elision_rejected += 1
            failed.add(entry["id"])
            continue
        if allow_unchecked:
            return entry, words
        result = rescan_joint(prev_words, words)
        if stats is not None:
            stats.rescan_attempts += 1
        if result.valid:
            return entry, words
        if stats is not None:
            stats.rescan_rejected += 1
        failed.add(entry["id"])
    if stats is not None:
        stats.slots_given_up += 1
    return None, None


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
            prev_words = current_line[-1].words if current_line else None
            entry, words = _pick_line_segment(candidates, used_refs, prev_words, allow_unchecked, stats)
            if entry is None:
                raise PoemFailed(f"could not resolve a same-line-compatible segment for {_key(pattern, is_start)}")
            used_refs.add(entry["id"])
            current_line.append(ResolvedSegment(source=entry["id"], words=words, continued=False))
        else:
            (pattern_a, is_start_a), (pattern_b, is_start_b) = segs
            row_key = render_row_key(segs)
            pair_entries = table.get(row_key, [])
            a_candidates = _filter_by_work(table.get(_key(pattern_a, is_start_a), []), works)
            b_candidates = _filter_by_work(table.get(_key(pattern_b, is_start_b), []), works)

            # Every 2-segment row here is a type="sq" continuation boundary:
            # A closes one cento line (which may have earlier segments of
            # its own) and B opens the next -- words_a + words_b is NOT the
            # whole line on its own, so full_line=False skips the
            # concatenation-must-be-a-clean-hexameter check (see
            # resolve_merge_slot's docstring).
            result = resolve_merge_slot(pair_entries, a_candidates, b_candidates, used_refs,
                                         allow_unchecked, stats=stats, full_line=False)
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
    lines = assemble_lines(all_lines)
    defective = first_defective_line(lines)
    if defective is not None:
        # Only reachable for a solitary (AB, whole-verse) single-segment
        # line: every 2-segment joint (continuation or same-line append)
        # already went through is_clean_hexameter() before being accepted.
        raise PoemFailed(f"line {defective.idx} has a defective/incomplete foot")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--works", nargs="*", default=None, choices=["Aeneid", "Eclogues", "Georgics"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--allow-unchecked-merges", action="store_true",
                         help="Skip rescan_joint's full-hexameter re-validation of merged "
                              "joints (e.g. if the compiled scansion grammar isn't available). "
                              "The elision check always runs regardless.")
    parser.add_argument("--max-attempts-multiplier", type=int, default=10,
                         help="Give up after --count * this many total poem attempts, in "
                              "case some row has a hard, unresolvable coverage gap.")
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

    max_total_attempts = args.count * args.max_attempts_multiplier
    print(f"\nGenerating {args.count} complete, fully-scanned poems -> {out_dir}/ "
          f"(up to {max_total_attempts} attempts)")
    written, skipped, attempt = 0, 0, 0
    stats = MergeStats()
    while written < args.count and attempt < max_total_attempts:
        attempt += 1
        try:
            lines = generate_poem(rows, table, args.works, args.allow_unchecked_merges, stats)
        except PoemFailed as exc:
            skipped += 1
            if skipped % 500 == 0:
                print(f"  ({skipped} attempts failed so far, most recently: {exc})")
            continue
        except ScansionUnavailable as exc:
            print(f"\nSome continuation rows have no pre-validated adjacent-verse pair "
                  f"and would need a re-scanned merge, but the scansion grammar isn't "
                  f"available: {exc}\nPass --allow-unchecked-merges to generate anyway.")
            raise SystemExit(1)
        written += 1
        out_path = op.join(out_dir, f"cento_{written:04d}.xml")
        write_poem(lines, out_path)
        if written % 100 == 0:
            print(f"  {written}/{args.count} (after {attempt} attempts)")

    if written < args.count:
        print(f"\nGave up after {attempt} attempts: only {written}/{args.count} poems were "
              f"both complete (131/131 lines) and fully scanned (no defective feet). Some "
              f"row/slot in scheme.json likely has no combination that satisfies elision + "
              f"clean-scan + rescan within the data currently in data/segment_table.json -- "
              f"more attempts won't help a hard coverage gap; re-run step-02/step-03 with "
              f"more source data, or widen --works.")
    print(f"Done. Generated {written}/{args.count} poems ({skipped} failed attempts, "
          f"{attempt} total attempts) in {out_dir}/")
    print("Merge-slot resolution:")
    print(stats.summary())


if __name__ == "__main__":
    main()

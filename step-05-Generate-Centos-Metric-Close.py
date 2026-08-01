"""Generate random centos matching only the TOTAL morae (sum, not exact
sequence) of each real cento segment, still respecting real word boundaries
at the segment cut -- AND still respecting genuine cross-line continuations.

Reuses scheme.json's row structure (via pycento.scheme.build_line_specs) to
reconstruct the real cento lines and know how many segments each has, same
as step-04, but looks each segment up by TOTAL morae in
data/segment_table_by_total.json instead of by exact sequence.

Two segments that fill the SAME cento line (an ordinary mid-verse-caesura
split) are independently drawn and re-scanned as a joint (see
pycento/generate.py's rescan_joint, which needs a locally-built
latin_scansion grammar archive -- see scripts/fetch_latin_scansion.sh; pass
--allow-unchecked-merges to skip re-validation, e.g. if that isn't set up)
-- unlike step-04, this never requires the two to come from genuinely
adjacent Virgil verses, since they're not standing in for a real
`type="sq"` continuation.

A line whose first segment IS a genuine `type="sq"` continuation of the
previous line's last segment (build_line_specs' `continues_previous`) is
different: that boundary pair IS resolved from data/segment_table_by_total.json's
"sequential" bucket -- pre-validated pairs of ADJACENT Virgil verses (same
file, raw_index differs by exactly 1), matched by total morae rather than
exact sequence. This preserves the gold cento's deliberate "quote two
verses in a row" construction even in loose mode, while everything else
about the line (vocabulary, exact dactyl/spondee pattern) is free to differ.

Usage:
    python step-05-Generate-Centos-Metric-Close.py [--count N] [--works Aeneid ...]
    python step-05-Generate-Centos-Metric-Close.py --count 100 --allow-unchecked-merges

Output: data/generated-compact/loose/cento_{n:04d}.xml
"""

import argparse
import json
import os.path as op
import random
from typing import List, Optional, Tuple

from pycento.data import Word
from pycento.generate import (
    MergeStats,
    ResolvedSegment,
    assemble_lines,
    elision_ok,
    entry_to_words,
    first_defective_line,
    is_clean_hexameter,
    pick_candidate,
    rescan_joint,
    resolve_merge_slot,
    resolve_pinned_slot,
    work_of,
    write_poem,
)
from pycento.scansion import ScansionUnavailable
from pycento.scheme import LineSpec, build_line_specs, iter_scheme_rows, line_segment_totals

_ROOT = op.dirname(op.abspath(__file__))


def _filter_by_work(candidates: list, works) -> list:
    if not works:
        return candidates
    return [e for e in candidates if work_of(e["id"]) in works]


def _filter_pairs_by_work(pairs: list, works) -> list:
    if not works:
        return pairs
    return [p for p in pairs if work_of(p[0]["id"]) in works and work_of(p[1]["id"]) in works]


class LineSkipped(Exception):
    pass


# A resolved segment slot: (source_id, words, continued).
Slot = Optional[Tuple[str, List[Word], bool]]


def resolve_continuation_boundaries(
    line_specs: List[LineSpec], totals_per_line: List[Tuple[int, ...]],
    by_total: dict, works, used_refs: set,
) -> List[List[Slot]]:
    """Resolve every genuine `type="sq"` cross-line boundary FIRST, from
    pre-validated adjacent-Virgil-verse pairs, before any of a line's other
    (independently drawn) segments are touched. Returns a per-line list of
    per-segment slots, pre-filled at the two boundary positions and None
    everywhere else."""
    resolved: List[List[Slot]] = [[None] * len(spec.segs) for spec in line_specs]
    sequential = by_total.get("sequential", {})

    for i, spec in enumerate(line_specs):
        if not spec.continues_previous or i == 0:
            continue
        a_total = totals_per_line[i - 1][-1]
        b_total = totals_per_line[i][0]
        key = f"{a_total}/{b_total}"
        pairs = _filter_pairs_by_work(sequential.get(key, []), works)
        pool = [
            p for p in pairs
            if p[0]["id"] not in used_refs and p[1]["id"] not in used_refs
        ] or pairs
        if not pool:
            continue  # left unresolved; surfaces as LineSkipped for both lines below
        entry_a, entry_b = random.choice(pool)
        used_refs.update([entry_a["id"], entry_b["id"]])
        resolved[i - 1][-1] = (entry_a["id"], entry_to_words(entry_a), False)
        resolved[i][0] = (entry_b["id"], entry_to_words(entry_b), True)

    return resolved


def resolve_line(
    totals: Tuple[int, ...], slots: List[Slot], by_total: dict, works,
    used_refs: set, allow_unchecked: bool, stats: MergeStats,
) -> List[ResolvedSegment]:
    """Fill in whichever of this line's 1 or 2 segments aren't already
    pinned by resolve_continuation_boundaries, then return the finished
    ResolvedSegments. Raises LineSkipped if a required split/whole-verse
    entry isn't covered, or no valid candidate/joint could be found."""
    if len(totals) == 1:
        if slots[0] is None:
            whole_candidates = _filter_by_work(by_total.get("whole", []), works)
            if not whole_candidates:
                raise LineSkipped("no whole-verse candidates available (segment_table_by_total.json "
                                   "has no 'whole' bucket -- regenerate it via step-03)")
            # A whole-verse entry is real, unmodified Virgil text -- no
            # gluing, so it should always be intrinsically clean. Verify
            # anyway rather than assume (a handful of retries in case a
            # rare bad entry is drawn), since this is the only path that
            # never goes through a joint check.
            failed: set = set()
            entry = None
            for _ in range(30):
                candidate = pick_candidate(whole_candidates, used_refs | failed)
                if stats is not None:
                    stats.clean_scan_checks += 1
                if is_clean_hexameter(entry_to_words(candidate)):
                    entry = candidate
                    break
                if stats is not None:
                    stats.clean_scan_rejected += 1
                failed.add(candidate["id"])
            if entry is None:
                if stats is not None:
                    stats.slots_given_up += 1
                raise LineSkipped("no whole-verse candidate scans as a clean hexameter "
                                   "after 30 attempts")
            used_refs.add(entry["id"])
            slots[0] = (entry["id"], entry_to_words(entry), False)
        source, words, continued = slots[0]
        return [ResolvedSegment(source=source, words=words, continued=continued)]

    if len(totals) != 2:
        raise LineSkipped(f"{len(totals)}-segment lines aren't covered by "
                           f"segment_table_by_total.json (splits are all 1- or 2-part)")

    start_total, end_total = totals
    key = f"{start_total}/{end_total}"
    entry = by_total.get(key)
    if entry is None:
        raise LineSkipped(f"split {key} isn't in segment_table_by_total.json -- "
                           f"regenerate it via step-03 (scheme.json may have changed)")
    a_candidates = _filter_by_work(entry.get("start", []), works)
    b_candidates = _filter_by_work(entry.get("end", []), works)

    if slots[0] is not None and slots[1] is not None:
        # Both boundary segments were pinned by a continuation on EACH side
        # (rare: this line is sandwiched between two `type="sq"` slots).
        # They weren't drawn to be compatible with each other, so the joint
        # still needs validating -- and since both sides are already pinned,
        # there's nothing left to redraw if it fails.
        (id_a, words_a, cont_a), (id_b, words_b, cont_b) = slots
        if stats is not None:
            stats.elision_checks += 1
        if not elision_ok(words_a, words_b):
            if stats is not None:
                stats.elision_rejected += 1
                stats.slots_given_up += 1
            raise LineSkipped(f"pinned joint for split {key} would un-elide "
                               f"(final syllable of {id_a} is elided, but {id_b} "
                               f"doesn't start with a vowel)")
        if stats is not None:
            stats.clean_scan_checks += 1
        if not is_clean_hexameter(words_a + words_b):
            if stats is not None:
                stats.clean_scan_rejected += 1
                stats.slots_given_up += 1
            raise LineSkipped(f"pinned joint for split {key} would write a defective foot")
        if not allow_unchecked:
            if stats is not None:
                stats.rescan_attempts += 1
            result = rescan_joint(words_a, words_b)
            if not result.valid:
                if stats is not None:
                    stats.rescan_rejected += 1
                    stats.slots_given_up += 1
                raise LineSkipped(f"pinned joint for split {key} failed rescan: {result.reason}")
        return [
            ResolvedSegment(source=id_a, words=words_a, continued=cont_a),
            ResolvedSegment(source=id_b, words=words_b, continued=cont_b),
        ]

    if slots[0] is not None:
        id_a, words_a, cont_a = slots[0]
        result = resolve_pinned_slot(words_a, True, b_candidates, used_refs, allow_unchecked, stats=stats)
        if result is None:
            raise LineSkipped(f"could not resolve a free end-candidate for split {key} "
                               f"against a pinned continuation start")
        words_b, id_b = result
        used_refs.add(id_b)
        return [
            ResolvedSegment(source=id_a, words=words_a, continued=cont_a),
            ResolvedSegment(source=id_b, words=words_b, continued=False),
        ]

    if slots[1] is not None:
        id_b, words_b, cont_b = slots[1]
        result = resolve_pinned_slot(words_b, False, a_candidates, used_refs, allow_unchecked, stats=stats)
        if result is None:
            raise LineSkipped(f"could not resolve a free start-candidate for split {key} "
                               f"against a pinned continuation end")
        words_a, id_a = result
        used_refs.add(id_a)
        return [
            ResolvedSegment(source=id_a, words=words_a, continued=False),
            ResolvedSegment(source=id_b, words=words_b, continued=cont_b),
        ]

    result = resolve_merge_slot([], a_candidates, b_candidates, used_refs, allow_unchecked, stats=stats)
    if result is None:
        raise LineSkipped(f"could not resolve start/end candidates for split {key}")
    words_a, words_b, ids = result
    used_refs.update(ids)
    return [
        ResolvedSegment(source=ids[0], words=words_a, continued=False),
        ResolvedSegment(source=ids[1], words=words_b, continued=False),
    ]


def generate_poem(line_specs: List[LineSpec], by_total: dict, works, allow_unchecked: bool, stats: MergeStats):
    """Resolve every one of the gold cento's 131 lines. Unlike the previous
    behavior, a line that can't be resolved is NOT silently dropped -- it
    fails the WHOLE poem (LineSkipped propagates to the caller), so every
    poem this returns has exactly as many lines as line_specs, all of them
    validated. The caller is expected to retry with a fresh poem attempt on
    failure rather than accept a shorter poem."""
    used_refs: set = set()
    totals_per_line = [line_segment_totals(spec.segs) for spec in line_specs]
    resolved_slots = resolve_continuation_boundaries(line_specs, totals_per_line, by_total, works, used_refs)

    all_lines: List[List[ResolvedSegment]] = [
        resolve_line(totals, slots, by_total, works, used_refs, allow_unchecked, stats)
        for spec, totals, slots in zip(line_specs, totals_per_line, resolved_slots)
    ]

    lines = assemble_lines(all_lines)
    defective = first_defective_line(lines)
    if defective is not None:
        # Final safety net: every joint (resolve_merge_slot/
        # resolve_pinned_slot/the both-pinned branch/the whole-verse
        # branch) already checks is_clean_hexameter() before accepting,
        # so this should be unreachable in practice -- but verify rather
        # than assume.
        raise LineSkipped(f"line {defective.idx} has a defective/incomplete foot")
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
                              "case some split has a hard, unresolvable coverage gap.")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print("Loading scheme.json...")
    with open(op.join(_ROOT, "scheme.json"), encoding="utf-8") as fh:
        scheme_table = json.load(fh)["table"]
    line_specs = build_line_specs(iter_scheme_rows(scheme_table))
    n_continuations = sum(1 for spec in line_specs if spec.continues_previous)
    print(f"  {len(line_specs)} lines, {n_continuations} continuation boundaries")

    print("Loading segment table (by total)...")
    with open(op.join(_ROOT, "data", "segment_table_by_total.json"), encoding="utf-8") as fh:
        by_total = json.load(fh)
    print(f"  {len(by_total)} entries (splits + whole-verse + sequential buckets)")

    out_dir = op.join(_ROOT, "data", "generated-compact", "loose")

    max_total_attempts = args.count * args.max_attempts_multiplier
    print(f"\nGenerating {args.count} complete ({len(line_specs)}/{len(line_specs)}-line), "
          f"fully-scanned poems -> {out_dir}/ (up to {max_total_attempts} attempts)")
    written, failed, attempt = 0, 0, 0
    stats = MergeStats()
    while written < args.count and attempt < max_total_attempts:
        attempt += 1
        try:
            lines = generate_poem(line_specs, by_total, args.works, args.allow_unchecked_merges, stats)
        except LineSkipped as exc:
            failed += 1
            if failed % 500 == 0:
                print(f"  ({failed} attempts failed so far, most recently: {exc})")
            continue
        except ScansionUnavailable as exc:
            print(f"\nSome slots here need a re-scanned merge, but the scansion grammar "
                  f"isn't available: {exc}\nPass --allow-unchecked-merges to generate anyway.")
            raise SystemExit(1)
        written += 1
        out_path = op.join(out_dir, f"cento_{written:04d}.xml")
        write_poem(lines, out_path)
        if written % 100 == 0:
            print(f"  {written}/{args.count} (after {attempt} attempts)")

    if written < args.count:
        print(f"\nGave up after {attempt} attempts: only {written}/{args.count} poems were "
              f"both complete ({len(line_specs)}/{len(line_specs)} lines) and fully scanned "
              f"(no defective feet). Some split in segment_table_by_total.json likely has no "
              f"combination that satisfies elision + clean-scan + rescan -- more attempts "
              f"won't help a hard coverage gap; re-run step-03 with more source data, or "
              f"widen --works.")
    print(f"Done. Generated {written}/{args.count} poems ({failed} failed attempts, "
          f"{attempt} total attempts) in {out_dir}/")
    print("Merge-slot resolution:")
    print(stats.summary())


if __name__ == "__main__":
    main()

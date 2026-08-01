"""Shared generation helpers for step-04-Generate-Centos-Sequence.py and
step-05-Generate-Centos-Metric-Close.py: converting a segment_table.json
entry into real Word/Syllable objects, resolving a two-segment merge slot
(preferring a pre-validated adjacent Virgil-verse pair, else independently
combining two candidates and re-scanning the joint), and writing a generated
poem out through pycento/serialize.py's compact-format writer.
"""

import os
import os.path as op
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import lxml.etree as et

from pycento.data import Line, Segment, Syllable, Word
from pycento.serialize import lines_to_compact_tree

_WORK_NAMES = {
    "phi0690.phi003": "Aeneid",
    "phi0690.phi001": "Eclogues",
    "phi0690.phi002": "Georgics",
}


def work_of(entry_id: str) -> Optional[str]:
    """'urn:cts:latinLit:phi0690.phi003:1.1' -> 'Aeneid'"""
    parts = entry_id.split(":")
    if len(parts) < 4:
        return None
    return _WORK_NAMES.get(parts[3])


def entry_to_words(entry: dict) -> List[Word]:
    """Direct, lossless mapping from a segment_table.json entry's `words`
    list into real Word/Syllable objects -- no re-chunking of a flat mora
    count into "roughly equal" per-word splits, since each entry already
    carries the real per-word text/lemma/pos/syllable data from the matched
    Virgil span."""
    return [
        Word(
            text=w["text"],
            lemma=w.get("lemma"),
            pos=w.get("pos"),
            morph=w.get("msd"),
            syllables=[Syllable(text=s["text"], length=s["length"]) for s in w["syllables"]],
        )
        for w in entry["words"]
    ]


_VOWELS = set("aeiouAEIOU")


def _last_syllable(words: List[Word]):
    for w in reversed(words):
        if w.syllables:
            return w.syllables[-1]
    return None


def _first_letter(words: List[Word]):
    for w in words:
        if w.text:
            return w.text[0]
    return None


def elision_ok(words_a: List[Word], words_b: List[Word]) -> bool:
    """Cheap, deterministic pre-check for gluing words_a's tail to words_b's
    head: if words_a's last syllable was originally marked "elided" in the
    gold data, that elision only holds because the ORIGINAL next word (in
    the real Virgil line) started with a vowel. Once we glue in a
    different words_b, the elision is only still valid if words_b's first
    word also starts with a vowel (a/e/i/o/u) -- otherwise the final
    syllable would no longer elide, silently changing the scansion, so the
    joint must be rejected.

    Unlike rescan_joint, this needs no compiled scansion grammar, so it
    should always run regardless of --allow-unchecked-merges.
    """
    last = _last_syllable(words_a)
    if last is None or last.length != "elided":
        return True
    first_letter = _first_letter(words_b)
    if first_letter is None:
        return True
    return first_letter in _VOWELS


@dataclass
class RescanResult:
    valid: bool
    reason: str = ""


def rescan_joint(words_a: List[Word], words_b: List[Word]) -> RescanResult:
    """Re-validate the metrical joint where words_a's tail meets words_b's
    head after gluing two independently-chosen Virgil segments together.

    Gluing two segments that weren't originally adjacent can change the
    scansion right at the seam -- a final vowel that didn't used to elide
    can suddenly meet a following vowel (or vice versa), and a syllable's
    long-by-position status can appear or disappear because what now
    follows/precedes it is different. This reconstructs a macron-marked
    string from our own already-known per-syllable weights (see
    pycento/scansion.py) and asks the latin_scansion/pynini FST engine
    whether the WHOLE glued sequence still scans as a valid hexameter --
    the engine determines weight/elision fresh right at the new boundary,
    while trusting our known weights everywhere else.

    Raises pycento.scansion.ScansionUnavailable if the compiled grammar
    archive isn't available (see scripts/fetch_latin_scansion.sh). Call
    sites must go through resolve_merge_slot()'s `allow_unchecked` gate to
    skip this entirely rather than calling rescan_joint directly.
    """
    from pycento.scansion import is_valid_hexameter, macronize_words

    text = macronize_words(list(words_a) + list(words_b))
    if not text.strip():
        return RescanResult(False, "empty joint text")
    if is_valid_hexameter(text):
        return RescanResult(True, f"scanned OK: {text!r}")
    return RescanResult(False, f"failed to scan as a valid hexameter: {text!r}")


def pick_candidate(candidates: List[dict], used_refs: set) -> dict:
    """Pick a random candidate, preferring ones not already used elsewhere
    in the poem (falls back to the full pool if every candidate is used)."""
    pool = [e for e in candidates if e["id"] not in used_refs] or candidates
    return random.choice(pool)


@dataclass
class MergeStats:
    """Counters for how merge-slot resolution actually went, across an
    entire generation run (accumulated across every poem, not reset per
    poem) -- surfaced at the end of step-04/step-05's run so it's visible
    how often an independently-combined merge gets thrown out by rescan_joint
    versus how often a pre-validated adjacent pair could be used instead."""
    pair_used: int = 0
    independent_resolved: int = 0
    elision_checks: int = 0
    elision_rejected: int = 0
    rescan_attempts: int = 0
    rescan_rejected: int = 0
    slots_given_up: int = 0

    def summary(self) -> str:
        total_independent = self.independent_resolved + self.slots_given_up
        lines = [
            f"  {self.pair_used} slot(s) used a pre-validated adjacent-verse pair (no rescan needed)",
        ]
        if self.elision_checks:
            lines.append(
                f"  {self.elision_checks} elision check(s): "
                f"{self.elision_rejected} rejected (elided final syllable would no longer "
                f"elide against the glued-in next word) "
                f"({100 * self.elision_rejected // self.elision_checks}% thrown out)"
            )
        if self.rescan_attempts:
            lines.append(
                f"  {self.rescan_attempts} independent rescan attempt(s): "
                f"{self.rescan_attempts - self.rescan_rejected} passed, "
                f"{self.rescan_rejected} rejected "
                f"({100 * self.rescan_rejected // self.rescan_attempts}% thrown out)"
            )
        if total_independent:
            lines.append(
                f"  {self.independent_resolved}/{total_independent} independent slot(s) "
                f"resolved; {self.slots_given_up} gave up after exhausting retries"
            )
        return "\n".join(lines)


def resolve_merge_slot(
    pair_entries: List[List[dict]],
    a_candidates: List[dict],
    b_candidates: List[dict],
    used_refs: set,
    allow_unchecked: bool,
    max_attempts: int = 30,
    stats: Optional[MergeStats] = None,
) -> Optional[Tuple[List[Word], List[Word], List[str]]]:
    """Resolve a two-segment slot (a cross-line continuation, or any other
    two-segment combination), returning (words_a, words_b, [id_a, id_b]).

    1. Prefer a pre-validated adjacent pair when `pair_entries` is non-empty
       -- these are two Virgil verses confirmed to be genuinely consecutive
       in the source text, so the joint between them is already valid,
       exactly as it was in the real Virgil corpus. No re-scan needed.
    2. Otherwise, independently draw one candidate from each side and either
       accept it unchecked (if `allow_unchecked`) or re-scan the joint,
       retrying with a fresh random draw up to `max_attempts` times. A pair
       that fails elision or rescan is removed from its side's pool for the
       remaining attempts (falling back to the full pool once every
       candidate on a side has been tried and failed), so retries actually
       explore new combinations instead of risking a repeat draw of the
       same bad candidate.

    Returns None if there are no candidates at all, or every attempt fails
    re-scan -- the caller should skip the whole poem in that case. Pass
    `stats` (a shared MergeStats instance) to accumulate counts of how often
    each path was taken and how often rescan_joint threw a merge out.
    """
    if pair_entries:
        pool = [
            pair for pair in pair_entries
            if pair[0]["id"] not in used_refs and pair[1]["id"] not in used_refs
        ] or pair_entries
        entry_a, entry_b = random.choice(pool)
        if stats is not None:
            stats.pair_used += 1
        return entry_to_words(entry_a), entry_to_words(entry_b), [entry_a["id"], entry_b["id"]]

    if not a_candidates or not b_candidates:
        if stats is not None:
            stats.slots_given_up += 1
        return None

    # Only the scarcer side's failed draw gets excluded from its pool on a
    # rejection -- the other side keeps its full pool available (re-drawing
    # the same ref there across attempts is fine, reuse isn't forbidden).
    # Constraining both sides on every rejection burns through the smaller
    # pool's already-limited diversity for no benefit, and can exhaust it
    # into pure-fallback (i.e. random, unexcluded) draws well before
    # max_attempts is reached.
    shrink_a = len(a_candidates) <= len(b_candidates)
    failed_a: set = set()
    failed_b: set = set()
    for _ in range(max_attempts):
        entry_a = pick_candidate(a_candidates, used_refs | failed_a)
        entry_b = pick_candidate(b_candidates, used_refs | failed_b)
        words_a, words_b = entry_to_words(entry_a), entry_to_words(entry_b)
        if stats is not None:
            stats.elision_checks += 1
        if not elision_ok(words_a, words_b):
            if stats is not None:
                stats.elision_rejected += 1
            (failed_a if shrink_a else failed_b).add((entry_a if shrink_a else entry_b)["id"])
            continue
        if allow_unchecked:
            if stats is not None:
                stats.independent_resolved += 1
            return words_a, words_b, [entry_a["id"], entry_b["id"]]
        result = rescan_joint(words_a, words_b)
        if stats is not None:
            stats.rescan_attempts += 1
        if result.valid:
            if stats is not None:
                stats.independent_resolved += 1
            return words_a, words_b, [entry_a["id"], entry_b["id"]]
        if stats is not None:
            stats.rescan_rejected += 1
        (failed_a if shrink_a else failed_b).add((entry_a if shrink_a else entry_b)["id"])
    if stats is not None:
        stats.slots_given_up += 1
    return None


def resolve_pinned_slot(
    pinned_words: List[Word],
    pinned_is_start: bool,
    free_candidates: List[dict],
    used_refs: set,
    allow_unchecked: bool,
    max_attempts: int = 30,
    stats: Optional[MergeStats] = None,
) -> Optional[Tuple[List[Word], str]]:
    """Resolve the one FREE side of a two-segment slot whose other side is
    already fixed -- e.g. a cross-line continuation boundary, where the
    pinned side was drawn from a pre-validated adjacent-Virgil-verse pair
    and must not be redrawn, but the line it belongs to may still need an
    ordinary (independently drawn) second segment to complete its own
    hexameter.

    Draws a candidate for the free side and re-scans the joint against the
    pinned words (unless `allow_unchecked`), retrying up to `max_attempts`
    times. A candidate that fails elision or rescan is removed from the pool
    for the remaining attempts (falling back to the full pool once every
    candidate has been tried and failed). Returns (free_words, free_id), or
    None if no candidates exist or every attempt fails re-scan.
    """
    if not free_candidates:
        if stats is not None:
            stats.slots_given_up += 1
        return None

    failed: set = set()
    for _ in range(max_attempts):
        entry_free = pick_candidate(free_candidates, used_refs | failed)
        words_free = entry_to_words(entry_free)
        words_a, words_b = (pinned_words, words_free) if pinned_is_start else (words_free, pinned_words)
        if stats is not None:
            stats.elision_checks += 1
        if not elision_ok(words_a, words_b):
            if stats is not None:
                stats.elision_rejected += 1
            failed.add(entry_free["id"])
            continue
        if allow_unchecked:
            if stats is not None:
                stats.independent_resolved += 1
            return words_free, entry_free["id"]
        result = rescan_joint(words_a, words_b)
        if stats is not None:
            stats.rescan_attempts += 1
        if result.valid:
            if stats is not None:
                stats.independent_resolved += 1
            return words_free, entry_free["id"]
        failed.add(entry_free["id"])
        if stats is not None:
            stats.rescan_rejected += 1
    if stats is not None:
        stats.slots_given_up += 1
    return None


@dataclass
class ResolvedSegment:
    source: str
    words: List[Word]
    continued: bool = False


def assemble_lines(resolved: List[List[ResolvedSegment]]) -> List[Line]:
    """`resolved` is one list of ResolvedSegment per output cento line."""
    return [
        Line(
            idx=idx,
            segments=[
                Segment(source=rs.source, words=rs.words, continued=rs.continued)
                for rs in segs
            ],
        )
        for idx, segs in enumerate(resolved, start=1)
    ]


def write_poem(lines: List[Line], out_path: str) -> None:
    os.makedirs(op.dirname(out_path), exist_ok=True)
    root = lines_to_compact_tree(lines)
    et.indent(root, space="    ")
    et.ElementTree(root).write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)

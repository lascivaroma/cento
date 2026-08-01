# Elision-safety fix: decision log and stats history

Context: `step-04-Generate-Centos-Sequence.py` ("exact") and
`step-05-Generate-Centos-Metric-Close.py` ("loose") both glue independently
chosen Virgil segments together to build generated centos. Gluing two
segments that weren't originally adjacent can silently break elision: if a
segment's last syllable was marked `elided` in the gold data (elided
against whatever *originally* followed it), and the newly glued-in next
segment doesn't start with a vowel, the elision no longer holds but the
compact output still renders the syllable as dropped.

All stats below are from `--seed 42`, real scansion checking enabled (no
`--allow-unchecked-merges`), run against the compiled `latin_scansion`
grammar at `vendor/latin_scansion/grammars/all.far`.

## 1. Add the elision check (`pycento/generate.py`)

Added `elision_ok(words_a, words_b)`: true unless `words_a`'s last syllable
is `elided` and `words_b`'s first letter isn't a/e/i/o/u. Needs no
compiled grammar, so it always runs regardless of `--allow-unchecked-merges`.
Wired into `resolve_merge_slot()` and `resolve_pinned_slot()`, ahead of the
existing `rescan_joint()` call. `MergeStats` gained `elision_checks` /
`elision_rejected`, reported separately from the rescan counters.

- step-04, count=1000: `26000 slot(s) used a pre-validated adjacent-verse
  pair` — the elision check never fired. All 26 distinct continuation
  patterns in `scheme.json` have real pre-validated adjacent-Virgil-verse
  pairs available (17 to 2505 pairs each, verified against
  `data/segment_table.json`), so `resolve_merge_slot()` never falls into the
  independent-draw branch in step-04.
- step-05, count=1000: `215447 elision check(s): 9887 rejected (4%)`,
  `205560 rescan attempt(s): 61332 passed, 144228 rejected (70%)`,
  `61307/82975 independent slot(s) resolved; 21668 gave up`,
  `21668 line(s) skipped` overall. step-05's same-line splits are never
  eligible for pre-validated pairs, so this is where the check actually
  bites.

Also fixed step-05's "both sides pinned" branch in `resolve_line()`
(`step-05-Generate-Centos-Metric-Close.py`) — a rare case (a line
sandwiched between two `type="sq"` continuations) that previously accepted
the joint with **no validation at all**, despite a comment saying it
needed it. Now runs `elision_ok()` + `rescan_joint()` and raises
`LineSkipped` if either fails (neither side can be redrawn).

## 2. Real bug found: `conclamat primusque` + `rapidive`

User-found case in an early `exact/cento_0001.xml`: `primusque` (elided
`-que`, 2 syllables) glued to `rapidive` (consonant-initial) — the elision
was invalid but the output kept it dropped anyway.

**Root cause**: this pair came from step-04's *ordinary same-line* 2-segment
split (e.g. an H1+H2 split at the caesura). Per `pycento/scheme.py`'s
row semantics, an ordinary same-line split is **two separate single-segment
rows in sequence**, not a 2-segment continuation row — so it was drawn
through step-04's `len(segs) == 1` branch in `generate_poem()`, completely
independently of `resolve_merge_slot()`/`resolve_pinned_slot()`. That path
had **zero** joint validation, elision or otherwise.

**Fix**: added `_pick_line_segment()` to `step-04-Generate-Centos-Sequence.py`,
which validates the boundary against the immediately preceding segment
already placed in the current line (elision check, then `rescan_joint()`
unless `--allow-unchecked-merges`), retrying up to `max_attempts` times.

- step-04, count=1000, `max_attempts=8` (first fix, before tuning):
  `Generated 227/1000 poems (773 skipped)`,
  `46666 elision check(s): 8286 rejected (17%)`,
  `38380 rescan attempt(s): 34550 passed, 3830 rejected (9%)`,
  `0/773 independent slot(s) resolved; 773 gave up`.
  Confirms the check works, but yield collapsed hard — most of the
  drop is same-line joints that were previously invalid and silently
  accepted.

## 3. Tuning: `max_attempts` 8 → 30, exclude failed draws from the pool

Two problems with the retry loop: (a) 8 attempts is a small budget once a
real check is actually rejecting candidates, and (b) `pick_candidate()`
could redraw the *same* already-failed candidate on a later attempt,
wasting budget. Fixed by tracking a per-slot `failed` set and excluding it
from the pool on each retry (falling back to the full pool once every
candidate's been tried), across all three resolvers:
`resolve_merge_slot()`, `resolve_pinned_slot()` (`pycento/generate.py`),
and `_pick_line_segment()` (`step-04-Generate-Centos-Sequence.py`).

- step-04, count=1000, `max_attempts=30`, exclude-both-sides-on-failure:
  `Generated 464/1000 poems (536 skipped)`,
  `75668 elision check(s): 14232 rejected (18%)`,
  `61436 rescan attempt(s): 44916 passed, 16520 rejected (26%)`,
  `0/536 independent slot(s) resolved; 536 gave up`.
  Yield roughly doubled (227 → 464) versus step 2's `max_attempts=8` run.

## 4. Only exclude the scarcer side of a pair

In `resolve_merge_slot()`, a rejected `(entry_a, entry_b)` pair was
excluding *both* `entry_a` from `a_candidates` and `entry_b` from
`b_candidates` on every retry. If one side's candidate pool is much larger
than the other, this needlessly burns through the larger pool's diversity
for no benefit — the real bottleneck is always the smaller side, and
reusing an already-tried ref on the larger side is fine (nothing forbids
reusing a source ref within a poem). Changed to compute
`shrink_a = len(a_candidates) <= len(b_candidates)` once per slot and only
add the scarcer side's drawn id to its `failed` set on rejection.

- step-04, count=2500 (to compensate for the ~46% attrition and get
  comfortably over 1000 valid poems):
  `Generated 1162/2500 poems (1338 skipped)`,
  `189511 elision check(s): 35529 rejected (18%)`,
  `153982 rescan attempt(s): 112632 passed, 41350 rejected (26%)`,
  `0/1338 independent slot(s) resolved; 1338 gave up`.
  Same ~46% yield rate as the count=1000 run in step 3 (464/1000 ≈ 46.4%
  vs 1162/2500 ≈ 46.5%) — confirms the remaining failures are **genuine
  per-pattern coverage gaps** (some same-line split patterns have small
  candidate pools where *nothing* in the pool satisfies elision+rescan
  against the fixed neighboring segment), not an artifact of attempt
  budget or draw-repetition. More attempts or smarter exclusion helps up
  to a point (step 2 → step 3), then plateaus (step 3 → step 4).
  Verified deterministic: rerunning the identical command reproduced
  `1162/2500` byte-for-byte.

- step-05, count=1000 (same final code, automatically inherits the
  `max_attempts=30` + scarcer-side-exclusion changes to
  `resolve_merge_slot()`/`resolve_pinned_slot()` since step-05 imports
  them unchanged):
  `Generated 1000/1000 poems (0 skipped)`,
  `21380 line(s) skipped` (vs 21668 in step 1 — negligible change),
  `600273 elision check(s): 23585 rejected (3%)`,
  `576688 rescan attempt(s): 61620 passed, 515068 rejected (89%)`,
  `61569/82949 independent slot(s) resolved; 21380 gave up`
  (vs 61307/82975 in step 1 — also negligible change).
  Same conclusion as step-04: raising `max_attempts` from 8 to 30 barely
  moved the needle for step-05 either (61307 → 61569 resolved slots) —
  most of its unresolved slots are pool-exhaustion dead ends, not
  budget-limited.

## 5. Final output

`data/generated-compact/exact/` and `data/generated-compact/loose/` were
regenerated from scratch with the final code (`--seed 42`) and trimmed to
exactly 1000 poems each:

- **exact**: the count=2500 run's 1162 successes, kept in ascending
  original-attempt order and renumbered contiguously `cento_0001.xml` ..
  `cento_1000.xml` (poem numbering has no semantic meaning inside the XML
  — only per-line `n=` attributes exist — so renumbering is safe).
- **loose**: the count=1000 run already produced exactly 1000 files (every
  attempt "succeeds" as a poem in step-05; only individual lines get
  skipped), so no trimming was needed.

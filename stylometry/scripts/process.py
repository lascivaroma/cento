#!/usr/bin/env python3
"""Thin wrapper around ``latin_masking`` stage 1 and stage 2 pipelines.

Runs the latin_masking package on preprocessed ``.txt`` files to perform
sentence splitting, adverb extraction (stage 1), and masking (stage 2).

When both stages run together, stage 1 regenerates and overwrites
``common_adverbs.txt`` before stage 2 reads it. Pass ``--keep-adverbs``
to preserve the existing (manually reviewed) ``common_adverbs.txt``
instead — useful when the corpus is unchanged and the adverb list
needs no revision. In that mode the existing file is restored after
stage 1 so stage 2 consumes the original list.

Usage:
    python3 process.py --stage1 --output-dir ./output 'data/*.txt'
    python3 process.py --stage2 --output-dir ./output 'data/*.txt'
    python3 process.py --stage1 --stage2 --output-dir ./output 'data/*.txt'
    python3 process.py --stage1 --stage2 --keep-adverbs --output-dir ./output 'data/*.txt'
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path
from typing import List

from latin_masking.pipeline import run_pipeline_stage1, run_pipeline_stage2
from latin_masking.types import MaskingConfig


def _resolve_paths(inputs: List[str]) -> List[Path]:
    """Expand glob patterns into a sorted list of existing file paths.

    Args:
        inputs: Filename(s) or glob patterns.

    Returns:
        Sorted, deduplicated list of resolved paths.
    """
    paths: List[Path] = []
    for inp in inputs:
        expanded = sorted(glob.glob(inp))
        if expanded:
            paths.extend(Path(p) for p in expanded)
        else:
            paths.append(Path(inp))
    return sorted(set(paths))


def stage1(input_paths: List[Path], config: MaskingConfig) -> None:
    """Run latin_masking stage 1 on the given files.

    Stage 1 performs sentence splitting and adverb extraction.  After
    processing, the sentence count is written back to each corresponding
    JSON sidecar file.

    Args:
        input_paths: Paths to input ``.txt`` files.
        config: Masking pipeline configuration.
    """
    import json as _json

    print(f"Stage1: processing {len(input_paths)} files...")
    for i, p in enumerate(input_paths, start=1):
        print(f"  [{i}/{len(input_paths)}] {p.name}", flush=True)

    result = run_pipeline_stage1(input_paths, config=config, preserve_eol=True)

    total_sentences: int = sum(result.sentences_per_file.values())
    print(f"Stage1: {total_sentences} sentences from {len(input_paths)} files")
    print(f"  common adverbs written to {result.common_adverbs_path}")

    # Write sentence counts back to sidecar JSON files.
    for txt_path, sent_count in result.sentences_per_file.items():
        sidecar_path = txt_path.with_suffix(".json")
        if sidecar_path.exists():
            sidecar: dict = _json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar["sentence_count"] = sent_count
            sidecar_path.write_text(
                _json.dumps(sidecar, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def stage2(input_paths: List[Path], config: MaskingConfig) -> None:
    """Run latin_masking stage 2 on the given files.

    Stage 2 performs masking.

    Args:
        input_paths: Paths to input ``.txt`` files.
        config: Masking pipeline configuration.
    """
    result = run_pipeline_stage2(input_paths, config=config)
    print(
        f"Stage2: {result.sentences_processed} sentences processed, "
        f"{len(result.output_files)} masked outputs"
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    p = argparse.ArgumentParser(
        description="Run latin_masking stage1 and/or stage2 on preprocessed .txt files."
    )
    p.add_argument(
        "inputs",
        nargs="+",
        help="Input .txt filename(s) or glob patterns",
    )
    p.add_argument(
        "--stage1",
        action="store_true",
        help="Run latin_masking stage1 (sentence splitting, adverb list)",
    )
    p.add_argument(
        "--stage2",
        action="store_true",
        help="Run latin_masking stage2 (masking)",
    )
    p.add_argument(
        "--output-dir",
        default="./output",
        help="Output directory for latin_masking (default ./output)",
    )
    default_cache = str(Path(__file__).resolve().parent.parent / "processed" / "udpipe_cache")
    p.add_argument(
        "--cache-dir",
        default=default_cache,
        help="Directory for cached UDPipe responses (default: processed/udpipe_cache).",
    )
    p.add_argument(
        "--keep-adverbs",
        action="store_true",
        help="Preserve the existing common_adverbs.txt across a combined "
             "stage1+stage2 run (do not let stage1 overwrite it)",
    )
    return p.parse_args()


def main() -> int:
    """Run the latin_masking pipeline stages.

    Returns:
        Exit code (0 on success, 2 if no stages requested).
    """
    args = parse_args()

    if not args.stage1 and not args.stage2:
        print("Nothing to do. Use --stage1 and/or --stage2.")
        return 2

    input_paths: List[Path] = _resolve_paths(args.inputs)
    if not input_paths:
        print("No input files found.")
        return 1

    config = MaskingConfig(
        output_dir=Path(args.output_dir),
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )

    # If keeping the existing adverb list across a combined run, snapshot
    # it before stage 1 (which would otherwise overwrite it) and restore
    # it afterwards so stage 2 reads the original reviewed list.
    adverb_backup = None
    if args.keep_adverbs and args.stage1 and args.stage2:
        adv_path = Path(config.common_adverbs_path)
        if adv_path.exists():
            adverb_backup = adv_path.read_bytes()

    if args.stage1:
        stage1(input_paths, config)

    if adverb_backup is not None:
        Path(config.common_adverbs_path).write_bytes(adverb_backup)
        print(f"Restored existing common adverbs from {config.common_adverbs_path}")

    if args.stage2:
        stage2(input_paths, config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

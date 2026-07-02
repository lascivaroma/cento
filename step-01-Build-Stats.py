"""Compute segment mora-lengths and schema for each Cento line, then visualize."""

import csv
import json
import os.path as op
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from pycento.data import parse_cento, Segment
from typing import Tuple, List
from collections import Counter

_ROOT = op.dirname(op.abspath(__file__))
_ALIGNED = op.join(_ROOT, "data", "gold", "cento.xml")

_MORA = {"long": 2, "short": 1, "anceps": 2, "elided": 0, "end": 2}
_COLORS = ["#4C72B0", "#DD8452", "#55A868"]


def segment_morae(seg: Segment) -> Tuple[int, List[Tuple[int, ...]]]:
    total = 0
    segs = [[]]
    for word in seg.words:
        for syll in word.syllables:
            total += _MORA.get(syll.length, 0)
            if syll.length == "elided":
                # segs[-1].append(0)
                continue
            elif length := _MORA.get(syll.length, 0):
                segs[-1].append(length)
            else:
                continue
    return total, [tuple(seg) for seg in segs if seg]


def line_schema(seg_data: list[tuple[int, bool]]) -> str:
    parts = []
    for morae, continued in seg_data:
        parts.append(f"~{morae}" if continued else str(morae))
    return "+".join(parts)


def main():
    lines = parse_cento(_ALIGNED)
    print(f"Parsed {len(lines)} lines")
    print(lines)

    table = []

    rows = []
    # last segment morae per line index, for continued-span length computation
    last_seg_morae_by_line: dict[int, int] = {}

    for line in lines:
        raw_seg_data = [(*segment_morae(s), s.continued) for s in line.segments]
        total = sum(m for m, *_ in raw_seg_data)

        # For continued segments, report combined length (prev last + own morae)
        seg_data = []
        for idx, (morae, scheme, continued) in enumerate(raw_seg_data):
            if continued:
                prev = last_seg_morae_by_line.get(line.idx - 1, 0)
                seg_data.append((prev + morae, True))
                table[-1].extend([0, *scheme])
            else:
                seg_data.append((morae, False))
                if idx == 0:
                    table.append([0, *scheme])
                else:
                    table.append(scheme)

        schema = line_schema(seg_data)
        if total != 24:
            print(f"  WARNING line {line.idx}: total morae = {total} (schema: {schema})", file=sys.stderr)

        row = {"line": line.idx, "n_segments": len(seg_data), "schema": schema, "total_morae": total}
        for i, (morae, cont) in enumerate(seg_data):
            row[f"seg{i+1}_morae"] = morae
            row[f"seg{i+1}_continued"] = cont
        rows.append(row)

        if raw_seg_data:
            last_seg_morae_by_line[line.idx] = raw_seg_data[-1][0]

    json_path = op.join(_ROOT, "scheme.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "table": table,
            "counter": Counter(map(str, table)),
        }, f, ensure_ascii=False, indent=4)

    total = 0
    for element in table:
        total += sum([x for l in element if isinstance(l, tuple) for x in l])
        print(f"{element}".replace("), 0", "), -|\n"))
        if total % 24 == 0:
            print()
    # --- CSV output ---
    csv_path = op.join(_ROOT, "segment_stats.csv")
    fieldnames = ["line", "n_segments",
                  "seg1_morae", "seg1_continued",
                  "seg2_morae", "seg2_continued",
                  "seg3_morae", "seg3_continued",
                  "schema", "total_morae"]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {csv_path}")

    # --- Print summary table ---
    schema_counts = Counter(r["schema"] for r in rows)
    # Build line index for lookup
    line_by_idx = {line.idx: line for line in lines}
    print("\nSchema distribution:")
    for schema, count in sorted(schema_counts.items(), key=lambda x: -x[1]):
        if count == 1:
            row = next(r for r in rows if r["schema"] == schema)
            line = line_by_idx[row["line"]]
            text = " ".join(w.text for w in line.words if w.text and w.text.strip())
            print(f"  {schema:30s}  {count}  (l.{row['line']}: {text})")
        else:
            print(f"  {schema:30s}  {count}")

    # --- Visualization ---
    fig_height = max(4, len(lines) * 0.18)
    fig, ax = plt.subplots(figsize=(6, fig_height))

    # Build color state: track last color index per cento line
    # so that a continued segment on line N picks up the color from line N-1's last segment
    last_color_by_line: dict[int, int] = {}

    for line in lines:
        y = line.idx - 1
        x = 0
        prev_last = last_color_by_line.get(line.idx - 1, -1)

        # If the first segment is NOT a continuation, start on a different color than prev line's last
        first_seg = line.segments[0] if line.segments else None
        if first_seg and not first_seg.continued:
            color_cursor = (prev_last + 1) % len(_COLORS)
        else:
            color_cursor = prev_last  # will be overridden by the continued branch below

        for seg in line.segments:
            morae, _ = segment_morae(seg)

            if seg.continued:
                # Inherit color from the last segment of the previous line
                color = _COLORS[prev_last % len(_COLORS)] if prev_last >= 0 else _COLORS[0]
                # Don't advance color_cursor — this slot is "owned" by the previous line
            else:
                color = _COLORS[color_cursor % len(_COLORS)]
                color_cursor += 1

            ax.barh(
                y=y,
                width=morae,
                left=x,
                height=0.85,
                color=color,
                edgecolor="#cccccc",
                linewidth=0.3,
            )
            x += morae

        last_color_by_line[line.idx] = (color_cursor - 1) % len(_COLORS) if color_cursor > 0 else 0

    # Foot grid lines at every 4 morae
    for foot_x in range(4, 25, 4):
        ax.axvline(x=foot_x, color="#444444", linewidth=0.5, linestyle="--", alpha=0.5)

    ax.set_xlim(0, 24)
    ax.set_ylim(-0.5, len(lines) - 0.5)
    ax.invert_yaxis()  # line 1 at top
    ax.axis("off")

    plt.tight_layout(pad=0.2)
    out_path = op.join(_ROOT, "segment_visualization.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()

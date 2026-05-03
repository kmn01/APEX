#!/usr/bin/env python3
"""Plot ``metrics.json`` files from sweep output directories (requires ``matplotlib``)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _collect_metrics(root: Path) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    root = root.resolve()
    # direct child dirs containing metrics.json
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        mp = d / "metrics.json"
        if mp.exists():
            rows.append((d.name, json.loads(mp.read_text())))
    # or root lists files
    mf = root / "metrics.json"
    if mf.exists():
        rows.append((root.name, json.loads(mf.read_text())))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="sweep folder with subruns")
    parser.add_argument("--output", type=Path, default=None, help="figure path (.png)")
    args = parser.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required: pip install 'apex[eval]' or matplotlib"
        ) from exc

    rows = _collect_metrics(args.input)
    if not rows:
        raise SystemExit(f"No metrics.json found under {args.input}")

    names = [r[0][:24] for r in rows]
    completions = [r[1].get("completed_instruction_count", 0) for r in rows]
    planned = [r[1].get("planned_spacetime_conflict_count", 0) for r in rows]
    exec_c = [r[1].get("executed_conflict_count", 0) for r in rows]

    fig, ax = plt.subplots(figsize=(min(14, max(6, len(names) * 0.5)), 5))
    x = range(len(names))
    ax.bar([i - 0.25 for i in x], completions, width=0.25, label="completed_instructions")
    ax.bar(x, planned, width=0.25, label="planned_spacetime_conflicts")
    ax.bar([i + 0.25 for i in x], exec_c, width=0.25, label="executed_conflicts")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.legend()
    ax.set_title("APEX sweep comparison")
    fig.tight_layout()
    outp = args.output or (args.input / "comparison.png")
    fig.savefig(outp, dpi=150)
    plt.close(fig)
    print(f"Wrote {outp}")


if __name__ == "__main__":
    main()

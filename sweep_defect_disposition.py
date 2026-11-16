#!/usr/bin/env python3
"""Generate a deterministic action-boundary table and SVG from one scenario."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from defect_disposition import DispositionInputs, decide


def sweep(base: DispositionInputs, confirmation_costs=(0.08, 0.10)) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for confirmation_cost in confirmation_costs:
        for response_detected in (False, True):
            for step in range(1, 20):
                prevalence = step * 0.05
                values = asdict(base)
                values.update(recoverable_prevalence=prevalence, confirmation_cost=confirmation_cost)
                result = decide(DispositionInputs(**values), response_detected)
                rows.append({
                    "confirmation_cost": confirmation_cost,
                    "response": "positive" if response_detected else "negative",
                    "recoverable_prevalence": prevalence,
                    "posterior_recoverable": result["posterior_recoverable"],
                    "recommended_action": result["recommended_action"],
                    **{f"expected_cost_{name}": cost for name, cost in result["expected_costs"].items()},
                })
    return rows


def render_svg(rows: list[dict[str, object]]) -> str:
    colors = {"rework": "#43aa8b", "hold_for_confirmation": "#f9c74f", "scrap": "#f94144"}
    bands = sorted({(row["confirmation_cost"], row["response"]) for row in rows})
    width, height, left, top, plot_width = 960, 300, 180, 42, 720
    band_height = 42
    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#090c10"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#e9ecef;font-size:13px}.small{fill:#9aa4b2;font-size:11px}</style>',
        '<text x="20" y="24" font-size="16">Synthetic defect-disposition action boundaries</text>',
    ]
    for band_index, (cost, response) in enumerate(bands):
        y = top + band_index * band_height
        chunks.append(f'<text x="20" y="{y + 23}">c={cost:.2f} · {response}</text>')
        for row in [item for item in rows if item["confirmation_cost"] == cost and item["response"] == response]:
            x = left + (float(row["recoverable_prevalence"]) - 0.025) * plot_width
            chunks.append(f'<rect x="{x:.2f}" y="{y}" width="{plot_width * 0.05 + 0.5:.2f}" height="30" fill="{colors[str(row["recommended_action"])]}"/>')
    axis_y = top + len(bands) * band_height + 12
    chunks.append(f'<line x1="{left}" y1="{axis_y}" x2="{left + plot_width}" y2="{axis_y}" stroke="#9aa4b2"/>')
    for value in (0.05, 0.25, 0.50, 0.75, 0.95):
        x = left + (value - 0.025) * plot_width
        chunks.append(f'<text class="small" x="{x - 10:.2f}" y="{axis_y + 18}">{value:.2f}</text>')
    chunks.extend([
        f'<text class="small" x="{left + 270}" y="{axis_y + 40}">assumed recoverable-defect prevalence</text>',
        '<rect x="180" y="270" width="14" height="14" fill="#43aa8b"/><text class="small" x="200" y="281">rework</text>',
        '<rect x="330" y="270" width="14" height="14" fill="#f9c74f"/><text class="small" x="350" y="281">hold for confirmation</text>',
        '<rect x="550" y="270" width="14" height="14" fill="#f94144"/><text class="small" x="570" y="281">scrap</text>',
        '<text class="small" x="700" y="281">illustrative inputs only</text>',
        '</svg>',
    ])
    return "\n".join(chunks) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--csv-out", type=Path, required=True)
    parser.add_argument("--svg-out", type=Path, required=True)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    rows = sweep(DispositionInputs(**scenario["inputs"]))
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.svg_out.write_text(render_svg(rows), encoding="utf-8")


if __name__ == "__main__":
    main()

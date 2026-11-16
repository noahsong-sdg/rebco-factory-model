#!/usr/bin/env python3
"""CLI for the transparent REBCO factory model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from model import ModelInputError, run_factory


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Factory model: {result['scenario_name']}",
        "",
        f"Reference condition: {result['reference_condition']}",
        "",
        f"> {result['evidence_notice']}",
        "",
        f"Model boundary: {result['model_boundary']}",
        "",
        "## Headline outputs",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Bottleneck | {result['bottleneck_step']} |",
        f"| Gross master web | {result['gross_master_m_per_year']:,.0f} m/year |",
        f"| Gross slit tape | {result['gross_slit_tape_m_per_year']:,.0f} m/year |",
        f"| Gross 12-mm-equivalent tape | {result['gross_12mm_equivalent_m_per_year']:,.0f} m/year |",
        f"| Independent process retention | {result['independent_process_retention']:.2%} |",
        f"| Piece retention | {result['piece_retention']:.2%} |",
        f"| Saleable tape | {result['saleable_tape_m_per_year']:,.0f} m/year |",
        f"| Qualified-grade share | {result['qualified_grade_share']:.2%} |",
        f"| Qualified tape | {result['qualified_tape_m_per_year']:,.0f} m/year |",
        f"| Qualified 12-mm-equivalent tape | {result['qualified_12mm_equivalent_m_per_year']:,.0f} m/year |",
        f"| Annual manufacturing cost | {_money(result['annual_manufacturing_cost'])} |",
        f"| Manufacturing cost / qualified m | {_money(result['manufacturing_cost_per_qualified_m'])} |",
        f"| Qualified kA·m | {result['qualified_kam_per_year']:,.0f} kA·m/year |",
        f"| Manufacturing cost / kA·m | {_money(result['manufacturing_cost_per_kam'])} |",
        "",
        "## Step capacities",
        "",
        "| Step | Effective speed | Master-web capacity |",
        "|---|---:|---:|",
    ]
    for step in result["step_capacities"]:
        lines.append(
            f"| {step['name']} | {step['effective_speed_m_per_hour']:,.1f} m/h | "
            f"{step['annual_capacity_master_m']:,.0f} m/year |"
        )
    lines.extend(
        [
            "",
            "## Grade outputs",
            "",
            "| Grade | Length | Qualified? | Ic at reference | Allocated manufacturing cost / kA·m |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for grade in result["grades"]:
        lines.append(
            f"| {grade['name']} | {grade['output_length_m']:,.0f} m | "
            f"{'yes' if grade['counts_as_qualified_output'] else 'no'} | "
            f"{grade['ic_a_at_reference']:,.0f} A | "
            f"{_money(grade['allocated_manufacturing_cost_per_kam'])} |"
        )
    lines.extend(
        [
            "",
            "## Order-risk indicators",
            "",
            f"- Single-lane clean-order probability: {result['single_lane_clean_order_probability']:.2%}",
            f"- All-lanes clean-order probability: {result['all_lanes_clean_order_probability']:.2%}",
            "",
            "These probabilities use the synthetic Poisson-defect assumptions in the input.",
            "They are not supplier forecasts.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Scenario JSON")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    try:
        result = run_factory(config)
    except ModelInputError as error:
        parser.error(str(error))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    markdown = _render_markdown(result)
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

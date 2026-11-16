#!/usr/bin/env python3
"""Compare piece yield while holding the expected marginal defect rate fixed."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from defect_simulation import simulate_piece_yield
from model import ModelInputError, _positive


def compare_defect_models(config: dict[str, Any]) -> dict[str, Any]:
    """Run a preregistered minimum-piece/model sweep from one common scenario."""
    minimum_lengths = config.get("minimum_shippable_piece_m_sweep")
    variants = config.get("variants")
    if not isinstance(minimum_lengths, list) or not minimum_lengths:
        raise ModelInputError("minimum_shippable_piece_m_sweep must be a non-empty list")
    if not isinstance(variants, list) or not variants:
        raise ModelInputError("variants must be a non-empty list")

    base = {
        key: value
        for key, value in config.items()
        if key not in {"minimum_shippable_piece_m_sweep", "variants", "diagnostic_question"}
    }
    expected_rate = _positive(
        base["common_mode_defects_per_master_km"] + base["lane_defects_per_lane_km"],
        "expected marginal defect rate",
        allow_zero=True,
    )
    rows: list[dict[str, Any]] = []
    for minimum in minimum_lengths:
        _positive(minimum, "minimum shippable piece", allow_zero=True)
        for variant in variants:
            if not isinstance(variant, dict) or not isinstance(variant.get("name"), str):
                raise ModelInputError("every variant requires a name")
            scenario = copy.deepcopy(base)
            scenario.update({key: value for key, value in variant.items() if key != "name"})
            scenario["minimum_shippable_piece_m"] = minimum
            scenario_rate = (
                scenario["common_mode_defects_per_master_km"]
                + scenario["lane_defects_per_lane_km"]
            )
            if not abs(scenario_rate - expected_rate) < 1e-12:
                raise ModelInputError("variants must preserve the expected marginal defect rate")
            result = simulate_piece_yield(scenario)
            rows.append(
                {
                    "variant": variant["name"],
                    "minimum_shippable_piece_m": minimum,
                    "mean_lane_retained_fraction": result["mean_lane_retained_fraction"],
                    "p10_lane_retained_fraction": result["p10_lane_retained_fraction"],
                    "mean_worst_lane_retained_fraction": result["mean_worst_lane_retained_fraction"],
                }
            )
    return {
        "diagnostic_question": config.get("diagnostic_question", ""),
        "expected_marginal_defects_per_lane_km": expected_rate,
        "rows": rows,
        "boundary": "Synthetic comparison; it tests model consequences, not any producer's yield.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = compare_defect_models(json.loads(args.config.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

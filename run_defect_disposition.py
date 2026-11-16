#!/usr/bin/env python3
"""Run a bounded synthetic defect-disposition scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from defect_disposition import DispositionInputs, decide


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    inputs = DispositionInputs(**scenario["inputs"])
    result = {
        "scenario": scenario["name"],
        "route_label": scenario["route_label"],
        "evidence_boundary": scenario["evidence_boundary"],
        "negative_response": decide(inputs, False),
        "positive_response": decide(inputs, True),
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a synthetic REBCO factory ramp scenario."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ramp_economics import run_ramp


def clean(value):
    if isinstance(value, float) and math.isinf(value):
        return None
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = clean(run_ramp(json.loads(args.scenario.read_text(encoding="utf-8"))))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a reproducible long-length REBCO defect scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from defect_simulation import simulate_piece_yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    result = simulate_piece_yield(json.loads(args.config.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Seeded long-length defect simulation for REBCO master-web and slit-lane risk."""

from __future__ import annotations

import math
import random
from statistics import fmean
from typing import Any

from model import ModelInputError, _positive


def _poisson_count(mean: float, rng: random.Random) -> int:
    if mean <= 0:
        return 0
    # Poisson additivity avoids Knuth underflow for large means.
    if mean > 30:
        chunks = math.ceil(mean / 30)
        return sum(_poisson_count(mean / chunks, rng) for _ in range(chunks))
    limit = math.exp(-mean)
    product = 1.0
    count = 0
    # Draw at least once: exp(-mean) can round to 1 for tiny positive means.
    while True:
        count += 1
        product *= rng.random()
        if product <= limit:
            return count - 1


def _poisson_points(rate_per_km: float, length_m: float, rng: random.Random) -> list[float]:
    rate_per_m = rate_per_km / 1000.0
    if rate_per_m == 0:
        return []
    points: list[float] = []
    position = rng.expovariate(rate_per_m)
    while position < length_m:
        points.append(position)
        position += rng.expovariate(rate_per_m)
    return points


def _clustered_points(
    total_rate_per_km: float,
    length_m: float,
    mean_children: float,
    cluster_sigma_m: float,
    rng: random.Random,
) -> list[float]:
    if total_rate_per_km == 0:
        return []
    parent_rate = total_rate_per_km / mean_children
    buffer = 4 * cluster_sigma_m
    parents = _poisson_points(parent_rate, length_m + 2 * buffer, rng)
    points: list[float] = []
    for raw_parent in parents:
        parent = raw_parent - buffer
        for _ in range(_poisson_count(mean_children, rng)):
            child = rng.gauss(parent, cluster_sigma_m)
            if 0 <= child < length_m:
                points.append(child)
    return sorted(points)


def retained_fraction(
    defect_positions_m: list[float],
    length_m: float,
    excluded_length_m: float,
    minimum_piece_m: float,
) -> float:
    """Return usable-length fraction after exclusions and minimum-piece cutting."""
    length_m = _positive(length_m, "length_m")
    excluded_length_m = _positive(excluded_length_m, "excluded_length_m", allow_zero=True)
    minimum_piece_m = _positive(minimum_piece_m, "minimum_piece_m", allow_zero=True)
    if not defect_positions_m:
        return 1.0 if length_m >= minimum_piece_m else 0.0
    intervals = sorted(
        (max(0.0, point), min(length_m, point + excluded_length_m))
        for point in defect_positions_m
        if 0 <= point < length_m
    )
    merged: list[tuple[float, float]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    usable = 0.0
    cursor = 0.0
    for start, end in merged:
        gap = start - cursor
        if gap >= minimum_piece_m:
            usable += gap
        cursor = max(cursor, end)
    final_gap = length_m - cursor
    if final_gap >= minimum_piece_m:
        usable += final_gap
    return usable / length_m


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def simulate_piece_yield(config: dict[str, Any]) -> dict[str, Any]:
    length = _positive(config["master_length_m"], "master_length_m")
    lanes_value = _positive(config["slit_lanes"], "slit_lanes")
    if int(lanes_value) != lanes_value:
        raise ModelInputError("slit_lanes must be an integer")
    lanes = int(lanes_value)
    common_rate = _positive(config["common_mode_defects_per_master_km"], "common rate", allow_zero=True)
    lane_rate = _positive(config["lane_defects_per_lane_km"], "lane rate", allow_zero=True)
    excluded = _positive(config["excluded_length_per_defect_m"], "excluded length", allow_zero=True)
    minimum = _positive(config["minimum_shippable_piece_m"], "minimum piece", allow_zero=True)
    repetitions_value = _positive(config["replications"], "replications")
    if int(repetitions_value) != repetitions_value:
        raise ModelInputError("replications must be an integer")
    repetitions = int(repetitions_value)
    model = config.get("defect_model")
    if model not in {"poisson", "clustered"}:
        raise ModelInputError("defect_model must be poisson or clustered")
    mean_children = float(config.get("mean_children_per_cluster", 1.0))
    sigma = float(config.get("cluster_sigma_m", 0.0))
    if model == "clustered":
        _positive(mean_children, "mean_children_per_cluster")
        _positive(sigma, "cluster_sigma_m")
    seed = config.get("seed")
    if not isinstance(seed, int):
        raise ModelInputError("seed must be an integer for reproducibility")
    notice = config.get("evidence_notice")
    if not isinstance(notice, str) or not notice.strip():
        raise ModelInputError("evidence_notice must be a non-empty string")

    rng = random.Random(seed)
    replicate_means: list[float] = []
    replicate_minima: list[float] = []
    common_counts: list[float] = []
    lane_counts: list[float] = []
    generator = _poisson_points if model == "poisson" else None
    for _ in range(repetitions):
        if generator:
            common = generator(common_rate, length, rng)
        else:
            common = _clustered_points(common_rate, length, mean_children, sigma, rng)
        lane_fractions: list[float] = []
        lane_count = 0
        for _lane in range(lanes):
            if generator:
                specific = generator(lane_rate, length, rng)
            else:
                specific = _clustered_points(lane_rate, length, mean_children, sigma, rng)
            lane_count += len(specific)
            lane_fractions.append(retained_fraction(common + specific, length, excluded, minimum))
        replicate_means.append(fmean(lane_fractions))
        replicate_minima.append(min(lane_fractions))
        common_counts.append(len(common))
        lane_counts.append(lane_count / lanes)

    return {
        "defect_model": model,
        "seed": seed,
        "replications": repetitions,
        "quantile_population": "replicate-level mean across lanes, not pooled individual lanes",
        "cluster_boundary_approximation": "Gaussian parents truncated at 4 sigma beyond each web end",
        "mean_lane_retained_fraction": fmean(replicate_means),
        "p10_lane_retained_fraction": _quantile(replicate_means, 0.10),
        "p50_lane_retained_fraction": _quantile(replicate_means, 0.50),
        "p90_lane_retained_fraction": _quantile(replicate_means, 0.90),
        "mean_worst_lane_retained_fraction": fmean(replicate_minima),
        "mean_common_defect_count": fmean(common_counts),
        "mean_lane_specific_defect_count": fmean(lane_counts),
        "evidence_notice": notice,
        "boundary": "Synthetic stochastic output; not a vendor yield or validated defect process.",
    }

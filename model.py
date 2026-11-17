"""Transparent, route-agnostic REBCO factory teaching model."""

from __future__ import annotations

import math
from typing import Any


class ModelInputError(ValueError):
    """Raised when a model configuration violates a domain invariant."""


def _positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    value = float(value)
    valid = value >= 0 if allow_zero else value > 0
    if not valid or not math.isfinite(value):
        relation = "non-negative" if allow_zero else "positive"
        raise ModelInputError(f"{name} must be finite and {relation}")
    return value


def _fraction(value: float, name: str, *, allow_zero: bool = False) -> float:
    value = float(value)
    lower_ok = value >= 0 if allow_zero else value > 0
    if not lower_ok or value > 1 or not math.isfinite(value):
        lower = "0" if allow_zero else "0 (exclusive)"
        raise ModelInputError(f"{name} must be between {lower} and 1")
    return value


def _validate_config(config: dict[str, Any]) -> None:
    factory = config.get("factory")
    steps = config.get("steps")
    defects = config.get("defects")
    grades = config.get("grades")
    if not isinstance(factory, dict):
        raise ModelInputError("factory must be an object")
    if not isinstance(steps, list) or not steps:
        raise ModelInputError("steps must be a non-empty list")
    if not isinstance(defects, dict):
        raise ModelInputError("defects must be an object")
    if not isinstance(grades, list) or not grades:
        raise ModelInputError("grades must be a non-empty list")
    reference_condition = config.get("reference_condition")
    if not isinstance(reference_condition, str) or not reference_condition.strip():
        raise ModelInputError("reference_condition must be a non-empty string")
    evidence_notice = config.get("evidence_notice")
    if not isinstance(evidence_notice, str) or not evidence_notice.strip():
        raise ModelInputError("evidence_notice must be a non-empty string")

    _positive(factory["scheduled_hours_per_year"], "scheduled_hours_per_year")
    _positive(factory["slit_lanes"], "slit_lanes")
    if int(factory["slit_lanes"]) != float(factory["slit_lanes"]):
        raise ModelInputError("slit_lanes must be an integer")
    _fraction(factory["slitting_length_yield"], "slitting_length_yield")
    master_width = _positive(factory["master_width_mm"], "master_width_mm")
    slit_width = _positive(factory["slit_tape_width_mm"], "slit_tape_width_mm")
    if int(factory["slit_lanes"]) * slit_width > master_width + 1e-9:
        raise ModelInputError("slit lanes times slit_tape_width_mm cannot exceed master_width_mm")
    _positive(factory["annual_overhead_cost"], "annual_overhead_cost", allow_zero=True)
    _positive(
        factory["downstream_variable_cost_per_tape_m"],
        "downstream_variable_cost_per_tape_m",
        allow_zero=True,
    )
    _positive(factory["order_length_m"], "order_length_m")

    step_names: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ModelInputError(f"steps[{index}] must be an object")
        name = str(step.get("name", "")).strip()
        if not name or name in step_names:
            raise ModelInputError("step names must be non-empty and unique")
        step_names.add(name)
        _positive(step["nominal_web_speed_m_per_hour"], f"{name}.nominal_web_speed")
        _positive(step["parallel_lines"], f"{name}.parallel_lines")
        if int(step["parallel_lines"]) != float(step["parallel_lines"]):
            raise ModelInputError(f"{name}.parallel_lines must be an integer")
        _fraction(step["availability"], f"{name}.availability")
        _fraction(step["performance_rate"], f"{name}.performance_rate")
        _fraction(step["independent_retention"], f"{name}.independent_retention")
        _positive(step["fixed_annual_cost"], f"{name}.fixed_annual_cost", allow_zero=True)
        _positive(
            step["variable_cost_per_master_m"],
            f"{name}.variable_cost_per_master_m",
            allow_zero=True,
        )

    for name in (
        "common_mode_defects_per_master_km",
        "lane_defects_per_lane_km",
        "excluded_length_per_defect_m",
        "minimum_shippable_piece_m",
    ):
        _positive(defects[name], name, allow_zero=True)

    grade_names: set[str] = set()
    total_share = 0.0
    qualified_share = 0.0
    for index, grade in enumerate(grades):
        if not isinstance(grade, dict):
            raise ModelInputError(f"grades[{index}] must be an object")
        name = str(grade.get("name", "")).strip()
        if not name or name in grade_names:
            raise ModelInputError("grade names must be non-empty and unique")
        grade_names.add(name)
        total_share += _fraction(grade["share"], f"{name}.share", allow_zero=True)
        if not isinstance(grade.get("counts_as_qualified_output"), bool):
            raise ModelInputError(f"{name}.counts_as_qualified_output must be boolean")
        if grade["counts_as_qualified_output"]:
            qualified_share += float(grade["share"])
        _positive(grade["ic_a_at_reference"], f"{name}.ic_a_at_reference")
        if "selling_price_per_m" in grade:
            _positive(
                grade["selling_price_per_m"],
                f"{name}.selling_price_per_m",
                allow_zero=True,
            )
    if not math.isclose(total_share, 1.0, rel_tol=0, abs_tol=1e-9):
        raise ModelInputError(f"grade shares must sum to 1, got {total_share}")
    if qualified_share <= 0:
        raise ModelInputError("at least one grade must count as qualified output")


def poisson_piece_retention(
    combined_defects_per_km: float,
    excluded_length_per_defect_m: float,
    minimum_piece_m: float,
) -> float:
    """Expected retained fraction for Poisson gaps and a minimum piece length."""
    rate_per_m = _positive(
        combined_defects_per_km,
        "combined_defects_per_km",
        allow_zero=True,
    ) / 1000.0
    excluded = _positive(
        excluded_length_per_defect_m,
        "excluded_length_per_defect_m",
        allow_zero=True,
    )
    minimum = _positive(minimum_piece_m, "minimum_piece_m", allow_zero=True)
    if rate_per_m == 0:
        return 1.0
    return math.exp(-rate_per_m * (excluded + minimum)) * (
        1.0 + rate_per_m * minimum
    )


def run_factory(config: dict[str, Any]) -> dict[str, Any]:
    """Run the deterministic analytic model and return auditable outputs."""
    _validate_config(config)
    factory = config["factory"]
    steps = config["steps"]
    defects = config["defects"]
    grades = config["grades"]

    hours = float(factory["scheduled_hours_per_year"])
    step_results: list[dict[str, float | str]] = []
    for step in steps:
        effective_speed = (
            float(step["nominal_web_speed_m_per_hour"])
            * int(step["parallel_lines"])
            * float(step["availability"])
            * float(step["performance_rate"])
        )
        step_results.append(
            {
                "name": step["name"],
                "effective_speed_m_per_hour": effective_speed,
                "annual_capacity_master_m": effective_speed * hours,
            }
        )

    bottleneck = min(step_results, key=lambda result: result["annual_capacity_master_m"])
    gross_master_m = float(bottleneck["annual_capacity_master_m"])
    process_retention = math.prod(float(step["independent_retention"]) for step in steps)
    lanes = int(factory["slit_lanes"])
    slitting_yield = float(factory["slitting_length_yield"])
    gross_slit_tape_m = gross_master_m * lanes * slitting_yield
    post_process_tape_m = gross_slit_tape_m * process_retention

    common_rate = float(defects["common_mode_defects_per_master_km"])
    lane_rate = float(defects["lane_defects_per_lane_km"])
    combined_lane_rate = common_rate + lane_rate
    piece_retention = poisson_piece_retention(
        combined_lane_rate,
        float(defects["excluded_length_per_defect_m"]),
        float(defects["minimum_shippable_piece_m"]),
    )
    saleable_tape_m = post_process_tape_m * piece_retention
    qualified_share = sum(
        float(grade["share"]) for grade in grades if grade["counts_as_qualified_output"]
    )
    qualified_tape_m = saleable_tape_m * qualified_share

    order_length_km = float(factory["order_length_m"]) / 1000.0
    single_lane_clean_probability = math.exp(-combined_lane_rate * order_length_km)
    all_lanes_clean_probability = math.exp(
        -(common_rate + lane_rate * lanes) * order_length_km
    )

    step_fixed_cost = sum(float(step["fixed_annual_cost"]) for step in steps)
    step_variable_cost = gross_master_m * sum(
        float(step["variable_cost_per_master_m"]) for step in steps
    )
    downstream_variable_cost = gross_slit_tape_m * float(
        factory["downstream_variable_cost_per_tape_m"]
    )
    annual_cost = (
        float(factory["annual_overhead_cost"])
        + step_fixed_cost
        + step_variable_cost
        + downstream_variable_cost
    )
    if not math.isfinite(annual_cost) or saleable_tape_m <= 0 or qualified_tape_m <= 0:
        raise ModelInputError("scenario produces zero output or non-finite cost; unit economics are undefined")
    cost_per_saleable_m = annual_cost / saleable_tape_m
    cost_per_qualified_m = annual_cost / qualified_tape_m

    grade_results: list[dict[str, float | str]] = []
    total_kam = 0.0
    total_revenue = 0.0
    has_all_prices = True
    for grade in grades:
        length_m = saleable_tape_m * float(grade["share"])
        ic_ka = float(grade["ic_a_at_reference"]) / 1000.0
        grade_kam = length_m * ic_ka
        is_qualified = bool(grade["counts_as_qualified_output"])
        if is_qualified:
            total_kam += grade_kam
        result: dict[str, float | str] = {
            "name": grade["name"],
            "output_length_m": length_m,
            "ic_a_at_reference": float(grade["ic_a_at_reference"]),
            "counts_as_qualified_output": is_qualified,
            "allocated_manufacturing_cost_per_kam": cost_per_saleable_m / ic_ka,
        }
        if "selling_price_per_m" in grade:
            revenue = length_m * float(grade["selling_price_per_m"])
            result["revenue"] = revenue
            total_revenue += revenue
        else:
            has_all_prices = False
        grade_results.append(result)

    result: dict[str, Any] = {
        "scenario_name": config.get("scenario_name", "unnamed"),
        "reference_condition": config["reference_condition"],
        "model_boundary": "Steady-state common-throughput proxy: retention applied after the minimum step capacity; all steps incur variable cost on gross master metres; downstream variable cost is charged on gross slit tape metres before process and piece retention. No serial scrap capacity recovery, queuing, ramp, inventory, capex or finance. Poisson piece formula is an infinite-length expectation, not a finite-roll forecast.",
        "cost_allocation_basis": "Headline manufacturing_cost_per_kam assigns all cost to qualified kA·m. Per-grade allocated_manufacturing_cost_per_kam spreads cost uniformly over all saleable metres (including downgraded grades), then divides by that grade's Ic in kA. These are different allocation bases, not additive costs.",
        "bottleneck_step": bottleneck["name"],
        "gross_master_m_per_year": gross_master_m,
        "gross_slit_tape_m_per_year": gross_slit_tape_m,
        "gross_12mm_equivalent_m_per_year": (
            gross_slit_tape_m * float(factory["slit_tape_width_mm"]) / 12.0
        ),
        "independent_process_retention": process_retention,
        "piece_retention": piece_retention,
        "saleable_tape_m_per_year": saleable_tape_m,
        "qualified_grade_share": qualified_share,
        "qualified_tape_m_per_year": qualified_tape_m,
        "qualified_12mm_equivalent_m_per_year": (
            qualified_tape_m * float(factory["slit_tape_width_mm"]) / 12.0
        ),
        "single_lane_clean_order_probability": single_lane_clean_probability,
        "all_lanes_clean_order_probability": all_lanes_clean_probability,
        "annual_manufacturing_cost": annual_cost,
        "manufacturing_cost_per_saleable_m": cost_per_saleable_m,
        "manufacturing_cost_per_qualified_m": cost_per_qualified_m,
        "qualified_kam_per_year": total_kam,
        "manufacturing_cost_per_kam": annual_cost / total_kam,
        "step_capacities": step_results,
        "grades": grade_results,
        "evidence_notice": config.get("evidence_notice", ""),
    }
    if has_all_prices:
        result["annual_revenue"] = total_revenue
        result["gross_margin_before_unmodeled_costs"] = (
            total_revenue - annual_cost
        ) / total_revenue if total_revenue else None
    return result

"""Transparent multi-year ramp cash model for a hypothetical REBCO factory."""

from __future__ import annotations

import math
from typing import Any

from model import ModelInputError


def _finite_nonnegative(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ModelInputError(f"{name} must be finite and nonnegative")
    return number


def _fraction(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ModelInputError(f"{name} must be between 0 and 1")
    return number


def run_ramp(config: dict[str, Any]) -> dict[str, Any]:
    """Calculate shipment-limited cash flow without inferring real vendor data."""
    evidence_notice = config.get("evidence_notice")
    currency = config.get("currency")
    years = config.get("years")
    if not isinstance(evidence_notice, str) or not evidence_notice.strip():
        raise ModelInputError("evidence_notice must be a non-empty string")
    if not isinstance(currency, str) or not currency.strip():
        raise ModelInputError("currency must be a non-empty string")
    if not isinstance(years, list) or not years:
        raise ModelInputError("years must be a non-empty list")

    discount_rate = _finite_nonnegative(config["discount_rate"], "discount_rate")
    working_capital_fraction = _fraction(
        config["working_capital_fraction_of_revenue"],
        "working_capital_fraction_of_revenue",
    )
    price = _finite_nonnegative(config["price_per_shipped_kam"], "price_per_shipped_kam")
    variable_cost = _finite_nonnegative(
        config["variable_cost_per_shipped_kam"],
        "variable_cost_per_shipped_kam",
    )
    fixed_cost = _finite_nonnegative(config["fixed_cost_per_year"], "fixed_cost_per_year")
    residual_value = _finite_nonnegative(config.get("residual_value_end", 0), "residual_value_end")

    seen_years: set[int] = set()
    previous_working_capital = 0.0
    cumulative_discounted_cash = 0.0
    payback_year: int | None = None
    output: list[dict[str, float | int]] = []

    for expected_year, row in enumerate(years, start=1):
        raw_year = row["year"]
        if isinstance(raw_year, bool) or not isinstance(raw_year, int):
            raise ModelInputError("years must be unique consecutive integers starting at 1")
        year = raw_year
        if year != expected_year or year in seen_years:
            raise ModelInputError("years must be unique consecutive integers starting at 1")
        seen_years.add(year)
        nameplate = _finite_nonnegative(row["nameplate_gross_kam_per_year"], f"year {year} nameplate")
        utilization = _fraction(row["utilization"], f"year {year} utilization")
        qualified_fraction = _fraction(row["qualified_fraction"], f"year {year} qualified_fraction")
        demand = _finite_nonnegative(row["demand_kam"], f"year {year} demand")
        capex = _finite_nonnegative(row["capex"], f"year {year} capex")

        gross = nameplate * utilization
        qualified = gross * qualified_fraction
        shipped = min(qualified, demand)
        revenue = shipped * price
        manufacturing_cost = fixed_cost + shipped * variable_cost
        working_capital = revenue * working_capital_fraction
        change_working_capital = working_capital - previous_working_capital
        previous_working_capital = working_capital
        terminal_value = residual_value if year == len(years) else 0.0
        free_cash_flow = revenue - manufacturing_cost - capex - change_working_capital + terminal_value
        discount_factor = (1 + discount_rate) ** year
        discounted_cash_flow = free_cash_flow / discount_factor
        cumulative_discounted_cash += discounted_cash_flow
        if payback_year is None and cumulative_discounted_cash >= 0:
            payback_year = year
        output.append({
            "year": year,
            "nameplate_gross_kam_per_year": nameplate,
            "gross_kam": gross,
            "qualified_kam": qualified,
            "demand_kam": demand,
            "shipped_kam": shipped,
            "unshipped_qualified_kam": qualified - shipped,
            "revenue": revenue,
            "manufacturing_cost": manufacturing_cost,
            "manufacturing_cost_per_shipped_kam": manufacturing_cost / shipped if shipped else math.inf,
            "working_capital": working_capital,
            "change_working_capital": change_working_capital,
            "capex": capex,
            "terminal_value": terminal_value,
            "free_cash_flow": free_cash_flow,
            "discounted_cash_flow": discounted_cash_flow,
            "cumulative_discounted_cash": cumulative_discounted_cash,
        })

    return {
        "scenario_name": config.get("scenario_name", "unnamed"),
        "currency": currency,
        "model_boundary": "Shipment-cost proxy: no cost for rejected or unsold output, no inventory carryover, no financing or taxes; all cash flows at year end. Working capital is not released at horizon end unless included explicitly in residual value.",
        "evidence_notice": evidence_notice,
        "years": output,
        "npv": cumulative_discounted_cash,
        "discounted_payback_year": payback_year,
        "total_capex": sum(float(row["capex"]) for row in output),
        "total_shipped_kam": sum(float(row["shipped_kam"]) for row in output),
    }

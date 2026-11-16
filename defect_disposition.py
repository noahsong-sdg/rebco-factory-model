"""Bayesian rework/hold/scrap decisions for a detected REBCO defect.

Inputs are scenario assumptions, not producer data.  The model distinguishes a
recoverable defect from an irreversible defect after a binary diagnostic signal.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DispositionInputs:
    recoverable_prevalence: float
    response_sensitivity: float
    response_specificity: float
    repair_success_if_recoverable: float
    rework_cost: float
    scrap_cost: float
    confirmation_cost: float

    def validate(self) -> None:
        probabilities = {
            "recoverable_prevalence": self.recoverable_prevalence,
            "response_sensitivity": self.response_sensitivity,
            "response_specificity": self.response_specificity,
            "repair_success_if_recoverable": self.repair_success_if_recoverable,
        }
        for name, value in probabilities.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in ("rework_cost", "scrap_cost", "confirmation_cost"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f"{name} must be finite and nonnegative")


def posterior_recoverable(inputs: DispositionInputs, response_detected: bool) -> float:
    """Return P(recoverable | observed binary response)."""
    inputs.validate()
    prior = inputs.recoverable_prevalence
    if response_detected:
        like_recoverable = inputs.response_sensitivity
        like_irreversible = 1 - inputs.response_specificity
    else:
        like_recoverable = 1 - inputs.response_sensitivity
        like_irreversible = inputs.response_specificity
    evidence = prior * like_recoverable + (1 - prior) * like_irreversible
    if evidence == 0:
        raise ValueError("observation has zero probability under the scenario")
    return prior * like_recoverable / evidence


def expected_costs(inputs: DispositionInputs, response_detected: bool) -> dict[str, float]:
    """Expected normalized cost for rework, scrap, or perfect confirmation.

    Confirmation is an explicit upper-bound information model: it is assumed to
    reveal defect class perfectly before choosing rework or scrap.
    """
    posterior = posterior_recoverable(inputs, response_detected)
    recoverable_rework = inputs.rework_cost + (1 - inputs.repair_success_if_recoverable) * inputs.scrap_cost
    rework = inputs.rework_cost + (
        posterior * (1 - inputs.repair_success_if_recoverable) + (1 - posterior)
    ) * inputs.scrap_cost
    confirm = inputs.confirmation_cost + posterior * min(recoverable_rework, inputs.scrap_cost) + (1 - posterior) * inputs.scrap_cost
    return {"rework": rework, "hold_for_confirmation": confirm, "scrap": inputs.scrap_cost}


def decide(inputs: DispositionInputs, response_detected: bool) -> dict[str, object]:
    costs = expected_costs(inputs, response_detected)
    action = min(costs, key=costs.get)
    return {
        "response_detected": response_detected,
        "posterior_recoverable": posterior_recoverable(inputs, response_detected),
        "expected_costs": costs,
        "recommended_action": action,
    }

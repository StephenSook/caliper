"""Two proportion sample size, and the refusal that depends on it.

ONE method, stated on the surface wherever a number appears. Cohen's h with the
normal approximation, which is what statsmodels' NormalIndPower solves. A
different convention (the Fleiss arcsine-free formula, or an exact test) gives a
materially different answer at these proportions, so mixing them silently is how
a slide ends up disagreeing with the code that produced it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import statsmodels.api as sm
from statsmodels.stats.power import NormalIndPower

METHOD = "Cohen's h, two sided, normal approximation (statsmodels NormalIndPower)"


@dataclass(frozen=True)
class PowerResult:
    baseline_rate: float
    target_rate: float
    effect_size_h: float
    alpha: float
    power: float
    n_per_arm: int
    method: str = METHOD


def n_per_arm(p_baseline: float, p_target: float, power: float = 0.80, alpha: float = 0.05) -> PowerResult:
    for name, value in (("baseline", p_baseline), ("target", p_target)):
        if not 0 < value < 1:
            raise ValueError(f"{name} rate must be strictly between 0 and 1, got {value}")
    if p_baseline == p_target:
        raise ValueError("baseline and target rates are identical; no effect to detect")
    h = abs(sm.stats.proportion_effectsize(p_baseline, p_target))
    n = NormalIndPower().solve_power(
        effect_size=h, power=power, alpha=alpha, ratio=1.0, alternative="two-sided"
    )
    return PowerResult(
        baseline_rate=p_baseline,
        target_rate=p_target,
        effect_size_h=float(h),
        alpha=alpha,
        power=power,
        n_per_arm=int(math.ceil(n)),
    )


def improvement_claim_licensed(observed_n_per_arm: int, required: PowerResult) -> dict:
    """The system refuses to declare improvement below its own power threshold.

    It prints the threshold rather than hiding it, because a refusal without the
    number attached reads as an inability instead of a standard.
    """
    licensed = observed_n_per_arm >= required.n_per_arm
    return {
        "licensed": licensed,
        "observed_n_per_arm": observed_n_per_arm,
        "required_n_per_arm": required.n_per_arm,
        "method": required.method,
        "verdict": "SUFFICIENT_POWER" if licensed else "INSUFFICIENT_POWER",
        "statement": (
            f"{observed_n_per_arm} calls per arm meets the {required.n_per_arm} required to detect "
            f"{required.baseline_rate:.3f} to {required.target_rate:.2f} at {int(required.power * 100)} "
            f"percent power."
            if licensed
            else f"We will not claim improvement. Detecting {required.baseline_rate:.3f} to "
            f"{required.target_rate:.2f} at {int(required.power * 100)} percent power needs "
            f"{required.n_per_arm} calls per arm and we have {observed_n_per_arm}."
        ),
    }


def rtm_risk(cohort_selection_rule: str) -> dict:
    """Regression to the mean guard.

    If the cohort was selected because it scored badly, scores improve regardless
    of the intervention. This is the single most important methodological point in
    the outcome loop, so the system states it rather than waiting to be asked.
    """
    selected_on_outcome = cohort_selection_rule in {"LOWEST_SCORERS", "BELOW_THRESHOLD"}
    return {
        "risk": "HIGH" if selected_on_outcome else "LOW",
        "explanation": (
            "The cohort was selected on the same measure used to evaluate improvement. "
            "Extreme scores regress toward the mean regardless of the intervention."
            if selected_on_outcome
            else "Cohort selection is independent of the outcome measure."
        ),
        "required_design": (
            "Comparison group, or regression discontinuity at the selection threshold."
            if selected_on_outcome
            else "Pre and post is acceptable."
        ),
        "citation": "Kahneman, Thinking Fast and Slow (2011); Tversky and Kahneman (1982) pp. 67-68",
    }

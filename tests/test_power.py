"""Sample size, the refusal it licenses, and the regression to the mean guard.

Golden test E12 lives here: a pre/post with n below threshold must return
INSUFFICIENT_POWER rather than a claim.
"""

from __future__ import annotations

import pytest

from caliper.instrument.power import improvement_claim_licensed, n_per_arm, rtm_risk


def test_n_per_arm_is_reproducible_and_matches_cohens_h():
    """Hand check with the factor of two that a one-sample formula omits.

    phi = 2*asin(sqrt(p)) has variance about 1/n, so for two independent arms
    Var(phi1 - phi2) = 2/n and the sample size per arm is

        n = 2 * ((z_alpha/2 + z_beta) / h)^2

    Dropping that 2 halves every answer. Calibrated below against Cohen (1988),
    whose published table gives n = 63 per group at h = 0.5, alpha .05 two
    tailed, power .80.
    """
    import math

    zsum = 1.959963985 + 0.8416212336

    # Calibration against the published table, so this test does not merely
    # agree with the implementation it is testing.
    assert math.ceil(2 * (zsum / 0.5) ** 2) == 63

    result = n_per_arm(0.176, 0.60)
    h = abs(2 * math.asin(math.sqrt(0.60)) - 2 * math.asin(math.sqrt(0.176)))
    assert result.effect_size_h == pytest.approx(h, abs=1e-6)
    assert result.n_per_arm == math.ceil(2 * (zsum / h) ** 2)


def test_published_reference_values_for_the_ui():
    """The three figures the interface caches. Asserted so a slide and the code
    cannot drift apart."""
    assert n_per_arm(0.176, 0.60).n_per_arm == 20
    assert n_per_arm(0.176, 0.70).n_per_arm == 13
    assert n_per_arm(0.176, 0.33).n_per_arm == 123


def test_larger_effect_needs_fewer_calls():
    assert n_per_arm(0.176, 0.70).n_per_arm < n_per_arm(0.176, 0.60).n_per_arm
    assert n_per_arm(0.176, 0.33).n_per_arm > n_per_arm(0.176, 0.60).n_per_arm


def test_the_method_travels_with_the_number():
    """Three conventions give materially different answers at these proportions,
    so a bare n is not a claim anyone can check."""
    assert "Cohen" in n_per_arm(0.176, 0.60).method


def test_E12_underpowered_claim_is_refused():
    required = n_per_arm(0.176, 0.33)
    verdict = improvement_claim_licensed(observed_n_per_arm=17, required=required)
    assert verdict["licensed"] is False
    assert verdict["verdict"] == "INSUFFICIENT_POWER"
    # The refusal prints the threshold rather than hiding it.
    assert str(required.n_per_arm) in verdict["statement"]


def test_sufficient_power_is_licensed():
    required = n_per_arm(0.176, 0.60)
    verdict = improvement_claim_licensed(required.n_per_arm + 5, required)
    assert verdict["licensed"] is True
    assert verdict["verdict"] == "SUFFICIENT_POWER"


def test_power_rejects_impossible_rates():
    with pytest.raises(ValueError):
        n_per_arm(0.0, 0.5)
    with pytest.raises(ValueError):
        n_per_arm(0.5, 1.0)
    with pytest.raises(ValueError):
        n_per_arm(0.3, 0.3)


def test_rtm_flags_cohorts_selected_on_the_outcome():
    """Selecting the lowest scorers guarantees apparent improvement even if the
    intervention does nothing."""
    high = rtm_risk("LOWEST_SCORERS")
    assert high["risk"] == "HIGH"
    assert "regression" in high["required_design"].lower() or "comparison" in high["required_design"].lower()

    low = rtm_risk("RANDOM_SAMPLE")
    assert low["risk"] == "LOW"
    assert "Pre and post is acceptable" in low["required_design"]

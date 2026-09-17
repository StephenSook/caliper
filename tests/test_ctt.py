"""Tests for the classical test theory core.

Two rules govern this file:

1. Every asserted number is either hand computed from a fixture written out in
   the test, or cross checked against an independent published implementation
   (pingouin, which is what the literature uses). No figure is asserted because a
   document said so. A wrong number in an assertion is a bug the suite DEFENDS.

2. The ddof consistency test exists because a mixed estimator (population item
   variance over sample total variance) silently inflates KR-20. On the supplied
   member experience form that mistake produces 0.5048 instead of 0.4661, which
   is a materially different claim about whether an instrument works.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pingouin as pg
import pytest

from caliper.instrument.ctt import (
    feldt_ci,
    item_analysis,
    kr20,
    phi_coefficient,
    reliability_report,
)

# A small fixture with known structure: 6 evaluations, 4 items.
# Item 0 is always passed (zero variance), item 3 is always failed (zero variance).
FIXTURE = np.array(
    [
        [1, 1, 1, 0],
        [1, 1, 0, 0],
        [1, 0, 1, 0],
        [1, 0, 0, 0],
        [1, 1, 1, 0],
        [1, 0, 0, 0],
    ],
    dtype=float,
)


def test_kr20_matches_pingouin_on_fixture():
    """Our KR-20 must equal Cronbach's alpha from an independent implementation."""
    ours = kr20(FIXTURE)
    theirs, _ = pg.cronbach_alpha(data=pd.DataFrame(FIXTURE))
    assert ours == pytest.approx(theirs, abs=1e-10)


def test_kr20_hand_computed():
    """Fully worked by hand so the test does not depend on any library.

    k = 4, n = 6.
    Item variances (ddof=1): [0.0, 0.3, 0.3, 0.0] -> sum 0.6
    Totals: [3, 2, 2, 1, 3, 1] -> mean 2.0, sample variance 0.8
    alpha = 4/3 * (1 - 0.6/0.8) = 4/3 * 0.25 = 0.333333...
    """
    totals = FIXTURE.sum(axis=1)
    assert FIXTURE.var(axis=0, ddof=1).sum() == pytest.approx(0.6)
    assert totals.var(ddof=1) == pytest.approx(0.8)
    assert kr20(FIXTURE) == pytest.approx(1 / 3, abs=1e-12)


def test_kr20_variance_convention_is_consistent():
    """Guards the exact defect that produced a wrong headline figure.

    Mixing a population item variance with a sample total variance inflates the
    coefficient by a factor of n/(n-1) inside the ratio. Consistent ddof either
    way must give the SAME answer; the mixed form must not equal ours.
    """
    matrix = FIXTURE
    n, k = matrix.shape

    population = (k / (k - 1)) * (1 - matrix.var(axis=0, ddof=0).sum() / matrix.sum(axis=1).var(ddof=0))
    sample = (k / (k - 1)) * (1 - matrix.var(axis=0, ddof=1).sum() / matrix.sum(axis=1).var(ddof=1))
    mixed = (k / (k - 1)) * (1 - matrix.var(axis=0, ddof=0).sum() / matrix.sum(axis=1).var(ddof=1))

    assert population == pytest.approx(sample, abs=1e-12), "consistent conventions must agree"
    assert kr20(matrix) == pytest.approx(sample, abs=1e-12)
    assert mixed != pytest.approx(sample, abs=1e-6), "the mixed estimator is a different number"


def test_feldt_ci_matches_pingouin():
    alpha = kr20(FIXTURE)
    low, high = feldt_ci(alpha, n=FIXTURE.shape[0], k=FIXTURE.shape[1])
    _, bounds = pg.cronbach_alpha(data=pd.DataFrame(FIXTURE), ci=0.95)
    assert low == pytest.approx(float(bounds[0]), abs=1e-3)
    assert high == pytest.approx(float(bounds[1]), abs=1e-3)


def test_feldt_ci_brackets_the_point_estimate():
    alpha = kr20(FIXTURE)
    low, high = feldt_ci(alpha, n=6, k=4)
    assert low < alpha < high


def test_feldt_degrees_of_freedom():
    report = reliability_report(FIXTURE)
    assert report.df1 == 5  # n - 1
    assert report.df2 == 15  # (n - 1)(k - 1)


def test_item_analysis_flags_zero_variance_and_band():
    stats = item_analysis(FIXTURE, ["I0", "I1", "I2", "I3"])
    by_id = {s.item_id: s for s in stats}

    # Always passed and always failed items carry no information at all.
    assert by_id["I0"].difficulty_p == 1.0
    assert by_id["I0"].discrimination_rpb is None
    assert "ZERO_VARIANCE" in by_id["I0"].flags
    assert by_id["I0"].verdict == "DEAD"

    assert by_id["I3"].difficulty_p == 0.0
    assert by_id["I3"].verdict == "DEAD"

    # Discrimination is the CORRECTED form, against the rest score.
    assert by_id["I1"].discrimination_rpb is not None


def test_item_analysis_corrected_not_uncorrected():
    """An uncorrected item-total correlation includes the item in its own total,
    which inflates it. Assert we use the rest score."""
    stats = item_analysis(FIXTURE, ["I0", "I1", "I2", "I3"])
    col = FIXTURE[:, 1]
    rest = FIXTURE.sum(axis=1) - col
    expected = float(np.corrcoef(col, rest)[0, 1])
    uncorrected = float(np.corrcoef(col, FIXTURE.sum(axis=1))[0, 1])
    got = next(s for s in stats if s.item_id == "I1").discrimination_rpb
    assert got == pytest.approx(expected, abs=1e-12)
    assert got != pytest.approx(uncorrected, abs=1e-6)


def test_kr20_rejects_degenerate_input():
    with pytest.raises(ValueError):
        kr20(np.array([[1.0, 0.0]]))  # one evaluation
    with pytest.raises(ValueError):
        kr20(np.array([[1.0], [0.0]]))  # one item
    with pytest.raises(ValueError):
        kr20(np.ones((4, 3)))  # zero total variance


def test_phi_reports_cells_and_handles_saturation():
    """Base rate saturation: two items that both fail on nearly everything produce
    a high co-failure count with no association. The count alone is not
    corroboration, which is why phi is reported next to it."""
    fail_a = np.array([1, 1, 1, 1, 0])
    fail_b = np.array([1, 1, 1, 1, 0])
    cells, phi = phi_coefficient(fail_a, fail_b)
    assert cells["n11"] == 4
    assert phi == pytest.approx(1.0)

    # No variance in one indicator makes phi undefined, not zero.
    cells, phi = phi_coefficient(np.array([1, 1, 1]), np.array([1, 0, 1]))
    assert phi is None


def test_phi_can_be_negative():
    """A negative phi means the two items anti-associate. Reporting such a pair as
    corroboration would be wrong, so the sign must survive."""
    _, phi = phi_coefficient(np.array([1, 1, 0, 0]), np.array([0, 0, 1, 1]))
    assert phi is not None and phi < 0

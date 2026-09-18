"""The labor and cost model, checked against the document it came from.

The case study names this as a deliverable: savings on labor and cost, USA
against Mexico or the Philippines. Every constant in `caliper/impact/labor.py`
is transcribed from `Labor_Cost_Curriculum_Build_Report.docx`, and a
transcription is a claim like any other.

So the tests below do not assert that the arithmetic is self consistent, which
would prove nothing. They assert that OUR arithmetic reproduces figures the
REPORT ITSELF PRINTS. If the two ever disagree, one of them is wrong and this
fails rather than quietly shipping a number to a slide.

The document is confidential and is not in this repository, so the expected
values are transcribed here with the section they came from. That is the same
split used for the de-identified export: the artifact stays out, the assertion
stays in, and the assertion names its source.
"""

from __future__ import annotations

import pytest

from caliper.impact import labor

# --------------------------------------------------------------------------
# Section 1. Every rate, as printed.


@pytest.mark.parametrize(
    ("key", "gross", "loaded", "monthly", "annual"),
    [
        ("philippines", 4.81, 6.49, 827, 10_015),
        ("mexico", 11.49, 14.25, 1_976, 23_899),
        ("usa", 38.94, 49.85, 6_750, 81_000),
    ],
)
def test_rates_match_the_report(key, gross, loaded, monthly, annual) -> None:
    geo = labor.GEOGRAPHIES[key]
    assert geo.gross_hourly == gross
    assert geo.fully_loaded_hourly == loaded
    assert geo.gross_monthly_172h == monthly
    assert geo.gross_annual_2080h == annual


@pytest.mark.parametrize("key", ["philippines", "mexico", "usa"])
def test_the_gross_hourly_rate_follows_from_the_annual_at_2080_hours(key) -> None:
    """The report states the derivation, so it is checkable."""
    geo = labor.GEOGRAPHIES[key]
    assert geo.gross_annual_2080h / 2080 == pytest.approx(geo.gross_hourly, abs=0.01)


@pytest.mark.parametrize("key", ["philippines", "mexico", "usa"])
def test_the_loaded_rate_follows_from_the_gross_and_the_add_on(key) -> None:
    """Within a cent, and the cent is the finding.

    The report does not round these consistently: the Philippines figure follows
    from the rounded gross hourly rate and the USA figure follows from the
    unrounded annual, which puts the two methods a cent apart. Immaterial to any
    decision, and the clearest available evidence that these are directional,
    which is exactly what the report says they are.
    """
    geo = labor.GEOGRAPHIES[key]
    from_rounded = geo.gross_hourly * (1 + geo.loading_pct)
    from_annual = (geo.gross_annual_2080h / 2080) * (1 + geo.loading_pct)
    assert min(from_rounded, from_annual) - 0.02 <= geo.fully_loaded_hourly
    assert geo.fully_loaded_hourly <= max(from_rounded, from_annual) + 0.02


@pytest.mark.parametrize("key", ["philippines", "mexico", "usa"])
def test_the_stated_add_on_sits_inside_its_own_stated_range(key) -> None:
    geo = labor.GEOGRAPHIES[key]
    low, high = geo.loading_range
    assert low <= geo.loading_pct <= high


# --------------------------------------------------------------------------
# Section 2. Cost to build one hour of finished curriculum.


@pytest.mark.parametrize(
    ("key", "printed"),
    [("philippines", 17.91), ("mexico", 39.33), ("usa", 137.59)],
)
def test_cost_per_curriculum_hour_reproduces_the_reports_own_table(key, printed) -> None:
    """The load bearing check in this file.

    These three figures are printed in the report. Ours are computed from the
    rate and the ratio. They have to agree, or a number on a slide disagrees
    with the sponsor's own page.
    """
    got = labor.cost_per_curriculum_hour(key, "weighted_actual")
    assert got == pytest.approx(printed, abs=0.01)


def test_the_usa_multiples_match_the_reports_prose() -> None:
    """The report says USA runs roughly 7.7 times the Philippines and 3.5 times
    Mexico, fully loaded. Those sentences are claims too."""
    c = labor.compare(1.0)
    assert c["usa_multiple_of"]["philippines"] == pytest.approx(7.7, abs=0.05)
    assert c["usa_multiple_of"]["mexico"] == pytest.approx(3.5, abs=0.05)


# --------------------------------------------------------------------------
# Section 3. The baselines, and the reason they are the whole story.


def test_every_baseline_carries_a_provenance_from_the_vocabulary() -> None:
    """A figure and how it was obtained travel together, or the figure is
    unusable. This is the same rule the reliability screen applies."""
    allowed = {labor.MEASURED, labor.TEAM_ESTIMATE, labor.INDUSTRY, labor.NOT_VERIFIED}
    for base in labor.BASELINES.values():
        assert base.provenance in allowed, base.key
        assert base.scope, f"{base.key} has no stated scope"


def test_the_starred_industry_revision_figure_is_marked_unverified() -> None:
    """The report stars it and says to treat starred values as directional
    placeholders rather than verified benchmarks. Losing that in transcription
    would promote a placeholder to a fact."""
    base = labor.BASELINES["revision_industry"]
    assert base.provenance == labor.NOT_VERIFIED
    assert "placeholder" in base.caveat.lower()


def test_the_two_build_ratios_are_reported_as_a_spread_not_reconciled() -> None:
    """2.76 and 17.47 differ by more than six times because they answer
    different questions. Picking one silently is the failure; stating the spread
    and the scope of each is the fix."""
    spread = labor.compare(1.0)["baseline_choice_matters"]
    assert spread["low"]["hours"] == 2.76
    assert spread["high"]["hours"] == 17.47
    assert spread["ratio"] == pytest.approx(6.3, abs=0.1)
    assert spread["low"]["scope"] != spread["high"]["scope"]


def test_rework_is_priced_from_the_measured_revision_figure() -> None:
    """The cost of being wrong is the strongest number here precisely because it
    comes from the team's own tracked revisions rather than from a benchmark."""
    assert labor.REWORK_BASELINE == "revision_team"
    assert labor.BASELINES[labor.REWORK_BASELINE].hours_per_curriculum_hour == 3.60
    # 3.60 hours per curriculum hour, two hours of curriculum, USA loaded rate.
    assert labor.rework_cycle_cost("usa", 2.0) == pytest.approx(3.60 * 2 * 49.85, abs=0.01)


# --------------------------------------------------------------------------
# The refusal. This is the part that makes the rest of it trustworthy.


def test_no_savings_figure_without_a_rate_of_misdiagnosis() -> None:
    """An avoided rework cycle has a defensible price. How often that rework
    happens is not in the supplied package and has not been measured here, and
    multiplying a real cost by a guessed frequency is the exact move this product
    exists to catch."""
    claim = labor.savings_claim(
        curriculum_hours=2.0, interventions_per_year=50, misdiagnosis_rate=None, rate_source=None
    )
    assert claim.licensed is False
    assert "not been measured" in claim.reason or "not in the supplied package" in claim.reason
    # It still hands over the thing it CAN stand behind.
    assert claim.detail["per_rework_cycle"]["usa"] == pytest.approx(358.92, abs=0.01)


def test_no_savings_figure_from_an_unsourced_rate() -> None:
    claim = labor.savings_claim(
        curriculum_hours=2.0, interventions_per_year=50, misdiagnosis_rate=0.2, rate_source=None
    )
    assert claim.licensed is False
    assert "source" in claim.reason.lower()


@pytest.mark.parametrize("bad", [-0.1, 1.4, 12])
def test_a_rate_that_is_not_a_proportion_is_refused(bad) -> None:
    claim = labor.savings_claim(
        curriculum_hours=2.0,
        interventions_per_year=50,
        misdiagnosis_rate=bad,
        rate_source="somewhere",
    )
    assert claim.licensed is False


def test_a_sourced_rate_is_licensed_and_the_source_is_recorded() -> None:
    claim = labor.savings_claim(
        curriculum_hours=2.0,
        interventions_per_year=50,
        misdiagnosis_rate=0.2,
        rate_source="supervisor interview, 2026-09-17",
        geography="usa",
    )
    assert claim.licensed is True
    assert claim.detail["rate_source"] == "supervisor interview, 2026-09-17"
    assert claim.detail["rework_cycles_avoided_per_year"] == pytest.approx(10.0)
    assert claim.detail["annual_labor_avoided"] == pytest.approx(358.92 * 10, abs=0.5)
    # The claim says what it assumed, rather than presenting itself as a floor.
    assert "assumes" in claim.detail["assumption"].lower()

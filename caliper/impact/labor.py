"""What a wrong diagnosis costs, in the sponsor's own numbers.

The case study asks for savings on labor and cost, evaluating USA against Mexico
or the Philippines. This module answers that, and it answers it the way the rest
of CALIPER answers everything: by refusing to state a figure the evidence cannot
carry.

Every constant here is transcribed from
`Labor_Cost_Curriculum_Build_Report.docx`, section by section, and every derived
figure is asserted in `tests/test_labor.py` to reproduce a value the report
itself prints. If our arithmetic and their table disagree, the tests fail.

THE THING THAT MATTERS MOST HERE IS THE BASELINE, and it is the easiest thing in
the whole case package to get wrong. The report gives two build ratios that
differ by more than six times:

    2.76 build hours per curriculum hour
        Weighted across 26 client projects with usable curriculum duration in
        the 2026 export, small projects excluded. It mixes every request type,
        so it is dominated by revisions.

    17.47 build hours per curriculum hour
        New training only, team average, including a stated 20 percent buffer
        because the team consistently runs over baseline estimates.

These are not contradictory and calling them inconsistent would be wrong. They
answer different questions. Which one applies depends entirely on whether the
intervention is a brand new build or a revision, and a savings figure that does
not say which one it used is not a savings figure. That is the same failure this
product exists to catch, one level up: a number quoted without the thing that
determines it.

WHAT THIS DELIBERATELY WILL NOT DO is multiply a cost by an invented rate of
misdiagnosis to produce one impressive headline. Nobody has measured how often a
needs analysis lands on the wrong root cause, this repository certainly has not,
and a number built on a guessed frequency is exactly the kind of figure the
audit screen exists to refuse. `savings_claim` requires the caller to supply the
frequency and records that they supplied it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Section 1 of the report. Labor rate per hour, USD.
#
# The report is explicit about what these are: "general external market
# benchmarks (Jobstreet, Indeed, ERI SalaryExpert, Payscale, ZipRecruiter) for
# the Instructional Designer role, not ResultsCX-specific pay scales. Treat as
# directional, not an internal cost basis." That sentence travels with every
# figure this module produces.


@dataclass(frozen=True)
class Geography:
    key: str
    name: str
    gross_hourly: float
    loading_pct: float
    loading_range: tuple[float, float]
    # As PRINTED in the report, not as recomputed. The report's own derivations
    # round inconsistently: the Philippines figure follows from the rounded
    # gross hourly rate and the USA figure follows from the unrounded annual,
    # which puts them a cent apart from each other's method. That is immaterial
    # to any decision and it is the clearest possible evidence that these are
    # directional, which is what the report says they are. Transcribing what is
    # printed keeps our output checkable against their page.
    fully_loaded_hourly: float
    gross_monthly_172h: int
    gross_annual_2080h: int
    statutory_note: str


GEOGRAPHIES: dict[str, Geography] = {
    "philippines": Geography(
        key="philippines",
        name="Philippines",
        gross_hourly=4.81,
        loading_pct=0.35,
        loading_range=(0.30, 0.40),
        fully_loaded_hourly=6.49,
        gross_monthly_172h=827,
        gross_annual_2080h=10_015,
        statutory_note="13th month pay, SSS, PhilHealth, Pag-IBIG, HMO",
    ),
    "mexico": Geography(
        key="mexico",
        name="Mexico",
        gross_hourly=11.49,
        loading_pct=0.24,
        loading_range=(0.20, 0.28),
        fully_loaded_hourly=14.25,
        gross_monthly_172h=1_976,
        gross_annual_2080h=23_899,
        statutory_note="IMSS, INFONAVIT, payroll tax, aguinaldo, vacation premium, PTU",
    ),
    "usa": Geography(
        key="usa",
        name="USA",
        gross_hourly=38.94,
        loading_pct=0.28,
        loading_range=(0.25, 0.30),
        fully_loaded_hourly=49.85,
        gross_monthly_172h=6_750,
        gross_annual_2080h=81_000,
        statutory_note="blended market survey loading",
    ),
}

# FX snapshot the rates were converted at, carried so a reader can date them.
FX_SNAPSHOT = {"as_of": "2026-08-28", "usd_php": 61.7, "usd_mxn": 16.97}

RATE_CAVEAT = (
    "General external market benchmarks for the Instructional Designer role, not "
    "ResultsCX pay scales. The report calls these directional rather than an "
    "internal cost basis, and the FX snapshot is dated 2026-08-28 and will drift."
)


# --------------------------------------------------------------------------
# Sections 2 and 3. Build hours per finished curriculum hour.


@dataclass(frozen=True)
class Baseline:
    key: str
    label: str
    hours_per_curriculum_hour: float
    scope: str
    provenance: str
    caveat: str = ""


# Provenance vocabulary, so a reader can tell at a glance how much weight a
# figure can take. This is the same discipline the instrument audit applies to
# reliability: the number and how it was obtained travel together.
MEASURED = "MEASURED"  # from the team's own tracked data
TEAM_ESTIMATE = "TEAM_ESTIMATE"  # team data plus a stated buffer
INDUSTRY = "INDUSTRY_BENCHMARK"  # published, external
NOT_VERIFIED = "NOT_VERIFIED"  # starred in the report as a placeholder

BASELINES: dict[str, Baseline] = {
    "weighted_actual": Baseline(
        key="weighted_actual",
        label="Weighted actual, all request types",
        hours_per_curriculum_hour=2.76,
        scope="every request type mixed, so dominated by revisions",
        provenance=MEASURED,
        caveat=(
            "Weighted across 26 client projects with a usable curriculum duration in the "
            "2026 export. Projects under about five curriculum hours were excluded to "
            "avoid denominator driven outliers."
        ),
    ),
    "new_training_team": Baseline(
        key="new_training_team",
        label="New training, team average",
        hours_per_curriculum_hour=17.47,
        scope="brand new builds only",
        provenance=TEAM_ESTIMATE,
        caveat="Includes a stated 20 percent buffer, because the team runs over baseline estimates.",
    ),
    "revision_team": Baseline(
        key="revision_team",
        label="Revision, team average",
        hours_per_curriculum_hour=3.60,
        scope="reworking training that already exists",
        provenance=TEAM_ESTIMATE,
        caveat="Includes the same 20 percent buffer as the new training figure.",
    ),
    "new_training_industry": Baseline(
        key="new_training_industry",
        label="New training, industry blended",
        hours_per_curriculum_hour=80.08,
        scope="brand new builds only",
        provenance=INDUSTRY,
        caveat="ATD and Kapp and Defelice, blended across three published complexity tiers.",
    ),
    "revision_industry": Baseline(
        key="revision_industry",
        label="Revision, industry estimated",
        hours_per_curriculum_hour=20.0,
        scope="reworking training that already exists",
        provenance=NOT_VERIFIED,
        caveat=(
            "Starred in the report. Derived from a rule of thumb that revision runs 20 to "
            "30 percent of original build time, because the published benchmark has no "
            "revision specific figure. The report says to treat starred values as "
            "directional placeholders, not verified benchmarks."
        ),
    ),
}

# The revision baseline is the one that prices a mistake, because a diagnosis
# that sends the wrong training into production is discovered later and fixed by
# reworking it. It is a measured team figure rather than a guess, which is why
# the cost of being wrong is the strongest number in this module.
REWORK_BASELINE = "revision_team"


def cost_per_curriculum_hour(geography: str, baseline: str) -> float:
    """Fully loaded labor cost to produce one hour of finished curriculum."""
    geo = GEOGRAPHIES[geography]
    base = BASELINES[baseline]
    return geo.fully_loaded_hourly * base.hours_per_curriculum_hour


def rework_cycle_cost(geography: str, curriculum_hours: float) -> float:
    """What one avoided rework cycle is worth, in labor, in one geography.

    This is the figure CALIPER can actually stand behind. A needs analysis that
    lands on the wrong root cause produces training that addresses the wrong
    behavior, which is discovered downstream and fixed by revising it, and the
    report prices a revision from the team's own tracked data.
    """
    return cost_per_curriculum_hour(geography, REWORK_BASELINE) * curriculum_hours


def compare(curriculum_hours: float, baseline: str = "weighted_actual") -> dict:
    """The build cost of one intervention across all three geographies."""
    base = BASELINES[baseline]
    rows = []
    for geo in GEOGRAPHIES.values():
        per_hour = cost_per_curriculum_hour(geo.key, baseline)
        rows.append(
            {
                "geography": geo.name,
                "key": geo.key,
                "fully_loaded_hourly": geo.fully_loaded_hourly,
                "cost_per_curriculum_hour": round(per_hour, 2),
                "cost_for_this_intervention": round(per_hour * curriculum_hours, 2),
                "rework_cycle_cost": round(rework_cycle_cost(geo.key, curriculum_hours), 2),
                "statutory_note": geo.statutory_note,
            }
        )

    usa = next(r for r in rows if r["key"] == "usa")
    ratios = {
        r["key"]: round(usa["cost_per_curriculum_hour"] / r["cost_per_curriculum_hour"], 2)
        for r in rows
        if r["key"] != "usa"
    }

    return {
        "curriculum_hours": curriculum_hours,
        "baseline": {
            "key": base.key,
            "label": base.label,
            "hours_per_curriculum_hour": base.hours_per_curriculum_hour,
            "scope": base.scope,
            "provenance": base.provenance,
            "caveat": base.caveat,
        },
        "baseline_choice_matters": _baseline_spread(),
        "rows": rows,
        "usa_multiple_of": ratios,
        "rework_baseline": {
            "key": REWORK_BASELINE,
            "hours_per_curriculum_hour": BASELINES[REWORK_BASELINE].hours_per_curriculum_hour,
            "why": (
                "A diagnosis that sends the wrong training into production is discovered "
                "downstream and fixed by revising it, so one avoided rework cycle is what "
                "a correct diagnosis is worth in labor."
            ),
        },
        "rate_caveat": RATE_CAVEAT,
        "fx_snapshot": FX_SNAPSHOT,
    }


def _baseline_spread() -> dict:
    """State the spread rather than hide it behind whichever figure was used."""
    low = BASELINES["weighted_actual"]
    high = BASELINES["new_training_team"]
    return {
        "low": {"key": low.key, "hours": low.hours_per_curriculum_hour, "scope": low.scope},
        "high": {"key": high.key, "hours": high.hours_per_curriculum_hour, "scope": high.scope},
        "ratio": round(high.hours_per_curriculum_hour / low.hours_per_curriculum_hour, 1),
        "statement": (
            "The two build ratios in the report differ by more than six times because they "
            "answer different questions, not because either is wrong. Any savings figure "
            "that does not say which one it used is not a savings figure."
        ),
    }


@dataclass
class SavingsClaim:
    licensed: bool
    reason: str
    detail: dict = field(default_factory=dict)


def savings_claim(
    curriculum_hours: float,
    interventions_per_year: int,
    misdiagnosis_rate: float | None,
    rate_source: str | None,
    geography: str = "usa",
) -> SavingsClaim:
    """An annual savings figure, or a refusal that says what is missing.

    An avoided rework cycle has a defensible price. How OFTEN a needs analysis
    lands on the wrong root cause does not: nobody has measured it here, and the
    supplied case package does not contain it. Multiplying a real cost by a
    guessed frequency produces a large number with nothing underneath it, which
    is the exact move this product was built to catch.

    So the frequency has to be supplied, and where it came from has to be
    supplied with it, and both are recorded in the output.
    """
    if misdiagnosis_rate is None:
        return SavingsClaim(
            licensed=False,
            reason=(
                "No rate of misdiagnosis was supplied. The cost of one avoided rework cycle "
                "is priced from the sponsor's own report; how often that rework happens is "
                "not in the supplied package and has not been measured here. Supply a rate "
                "and its source, or read the per cycle figure and apply your own."
            ),
            detail={
                "per_rework_cycle": {
                    geo.key: round(rework_cycle_cost(geo.key, curriculum_hours), 2)
                    for geo in GEOGRAPHIES.values()
                },
                "curriculum_hours": curriculum_hours,
            },
        )

    if not rate_source:
        return SavingsClaim(
            licensed=False,
            reason=(
                "A rate was supplied with no source. An unsourced frequency is the part of "
                "a savings claim that cannot be checked, so it is the part that has to be "
                "attributable."
            ),
        )

    if not 0.0 <= misdiagnosis_rate <= 1.0:
        return SavingsClaim(
            licensed=False,
            reason=f"A rate of {misdiagnosis_rate} is not a proportion between 0 and 1.",
        )

    per_cycle = rework_cycle_cost(geography, curriculum_hours)
    avoided = interventions_per_year * misdiagnosis_rate
    return SavingsClaim(
        licensed=True,
        reason="Licensed: the frequency was supplied and attributed.",
        detail={
            "geography": GEOGRAPHIES[geography].name,
            "per_rework_cycle": round(per_cycle, 2),
            "interventions_per_year": interventions_per_year,
            "misdiagnosis_rate": misdiagnosis_rate,
            "rate_source": rate_source,
            "rework_cycles_avoided_per_year": round(avoided, 2),
            "annual_labor_avoided": round(per_cycle * avoided, 2),
            "assumption": (
                "Assumes every avoided misdiagnosis would otherwise have cost exactly one "
                "revision cycle, which is the cheapest thing it could have cost."
            ),
        },
    )

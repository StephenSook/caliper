"""Golden tests E1 to E4 and E10, on synthetic designs with known answers.

These run without the confidential package so they execute in CI. A guard that
can only run on one machine is not a guard.
"""

from __future__ import annotations

from caliper.diagnose.corroborate import scan
from caliper.diagnose.engine import classify, diagnose, rank_defects
from caliper.diagnose.taxonomy import TAXONOMY, RootCause, environment_first
from conftest import Obs


def design(spec: list[tuple[str, str, str, bool]], domain: str = "member_experience") -> list[Obs]:
    """spec rows are (agent, occasion, item, passed)."""
    return [
        Obs(
            eval_id=f"{agent}|{occ}",
            agent_ref=agent,
            rater_ref="R1" if agent in {"A1", "A2", "A3"} else "R2",
            domain=domain,
            item_id=item,
            item_text=item.replace("-", " ").title(),
            passed=passed,
            call_date=f"2026-08-0{occ}",
        )
        for agent, occ, item, passed in spec
    ]


def _fake_audit(**over):
    base = {
        "connectivity": {
            "verdict": "FRAGILE", "calls_double_scored": 0, "n_calls": 6,
            "linkage_fragility": 2, "n_subjects": 6, "bridge_subjects": ["A2", "A3"],
            "remedy": {"action": "link", "citation": "DeMars 2023", "minimum_linking_calls": 6},
        },
        "domains": {"member_experience": {"sufficiency": {"mean_evaluations_per_subject": 1.7}}},
    }
    base["connectivity"].update(over.get("connectivity", {}))
    base["domains"]["member_experience"]["sufficiency"].update(over.get("sufficiency", {}))
    return base


def test_E1_recurring_defect_outranks_a_rare_one():
    rows = []
    for i, agent in enumerate(["A1", "A2", "A3", "A4", "A5", "A6"]):
        rows.append((agent, "1", "recurring", False))
        rows.append((agent, "1", "occasional", i == 0))
    ranked = rank_defects(design(rows), "member_experience")
    assert ranked[0]["item_id"] == "recurring"
    assert ranked[0]["fails"] > ranked[-1]["fails"]


def test_E2_a_single_incident_is_not_promoted_to_systemic():
    """One person, one call. Promoting this to a systemic root cause is the
    failure mode the case names first."""
    rows = [(a, "1", "rare", a != "A1") for a in ["A1", "A2", "A3", "A4", "A5", "A6"]]
    ranked = rank_defects(design(rows), "member_experience")
    entry = next(r for r in ranked if r["item_id"] == "rare")
    assert entry["fails"] == 1
    assert entry["is_systemic"] is False


def test_E3_skill_and_measurement_are_distinguished_by_the_item_not_the_count():
    """Same failure count, different item properties, different cause.

    A functioning item that many people fail is a workforce finding. An item that
    breaches both psychometric floors is a finding about the item.
    """
    functioning = {"difficulty_p": 0.45, "discrimination_rpb": 0.35, "fail_rate": 0.55,
                   "breadth_subjects": 5, "breadth_denominator": 10, "domain": "d"}
    impaired = {"difficulty_p": 0.17, "discrimination_rpb": 0.08, "fail_rate": 0.82,
                "breadth_subjects": 8, "breadth_denominator": 10, "domain": "d"}

    cause_f, _, _, _ = classify(functioning, curriculum_covered=False)
    cause_i, _, _, rejected_i = classify(impaired, curriculum_covered=True)

    assert cause_f == RootCause.SKILL
    assert cause_i == RootCause.MEASUREMENT
    assert {r.cause for r in rejected_i} >= {RootCause.SKILL.value, RootCause.WILL.value}


def test_E4_training_is_correctly_rejected_on_a_measurement_defect():
    """The moment the case explicitly asks for: the system declines to recommend
    training when the evidence points at the instrument."""
    impaired = {"difficulty_p": 0.17, "discrimination_rpb": 0.08, "fail_rate": 0.82,
                "breadth_subjects": 10, "breadth_denominator": 10, "domain": "d"}
    cause, _, evidence, _ = classify(impaired, curriculum_covered=True)
    assert cause == RootCause.MEASUREMENT
    assert TAXONOMY[cause].is_training is False
    assert "calibrate" in TAXONOMY[cause].default_intervention.lower()
    assert any("below" in e.claim.lower() for e in evidence)


def test_E10_ambiguous_evidence_does_not_produce_a_confident_individual_finding():
    rows = []
    for agent in ["A1", "A2", "A3", "A4", "A5", "A6"]:
        rows.append((agent, "1", "item-a", False))
        rows.append((agent, "1", "item-b", True))
    d = diagnose(design(rows), _fake_audit(), curriculum_covered=True)
    assert d.individual_attribution["licensed"] is False
    # A decline is never rendered without the corrective path beside it.
    assert d.individual_attribution["remedy"]["minimum_linking_calls"] >= 1
    assert "common set" in d.individual_attribution["statement"]


def test_individual_attribution_is_licensed_when_the_design_supports_it():
    """The refusal must be a standard, not a hardcoded no. Give it a design that
    actually separates severity from ability and it commits."""
    rows = [(a, "1", "item-a", False) for a in ["A1", "A2", "A3", "A4", "A5", "A6"]]
    audit = _fake_audit(
        connectivity={"verdict": "CONNECTED", "calls_double_scored": 6},
        sufficiency={"mean_evaluations_per_subject": 6.0},
    )
    d = diagnose(design(rows), audit, curriculum_covered=False)
    assert d.individual_attribution["licensed"] is True


def test_corroboration_refuses_an_anti_associated_pairing():
    """Two items that co fail often but move in opposite directions must not be
    reported as corroboration."""
    rows = []
    for i, agent in enumerate(["A1", "A2", "A3", "A4", "A5", "A6"]):
        rows.append((agent, "1", "target", i < 4))
        rows.append((agent, "1", "inverse", i >= 4))
    results = scan(design(rows), "member_experience", "target")
    inverse = next(r for r in results if r.item_id == "inverse")
    assert inverse.phi is not None and inverse.phi < 0
    assert inverse.is_corroborating is False
    assert "anti associated" in inverse.note.lower()


def test_gilbert_orders_environment_causes_before_person_causes():
    ordered = environment_first([RootCause.SKILL, RootCause.PROCESS, RootCause.KNOWLEDGE, RootCause.TOOLING])
    assert TAXONOMY[ordered[0]].row == "environment"
    assert TAXONOMY[ordered[-1]].row == "person"


def test_every_cause_declares_whether_it_is_training():
    for cause, spec in TAXONOMY.items():
        assert isinstance(spec.is_training, bool)
        assert spec.default_intervention
        assert spec.diagnostic_question.endswith("?")
    # Only knowledge and skill are fixed by training. The other six are not, and
    # recommending a course for them is the error the case is built around.
    training = {c for c, s in TAXONOMY.items() if s.is_training}
    assert training == {RootCause.KNOWLEDGE, RootCause.SKILL}

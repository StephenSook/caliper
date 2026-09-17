"""Golden tests E7 and E8, plus the sponsor's own knowledge check gate.

E7 every intervention element traces to an approved diagnosis, coverage 1.0
E8 the practice simulation scores the behaviour the diagnosis produced
"""

from __future__ import annotations

from caliper.intervene.align import validate
from caliper.intervene.item_rewrite import rewrite
from caliper.intervene.objectives import build_activity, build_objective, is_observable

REWRITTEN_ID = "ME-X-v2-CONFIRM-UNDERSTANDING"


def bundle(**over) -> dict:
    objective = build_objective("DIAG-001", REWRITTEN_ID).to_dict()
    activity = build_activity("OBJ-001").to_dict()
    base = {
        "diagnoses": [{"diagnosis_id": "DIAG-001", "human_decision": "APPROVE"}],
        "rewritten_item": {"item_id": REWRITTEN_ID},
        "objectives": [objective],
        "activities": [activity],
        "simulations": [{"simulation_id": "SIM-001", "scored_item_id": REWRITTEN_ID}],
        "metrics": [{"metric_id": "METRIC-001", "instrument_item_id": REWRITTEN_ID}],
        "knowledge_checks": [],
    }
    base.update(over)
    return base


def test_E7_a_fully_traced_bundle_reaches_coverage_one():
    report = validate(bundle())
    assert report.passed is True
    assert report.coverage == 1.0
    assert report.total_elements == 4
    assert len(report.checks_run) >= 6


def test_E8_a_simulation_scoring_the_wrong_behavior_fails():
    """The exact failure the sponsor names in their own process document: a
    technically excellent simulation that scores the wrong behaviour, where
    nobody finds out until the quality data looks identical to before."""
    broken = bundle(simulations=[{"simulation_id": "SIM-001", "scored_item_id": "SOME-OTHER-ITEM"}])
    report = validate(broken)
    assert report.passed is False
    codes = {f.code for f in report.failures}
    assert "SIMULATION_SCORES_WRONG_BEHAVIOR" in codes
    assert report.coverage < 1.0


def test_an_unapproved_diagnosis_orphans_everything_downstream():
    report = validate(bundle(diagnoses=[{"diagnosis_id": "DIAG-001", "human_decision": None}]))
    assert report.passed is False
    assert "OBJECTIVE_ORPHANED" in {f.code for f in report.failures}


def test_an_objective_without_a_criterion_fails():
    """A behaviour with no criterion is the exact defect we diagnosed in the
    original item, so generating one would repeat the mistake we are fixing."""
    obj = build_objective("DIAG-001", REWRITTEN_ID).to_dict()
    obj["criterion"] = ""
    report = validate(bundle(objectives=[obj]))
    assert "OBJECTIVE_NO_CRITERION" in {f.code for f in report.failures}


def test_a_metric_measuring_a_different_item_fails():
    report = validate(bundle(metrics=[{"metric_id": "M1", "instrument_item_id": "OTHER"}]))
    assert "METRIC_MEASURES_WRONG_BEHAVIOR" in {f.code for f in report.failures}


def test_an_empty_bundle_is_not_reported_as_perfect():
    """Zero over zero must not read as full coverage. A validator that passes an
    empty bundle is the vacuous case."""
    report = validate(bundle(objectives=[], activities=[], simulations=[], metrics=[]))
    assert report.total_elements == 0
    assert report.coverage == 0.0


def test_mager_rejects_non_observable_verbs():
    assert is_observable("elicit a restatement from the member") is True
    assert is_observable("understand the difference between billed and allowed") is False
    assert is_observable("know the plan rules") is False


def test_rcx_knowledge_check_gate_runs_all_five_checks():
    good = {
        "kc_id": "KC-001",
        "parent_objective": "OBJ-001",
        "question_stem": "The member says she owes nothing. What is the best next step?",
        "options": [
            "Ask her to restate what she owes",
            "Read the claim lines in order",
            "Apply a courtesy adjustment now",
            "Transfer her to the billing team",
        ],
        "sop_reference": "Cost share SOP",
        "sme_confirmed": True,
    }
    report = validate(bundle(knowledge_checks=[good]))
    gate = report.kc_gate
    assert gate["total"] == 1 and gate["passed"] == 1
    assert set(gate["checks"]) == {
        "objective_aligned",
        "decision_based_question",
        "all_options_plausible",
        "sop_aligned_correct_answer",
        "sme_confirmed",
    }


def test_rcx_gate_flags_a_recall_question_and_a_missing_sme():
    recall = {
        "kc_id": "KC-002",
        "parent_objective": "OBJ-001",
        "question_stem": "Which of the following is a required element of the disclosure?",
        "options": [
            "The recording notice",
            "A callback time estimate",
            "The full privacy policy",
            "The supervisor name",
        ],
        "sop_reference": "",
        "sme_confirmed": False,
    }
    gate = validate(bundle(knowledge_checks=[recall])).kc_gate
    failed = gate["results"][0]["failed_checks"]
    assert "decision_based_question" in failed
    assert "sop_aligned_correct_answer" in failed
    assert "sme_confirmed" in failed
    assert gate["passed"] == 0


def test_rewrite_explains_why_the_old_item_failed():
    item = rewrite(
        "ME-X", "Explained options clearly", ["BELOW_DIFFICULTY_FLOOR", "BELOW_DISCRIMINATION_FLOOR"]
    )
    assert item.observable is True
    assert len(item.why_the_old_item_failed) >= 3
    # Provenance must not overclaim.
    assert item.provenance["claimed_as_standard"] is False
    assert "teach back" in item.provenance["honesty_note"].lower()

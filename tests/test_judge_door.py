"""The judge door and the golden harness.

This page is the answer to "how do you know it works" for a judge who never
speaks to us, so it gets a guard. Rigor a judge cannot reach scores as absent.
"""

from __future__ import annotations

import re

from caliper.api.judge import render
from caliper.evaluation.golden import DIFFERENTIATORS, run

EVIDENCE = {
    "instruments": {
        "member_experience": {
            "kr20": 0.4661,
            "ci_low": -0.0192,
            "ci_high": 0.7756,
            "n_items": 9,
            "items_outside_band": 5,
            "items_zero_variance": 2,
            "verdict": "INDETERMINATE",
            "n_evaluations": 17,
        },
        "compliance": {
            "kr20": 0.3101,
            "ci_low": -0.3087,
            "ci_high": 0.7092,
            "n_items": 10,
            "items_outside_band": 10,
            "items_zero_variance": 7,
            "verdict": "INDETERMINATE",
            "n_evaluations": 17,
        },
    },
    "connectivity": {
        "linkage_fragility": 2,
        "n_subjects": 10,
        "calls_double_scored": 0,
        "n_calls": 17,
        "verdict": "FRAGILE",
    },
    "cross_instrument": {"statement": "All three forms have a lower bound at or below zero."},
    "identifiers_redacted_from_supplied_material": 18,
}

GOLDEN = {
    "cases": [
        {
            "id": "E4",
            "name": "Training is correctly rejected",
            "asserts": "not training",
            "passed": True,
            "detail": "primary cause MEASUREMENT",
            "is_differentiator": True,
        },
        {
            "id": "E1",
            "name": "A recurring defect is recognised",
            "asserts": "frequent and broad",
            "passed": True,
            "detail": "14 of 17",
            "is_differentiator": False,
        },
    ],
    "passed": 2,
    "total": 2,
    "all_passed": True,
}


def test_the_page_renders_without_any_credential():
    """Assert on the absence of an auth SURFACE, not on the absence of the word.

    The first version of this test failed on the page's own sentence, "no
    credential, no login, nothing to install", which is exactly the copy we want.
    A guard that fires on the correct behaviour is worse than no guard.
    """
    page = render(EVIDENCE, GOLDEN)
    assert page.startswith("<!doctype html>")
    for element in ("<form", "<input", 'type="password"', "Authorization"):
        assert element not in page, f"the judge door presents an auth surface: {element}"


def test_the_page_leads_with_the_finding_rather_than_the_architecture():
    page = render(EVIDENCE, GOLDEN)
    head = page[: page.index("Three minutes")]
    assert EVIDENCE["cross_instrument"]["statement"] in head


def test_the_page_carries_no_identifier_and_no_iso_date():
    """The render timestamp is deliberately not ISO, so an ISO date appearing
    here means a real leak rather than our own clock."""
    page = render(EVIDENCE, GOLDEN)
    for pattern, label in [
        (r"\bAgent\s*\d+\b", "agent label"),
        (r"\bQA\s*\d+\b", "evaluator label"),
        (r"\b\d{4}-\d{2}-\d{2}\b", "ISO date of service"),
        (r"\bWDSK\w+\b", "participation id"),
    ]:
        assert not re.search(pattern, page), f"the judge page leaked a {label}"


def test_the_page_states_what_we_refuse_to_claim():
    page = render(EVIDENCE, GOLDEN)
    for claim in ("HIPAA compliance", "teach back", "without its interval"):
        assert claim in page, f"the page does not disclaim {claim!r}"


def test_the_page_prints_a_command_a_stranger_can_run():
    """A number a stranger can recompute is worth more than one they must trust."""
    page = render(EVIDENCE, GOLDEN)
    assert "caliper.instrument.audit" in page
    assert "/api/evidence" in page


def test_differentiator_cases_are_marked():
    page = render(EVIDENCE, GOLDEN)
    assert "star" in page
    assert DIFFERENTIATORS == {"E4", "E11", "E12"}


def test_html_in_the_data_is_escaped():
    """Case details come from the engine, so the page escapes them rather than
    trusting the shape of a string it did not write."""
    hostile = {**GOLDEN, "cases": [{**GOLDEN["cases"][0], "detail": "<script>alert(1)</script>"}]}
    page = render(EVIDENCE, hostile)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_the_golden_harness_runs_without_the_confidential_package():
    """Cases that need the supplied export must FAIL honestly rather than being
    silently skipped, because a skipped case reports clean in the same words as a
    passing one."""
    report = run(data_dir="/nonexistent")
    assert report.total >= 13
    synthetic = {"E2", "E3", "E4", "E6", "E7", "E8", "E11", "E12"}
    for case in report.cases:
        if case.id in synthetic:
            assert case.passed, f"{case.id} should not depend on the supplied package"
        elif not case.passed:
            assert "not present" in case.detail


def test_every_case_states_what_it_asserts():
    """A verdict a reader cannot disagree with is not evidence."""
    for case in run(data_dir="/nonexistent").cases:
        assert case.asserts and len(case.asserts) > 30
        assert case.name

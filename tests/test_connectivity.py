"""Design connectivity and linkage fragility.

Golden test E11 lives here: a deliberately disconnected design must be DETECTED,
because the entire refusal to diagnose an individual rests on this check firing
correctly. A connectivity check that cannot report a disconnection is decorative.
"""

from __future__ import annotations

from conftest import make_obs

from caliper.instrument.connectivity import connectivity_report, linkage_fragility


def test_E11_disconnected_design_is_detected():
    """Two raters, disjoint agents, no shared subject at all.

    Rater severity and subject ability are mathematically confounded here: an
    infinity of estimate sets fit equally well. The report must say DISCONNECTED.
    """
    obs = [
        make_obs("R1", "A1", "d1"),
        make_obs("R1", "A2", "d2"),
        make_obs("R2", "A3", "d3"),
        make_obs("R2", "A4", "d4"),
    ]
    report = connectivity_report(obs)
    assert report.n_components == 2
    assert report.verdict == "DISCONNECTED"
    assert report.bridge_subjects == []


def test_connected_design_with_many_bridges_is_not_fragile():
    """Every agent seen by both raters. Removing any two still leaves a link."""
    obs = []
    for agent in ["A1", "A2", "A3", "A4", "A5"]:
        obs.append(make_obs("R1", agent, "d1"))
        obs.append(make_obs("R2", agent, "d2"))
    report = connectivity_report(obs)
    assert report.n_components == 1
    assert len(report.bridge_subjects) == 5
    assert report.linkage_fragility == 5
    assert report.verdict == "CONNECTED"


def test_fragile_design_rests_on_two_subjects():
    """Connected, but every comparison passes through exactly two agents.

    This is the supplied design's shape and the distinction the pitch turns on:
    'connected' and 'trustworthy' are not the same claim.
    """
    obs = [
        make_obs("R1", "A1", "d1"),
        make_obs("R1", "A2", "d1"),
        make_obs("R1", "A3", "d1"),
        make_obs("R2", "A2", "d2"),
        make_obs("R2", "A3", "d2"),
        make_obs("R2", "A4", "d2"),
    ]
    report = connectivity_report(obs)
    assert report.n_components == 1
    assert report.bridge_subjects == ["A2", "A3"]
    assert report.linkage_fragility == 2
    assert report.verdict == "FRAGILE"
    assert set(report.minimum_removal_set) == {"A2", "A3"}


def test_single_bridge_is_maximally_fragile():
    obs = [
        make_obs("R1", "A1", "d1"),
        make_obs("R1", "A2", "d1"),
        make_obs("R2", "A2", "d2"),
        make_obs("R2", "A3", "d2"),
    ]
    report = connectivity_report(obs)
    assert report.linkage_fragility == 1
    assert report.verdict == "FRAGILE"


def test_double_scored_call_is_distinguished_from_shared_agent():
    """A shared AGENT across different days is a much weaker link than the same
    CALL scored twice. Conflating them overstates the design."""
    across_occasions = [
        make_obs("R1", "A1", "2026-01-01"),
        make_obs("R2", "A1", "2026-02-01"),
    ]
    report = connectivity_report(across_occasions)
    assert report.calls_double_scored == 0
    assert report.link_type == "SUBJECT_LEVEL_ACROSS_OCCASIONS"

    same_call = [
        make_obs("R1", "A1", "2026-01-01"),
        make_obs("R2", "A1", "2026-01-01"),
    ]
    report = connectivity_report(same_call)
    assert report.calls_double_scored == 1
    assert report.link_type == "CALL_LEVEL_DOUBLE_SCORED"


def test_remedy_is_always_attached_to_a_fragile_verdict():
    """A decline is never rendered without the corrective path next to it."""
    obs = [
        make_obs("R1", "A1", "d1"),
        make_obs("R1", "A2", "d1"),
        make_obs("R2", "A2", "d2"),
        make_obs("R2", "A3", "d2"),
    ]
    report = connectivity_report(obs)
    assert report.remedy["minimum_linking_calls"] >= 1
    assert "linking" in report.remedy["action"].lower()
    assert report.remedy["citation"]


def test_linkage_fragility_returns_none_when_raters_cannot_be_separated():
    pairs = [("R1", "A1"), ("R2", "A1")]
    size, removal = linkage_fragility(pairs, ["R1", "R2"], ["A1"])
    assert size == 1 and removal == ["A1"]

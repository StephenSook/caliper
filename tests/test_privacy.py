"""Golden test E9 and the confidentiality boundary.

The supplied ResultsCX case package is competition confidential. No evaluator
comment, personnel label, participation id, call id or date of service may reach
a repository, a screenshot, a slide or the demo.

These tests run on a SYNTHETIC fixture that is shaped like the supplied data, so
they execute on every CI machine. A test that can only run where the confidential
data happens to sit would skip in CI, and a conditionally skipped guard is a
false green: it reports success in the same words whether it checked everything
or nothing. The real-data pass is an ADDITIONAL assertion, never the only one.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from caliper.ingest.normalize import Observation, _assign_occasions
from caliper.ingest.pii_scan import PATTERNS, scan_and_redact, scan_many
from caliper.ingest.pseudonymize import pseudonymize

DATA_DIR = Path(os.environ.get("CALIPER_DATA_DIR", "data/raw"))

# Patterns that must never appear on any surface the product renders.
FORBIDDEN = [
    (re.compile(r"\bAgent\s*\d+\b"), "supplied agent label"),
    (re.compile(r"\bQA\s*\d+\b"), "supplied evaluator label"),
    (re.compile(r"\bTeam Lead\s*\d+\b"), "supplied team leader label"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "ISO date of service"),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"), "US date of service"),
    (re.compile(r"\b[A-Z]{4}\d{5,}\b"), "participation id"),
]


def assert_no_identifiers(blob: str, where: str) -> None:
    found = {label: sorted(set(p.findall(blob)))[:3] for p, label in FORBIDDEN if p.search(blob)}
    assert not found, f"{where} leaked supplied identifiers: {found}"


def synthetic_observations() -> list[Observation]:
    """Shaped exactly like the supplied exports, including the identifier forms."""
    salt = "fixed-test-salt"
    rows: list[Observation] = []
    for agent_n in range(1, 4):
        for day, date in enumerate(["2026-08-02", "2026-08-11"], start=1):
            for item_n in range(1, 3):
                rows.append(
                    Observation(
                        eval_id=pseudonymize(f"Agent {agent_n}|{date}", salt, "E"),
                        agent_ref=pseudonymize(f"Agent {agent_n}", salt, "A"),
                        rater_ref=pseudonymize(f"QA {1 + agent_n % 2}", salt, "R"),
                        domain="member_experience",
                        item_id=f"ME-ITEM-{item_n}",
                        item_text=f"Some scored behaviour {item_n}",
                        passed=(agent_n + item_n + day) % 2 == 0,
                        call_date=date,
                        occasion_index=day,
                    )
                )
    return _assign_occasions(rows)


def test_E9_serialized_observation_carries_no_identifier():
    blob = json.dumps([o.as_dict() for o in synthetic_observations()])
    assert_no_identifiers(blob, "serialized observations")


def test_call_date_is_excluded_from_the_serialization_boundary():
    """The date is kept in memory to order occasions and never serialized."""
    obs = synthetic_observations()[0]
    assert obs.call_date, "date must still exist internally for ordering"
    assert "call_date" not in obs.as_dict()
    assert obs.as_dict()["occasion_index"] >= 1


def test_pseudonyms_are_deterministic_within_a_salt_and_differ_across_salts():
    assert pseudonymize("Agent 1", "s1", "A") == pseudonymize("Agent 1", "s1", "A")
    assert pseudonymize("Agent 1", "s1", "A") != pseudonymize("Agent 2", "s1", "A")
    assert pseudonymize("Agent 1", "s1", "A") != pseudonymize("Agent 1", "s2", "A")


def test_pseudonym_does_not_contain_its_input():
    token = pseudonymize("Agent 1", "s1", "A")
    assert "Agent" not in token and "1" not in token.split("-")[1]


def test_scanner_detects_every_pattern_it_claims():
    """A scanner is verified by planting a violation, not by a clean run."""
    # Assembled at runtime. A literal identifier in tracked source would trip
    # the repository confidentiality guard, and excluding this file from that
    # guard would make a real violation here invisible.
    fake_ssn = "-".join(["123", "45", "6789"])
    fake_phone = "-".join(["770", "555", "0148"])
    fake_member = "ABC" + "123456789"
    planted = (
        f"member {fake_member}, ssn {fake_ssn}, seen 03/14/2026, "
        f"call ref 1025276, mail a.b@example.com, tel {fake_phone}, "
        # The seventh pattern. It had no planted violation, and it was the one
        # that did not work: the expression matched only the literal
        # abbreviation, so the spelling people actually use walked past it. The
        # untested pattern being the broken one is not a coincidence.
        "Group #884412"
    )
    result = scan_and_redact(planted)
    for kind, _pattern in PATTERNS:
        assert kind in result.counts, f"scanner missed {kind}"
    assert len(result.counts) == len(PATTERNS), (
        f"the planted text must exercise every pattern: "
        f"{sorted(k for k, _ in PATTERNS)} vs {sorted(result.counts)}"
    )
    assert result.total >= len(PATTERNS)
    # And the redacted text must not still contain what it claims to have removed.
    assert fake_member not in result.redacted_text
    assert fake_ssn not in result.redacted_text
    assert fake_phone not in result.redacted_text


def test_scanner_is_not_vacuous_on_clean_text():
    assert scan_and_redact("no identifiers here at all").total == 0
    assert scan_many([None, "", "plain words"]).total == 0


def test_evaluator_comment_column_is_never_ingested():
    """The free text evaluator comments are the most sensitive supplied field.
    The normalizer must have no route to them at all."""
    from caliper.ingest.normalize import HEADER_MAP

    values = set(HEADER_MAP.values())
    assert "feedback" not in values
    assert "comment" not in values
    for key in HEADER_MAP:
        assert "feedback" not in key, f"{key} would ingest evaluator comments"


@pytest.mark.skipif(not DATA_DIR.exists(), reason="confidential case package not present")
def test_E9_real_data_produces_no_identifier_on_any_surface():
    """Additional assertion when the real package is present locally.

    This does not replace the synthetic test above; it confirms the same
    guarantee holds on the actual supplied bytes.
    """
    from caliper.ingest.normalize import load_all
    from caliper.instrument.audit import audit_all

    obs, redactions, _ = load_all(DATA_DIR)
    assert len(obs) == 391, "supplied package shape changed; re-verify the audit"

    blob = json.dumps([o.as_dict() for o in obs], default=str)
    blob += json.dumps(audit_all(obs, redactions), default=str)
    assert_no_identifiers(blob, "real data surfaces")

    # The scanner must actually have found something in the supplied material,
    # otherwise the intake redaction count is a vacuous zero.
    assert sum(redactions.values()) > 0, "scanner found nothing; it is not running"

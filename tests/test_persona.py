"""The persona's plan arithmetic must be internally consistent.

The domain mechanics have to be right or the healthcare professionals in the room
will know. Coinsurance is a percentage of the ALLOWED amount, not the billed
amount, and it applies after the deductible is met, so a member who just met her
deductible still owes coinsurance until she reaches the out of pocket maximum.

This is a test rather than a careful reading because the numbers appear in the
persona file, in the spoken demo, and on screen, and three copies of a figure
drift. The first version of this file had an opening line quoting a number that
did not match its own member responsibility.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

PERSONA_DIR = Path("caliper/voice/personas")
PERSONAS = sorted(PERSONA_DIR.glob("*.yaml"))


def test_at_least_one_persona_exists():
    """A parameterised suite over an empty glob passes while testing nothing."""
    assert PERSONAS, f"no persona files found in {PERSONA_DIR}"


@pytest.mark.parametrize("path", PERSONAS, ids=lambda p: p.stem)
def test_plan_arithmetic_is_internally_consistent(path: Path):
    facts = yaml.safe_load(path.read_text())["plan_facts"]

    billed = facts["billed_amount"]
    allowed = facts["allowed_amount"]
    rate = facts["coinsurance_rate"]
    plan_paid = facts["plan_paid"]
    member = facts["member_responsibility"]

    # The network adjustment is billed minus allowed, and an in network member
    # does not owe it.
    assert facts["network_adjustment"] == pytest.approx(billed - allowed)

    # Coinsurance is a percentage of the ALLOWED amount. Taking it off the billed
    # amount is the single most common way to get this wrong.
    assert member == pytest.approx(allowed * rate)
    assert member != pytest.approx(billed * rate), "coinsurance was taken off the billed amount"

    # What the plan paid plus what the member owes reconstitutes the allowed
    # amount. If these do not close, the explanation of benefits is fiction.
    assert plan_paid + member == pytest.approx(allowed)

    assert billed > allowed, "an allowed amount above the billed amount is not a real claim"


@pytest.mark.parametrize("path", PERSONAS, ids=lambda p: p.stem)
def test_the_spoken_opening_line_matches_the_computed_amount(path: Path):
    """The number in her mouth is the number the arithmetic produces."""
    data = yaml.safe_load(path.read_text())
    member = data["plan_facts"]["member_responsibility"]
    line = data["member_state"]["opening_line"].lower()

    words = {
        285.0: "two hundred and eighty five",
        25.0: "twenty five",
        340.0: "three hundred and forty",
    }
    spoken = words.get(member)
    if spoken is None:
        pytest.skip(f"no spoken form recorded for {member}")
    assert spoken in line, f"opening line quotes a different amount than {member}"


@pytest.mark.parametrize("path", PERSONAS, ids=lambda p: p.stem)
def test_persona_is_labelled_synthetic_and_carries_its_disclosure(path: Path):
    data = yaml.safe_load(path.read_text())
    assert data.get("synthetic") is True
    assert data.get("disclosure"), "a synthetic person must carry its disclosure in the file"


@pytest.mark.parametrize("path", PERSONAS, ids=lambda p: p.stem)
def test_identity_verification_precedes_disclosure(path: Path):
    """Omitting the verification step is the fastest way to look fake to a
    healthcare judge. HIPAA requires verifying identity and authority before
    protected health information is disclosed (45 CFR 164.514(h))."""
    data = yaml.safe_load(path.read_text())
    required = [r.lower() for r in data["verification_required"]]
    assert len(required) >= 2, "one identifier is not verification"
    assert any("name" in r for r in required)
    criteria = {c["id"] for c in data["scored_criteria"]}
    assert "VERIFY_IDENTITY" in criteria, "identity verification must be a scored criterion"

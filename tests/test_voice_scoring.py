"""Live practice scoring, and the division of labour it rests on.

The model OBSERVES what was said. The code DECIDES whether that satisfies the
criterion. That split is what makes "we score the practice on the same instrument
that produced the diagnosis" a measurement claim rather than a slogan, so these
tests hold the code side to it.

The other rule enforced here is that every path returns a payload. AWS is
explicit that Nova 2 Sonic waits forever for a toolResult after every toolUse, so
a scoring path that raises turns into a silent call on stage.
"""

from __future__ import annotations

import pytest

from caliper.voice.scoring_tool import FAIL, PASS, PENDING, new_score, safe_score, score

CRITERIA = [
    {"id": "VERIFY_IDENTITY", "text": "Identity verified", "basis": "45 CFR 164.514(h)"},
    {"id": "ALLOWED_VS_BILLED", "text": "Billed distinguished from allowed"},
    {"id": "CONFIRM_UNDERSTANDING", "text": "Member restated what she owes"},
]
FACTS = {"member_responsibility": 285.0, "allowed_amount": 1425.0, "coinsurance_rate": 0.20}


@pytest.fixture
def state():
    return new_score(CRITERIA)


def test_everything_starts_pending(state):
    assert {c.state for c in state.criteria.values()} == {PENDING}
    assert state.all_passed is False


def test_identity_needs_a_name_plus_two_independent_identifiers(state):
    score(state, "VERIFY_IDENTITY", "Can I get your full name?")
    assert state.criteria["VERIFY_IDENTITY"].state == PENDING, "a name alone is not verification"

    score(state, "VERIFY_IDENTITY", "Your full name and date of birth please?")
    assert state.criteria["VERIFY_IDENTITY"].state == PENDING, "one identifier is not enough"

    score(
        state,
        "VERIFY_IDENTITY",
        "Can I get your full name, your date of birth, and the member id on your card?",
    )
    assert state.criteria["VERIFY_IDENTITY"].state == PASS


def test_allowed_versus_billed_needs_both_halves(state):
    score(state, "ALLOWED_VS_BILLED", "The hospital billed seventeen hundred dollars.")
    assert state.criteria["ALLOWED_VS_BILLED"].state == PENDING

    score(state, "ALLOWED_VS_BILLED", "The hospital billed 1700 but the amount the plan allows is 1425.")
    assert state.criteria["ALLOWED_VS_BILLED"].state == PASS


def test_a_wrong_restatement_FAILS_rather_than_passing(state):
    """The criterion has to be able to say no, or the practice is a rubber stamp
    and the whole closed loop claim is theatre."""
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="So I owe nothing then.",
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == FAIL


def test_a_correct_amount_without_a_reason_still_fails(state):
    """The criterion is the amount AND the reason. Parroting a number back is not
    evidence of understanding."""
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="285 dollars.",
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == FAIL
    assert "no reason" in state.criteria["CONFIRM_UNDERSTANDING"].evidence


def test_a_reason_without_the_right_amount_fails(state):
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="I owe 500 because of my coinsurance.",
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == FAIL


def test_a_correct_restatement_in_her_own_words_passes(state):
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text=(
            "So meeting my deductible did not mean I was done. "
            "My twenty percent just started. I owe 285 dollars."
        ),
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == PASS


def test_the_spoken_form_of_the_number_counts(state):
    """A member says the number out loud. Requiring digits would fail a correct
    answer for being spoken, which is the wrong failure."""
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="I owe two hundred and eighty five dollars, it's my coinsurance.",
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == PASS


def test_the_member_has_to_do_it_herself(state):
    """If the representative states the number, the criterion is not met. The
    item scores whether the EXPLANATION landed, not whether it was delivered."""
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "You owe 285 dollars because your coinsurance is twenty percent.",
        member_restated=False,
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == PENDING


def test_an_unknown_criterion_returns_a_payload_rather_than_raising(state):
    out = safe_score(state, {"criterion_id": "NOT_A_CRITERION"}, FACTS)
    assert "error" in out
    assert "criteria" in out, "a refusal must still carry the current form state"


def test_malformed_arguments_still_produce_a_tool_result(state):
    """Nova waits forever for a toolResult after a toolUse, so no input may cause
    a path that returns nothing."""
    for bad in (
        {},
        {"criterion_id": None},
        {"criterion_id": "CONFIRM_UNDERSTANDING", "member_restated": "yes"},
    ):
        out = safe_score(state, bad, FACTS)
        assert isinstance(out, dict) and "criteria" in out


def test_the_payload_shape_is_what_the_interface_renders(state):
    payload = state.as_payload()
    assert set(payload) == {"criteria"}
    for c in payload["criteria"]:
        assert set(c) == {"id", "state", "evidence"}
        assert c["state"] in {PASS, FAIL, PENDING}


def test_all_passed_only_when_every_criterion_passes(state):
    score(state, "VERIFY_IDENTITY", "full name, date of birth, and the member id please?")
    score(state, "ALLOWED_VS_BILLED", "billed 1700, the plan allows 1425")
    assert state.all_passed is False
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="I owe 285, that's my twenty percent coinsurance.",
        plan_facts=FACTS,
    )
    assert state.all_passed is True


def test_a_passed_criterion_is_sticky(state):
    """Found by a live call: the scorer runs on every turn, so a later turn that
    does not re mention the billed amount was silently downgrading a criterion
    the representative had already satisfied. On screen that is a PASS flickering
    away, which is the worst thing a live scored form can do in front of a judge.
    """
    score(state, "ALLOWED_VS_BILLED", "They billed 1700 but the plan allows 1425.")
    assert state.criteria["ALLOWED_VS_BILLED"].state == PASS

    score(state, "ALLOWED_VS_BILLED", "Let me check one more thing for you.")
    assert state.criteria["ALLOWED_VS_BILLED"].state == PASS, "a passed criterion moved back"


def test_a_failed_criterion_can_still_be_earned(state):
    """Stickiness must not trap a FAIL. A second attempt is a real outcome and the
    representative explaining it again and succeeding has to be able to score."""
    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="I owe nothing.",
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == FAIL

    score(
        state,
        "CONFIRM_UNDERSTANDING",
        "",
        member_restated=True,
        restatement_text="I owe 285, that is my twenty percent coinsurance.",
        plan_facts=FACTS,
    )
    assert state.criteria["CONFIRM_UNDERSTANDING"].state == PASS

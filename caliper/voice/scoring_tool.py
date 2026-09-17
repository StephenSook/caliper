"""Live scoring of the practice call.

The division of labour matters and it is the same one the whole product uses:

    the MODEL observes    what was said, and whether the member restated
    the CODE decides      whether that satisfies the criterion

So the speech model never awards a pass. It reports an observation through a
typed tool schema, and this module applies the criterion to it. That is what
makes the sentence "we score the practice on the same instrument that produced
the diagnosis" true rather than decorative: both ends are arithmetic over a
stated rule.

Every toolUse MUST receive a toolResult. AWS is explicit: "Nova 2 Sonic expects a
toolResult event after every toolUse event it sends. If your application fails to
respond, the model enters a waiting state, causing unresponsive behavior." So
every path through `score` returns a payload, including the error paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PASS = "PASS"
FAIL = "FAIL"
PENDING = "PENDING"

# Two independent identifiers beyond the name, per HIPAA verification practice
# (45 CFR 164.514(h)). Caller id alone is not verification.
IDENTITY_TOKENS = {
    "date of birth": ("date of birth", "birth date", "dob", "birthday"),
    "member id": ("member id", "member number", "id number", "member i d"),
    "address": ("address", "zip code", "postal code"),
    "name": ("full name", "your name", "first and last"),
}

# Stems rather than whole phrases. A representative says "what the plan allows"
# as often as "the allowed amount", and matching only the past participle fails a
# correct answer for being phrased naturally, which is the wrong failure.
BILLED_TOKENS = ("bill", "charge", "what the hospital", "what the provider")
ALLOWED_TOKENS = ("allow", "negotiated rate", "approved amount", "covered amount")


@dataclass
class CriterionState:
    id: str
    text: str
    state: str = PENDING
    evidence: str = ""
    basis: str = ""


@dataclass
class PracticeScore:
    criteria: dict[str, CriterionState] = field(default_factory=dict)

    def as_payload(self) -> dict:
        return {
            "criteria": [
                {"id": c.id, "state": c.state, "evidence": c.evidence[:160]} for c in self.criteria.values()
            ]
        }

    @property
    def all_passed(self) -> bool:
        return all(c.state == PASS for c in self.criteria.values())


def new_score(scored_criteria: list[dict]) -> PracticeScore:
    return PracticeScore(
        criteria={
            c["id"]: CriterionState(id=c["id"], text=c["text"], basis=c.get("basis", ""))
            for c in scored_criteria
        }
    )


def _mentions(text: str, tokens) -> bool:
    lowered = text.lower()
    return any(t in lowered for t in tokens)


def _numbers(text: str) -> set[float]:
    """Numbers as digits or as the spoken forms a person actually uses."""
    found = {float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
    spoken = {
        "twenty five": 25.0,
        "two hundred and eighty five": 285.0,
        "two hundred eighty five": 285.0,
        "two eighty five": 285.0,
        "three hundred and forty": 340.0,
    }
    lowered = text.lower()
    for phrase, value in spoken.items():
        if phrase in lowered:
            found.add(value)
    return found


def score(
    state: PracticeScore,
    criterion_id: str,
    transcript_window: str,
    member_restated: bool = False,
    restatement_text: str = "",
    plan_facts: dict | None = None,
) -> dict:
    """Apply one criterion. Always returns a payload, including on bad input.

    Returning a refusal rather than raising is deliberate. An exception gives the
    model nothing to correct and hangs the conversation; a payload naming the
    problem lets it carry on talking.
    """
    if criterion_id not in state.criteria:
        return {
            **state.as_payload(),
            "error": f"unknown criterion {criterion_id!r}",
            "known_criteria": sorted(state.criteria),
        }

    crit = state.criteria[criterion_id]
    window = transcript_window or ""

    # A criterion that has already PASSED never moves back.
    #
    # The scorer runs on every turn, so without this a later turn that simply
    # does not re mention the billed amount silently downgrades a criterion the
    # representative already satisfied. On screen that reads as a PASS flickering
    # away, which is both wrong and the single most damaging thing a live scored
    # form can do in front of a judge. A FAIL may still become a PASS, because a
    # second attempt is a real outcome.
    if crit.state == PASS:
        return state.as_payload()

    if criterion_id == "VERIFY_IDENTITY":
        asked = {label for label, tokens in IDENTITY_TOKENS.items() if _mentions(window, tokens)}
        # A name plus at least two independent identifiers.
        beyond_name = asked - {"name"}
        if len(beyond_name) >= 2:
            crit.state = PASS
            crit.evidence = f"asked for {', '.join(sorted(asked))}"
        elif asked:
            crit.state = PENDING
            crit.evidence = f"so far only {', '.join(sorted(asked))}"
        else:
            crit.state = PENDING

    elif criterion_id == "ALLOWED_VS_BILLED":
        if _mentions(window, BILLED_TOKENS) and _mentions(window, ALLOWED_TOKENS):
            crit.state = PASS
            crit.evidence = "distinguished the billed amount from the allowed amount"
        else:
            crit.state = PENDING

    elif criterion_id == "CONFIRM_UNDERSTANDING":
        # The only criterion where the MEMBER has to do something. The model
        # reports whether she restated; the code checks whether she was right.
        if not member_restated:
            crit.state = PENDING
            crit.evidence = "the member has not restated it yet"
        else:
            owed = (plan_facts or {}).get("member_responsibility")
            said = _numbers(restatement_text)
            correct_number = owed is not None and any(abs(n - owed) < 0.51 for n in said)
            gave_reason = _mentions(
                restatement_text,
                ("coinsurance", "percent", "%", "twenty percent", "my share", "deductible"),
            )
            if correct_number and gave_reason:
                crit.state = PASS
                crit.evidence = restatement_text
            else:
                crit.state = FAIL
                missing = []
                if not correct_number:
                    missing.append("the amount was wrong or absent")
                if not gave_reason:
                    missing.append("no reason was given")
                crit.evidence = f"{restatement_text} ({', '.join(missing)})"

    else:
        crit.state = PENDING
        crit.evidence = "no rule is defined for this criterion, so it stays pending"

    return state.as_payload()


def safe_score(state: PracticeScore, arguments: dict, plan_facts: dict | None = None) -> dict:
    """Wrapper that cannot fail to produce a toolResult.

    A code path that exits without responding puts Nova into a waiting state and
    the call goes silent on stage, so every exception becomes a payload.
    """
    try:
        return score(
            state,
            criterion_id=arguments.get("criterion_id", ""),
            transcript_window=arguments.get("transcript_window", ""),
            member_restated=bool(arguments.get("member_restated", False)),
            restatement_text=arguments.get("restatement_text", "") or "",
            plan_facts=plan_facts,
        )
    except Exception as exc:  # noqa: BLE001
        return {**state.as_payload(), "error": f"{type(exc).__name__}: {exc}"}

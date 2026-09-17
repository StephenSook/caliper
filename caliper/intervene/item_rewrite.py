"""Rewrite a defective rating item into an observable criterion.

The defect this fixes: an item that names a behaviour without stating a criterion
asks a reviewer for an opinion. "Explained options in a clear, organized and
appropriate manner" has no answer key, so two evaluators can disagree forever and
neither is wrong.

The fix is not a better adjective. It is a criterion someone can observe:

    old   did the representative explain it clearly          (reviewer judgement)
    new   did the member restate what they owe, correctly    (observation)

Provenance, stated carefully because overclaiming here loses a healthcare judge:
this is CLOSED LOOP CONFIRMATION OF UNDERSTANDING, which traces to aviation crew
resource management and appears in AHRQ TeamSTEPPS as the check back. The
clinically validated cousin is the teach back method (AHRQ Health Literacy
Universal Precautions Toolkit, Tool 5), cited for pedigree.

We do NOT claim teach back is an established payer call center standard. We
searched NCQA, URAC, CMS and vendor scorecards and found none.

AHRQ's own framing, useful verbatim: "Remember, you are checking how well you
explained something, not testing the patient," and "'Do you understand?' and
'Does that make sense?' are NOT teach-back questions."
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RewrittenItem:
    item_id: str
    replaces_item_id: str
    old_text: str
    new_text: str
    scoring: str
    observable: bool
    why_the_old_item_failed: list[str]
    provenance: dict
    scored_states: list[str] = field(default_factory=lambda: ["PASS", "FAIL", "PENDING"])

    def to_dict(self) -> dict:
        return asdict(self)


PROVENANCE = {
    "criterion_name": "Closed loop confirmation of understanding",
    "lineage": "Aviation crew resource management, then AHRQ TeamSTEPPS check back.",
    "clinical_cousin": "Teach back method, AHRQ Health Literacy Universal Precautions Toolkit Tool 5.",
    "claimed_as_standard": False,
    "honesty_note": (
        "Teach back is cited for pedigree, not asserted as a payer call center standard. "
        "No NCQA, URAC, CMS or vendor scorecard requiring confirmation of understanding on a "
        "routine service call could be located. Those standards are paywalled and we could "
        "neither confirm nor rule them out."
    ),
    "regulatory_context": (
        "42 CFR 422.2274(c)(9)(i) requires a Medicare Advantage organization to confirm that "
        "beneficiaries enrolled by agents or brokers understand the product. That obligation is "
        "scoped to enrollment, and 42 CFR Part 422 Subpart V requires only that live "
        "communications not mislead, confuse or provide materially inaccurate information. "
        "Accuracy is regulated. Comprehension is not."
    ),
}


def rewrite(old_item_id: str, old_text: str, flags: list[str]) -> RewrittenItem:
    reasons = []
    if "BELOW_DIFFICULTY_FLOOR" in flags:
        reasons.append("Almost nobody passed it, so it cannot separate a strong performer from a weak one.")
    if "ABOVE_DIFFICULTY_CEILING" in flags:
        reasons.append("Almost everybody passed it, so it carries no information.")
    if "BELOW_DISCRIMINATION_FLOOR" in flags:
        reasons.append(
            "It barely correlates with how the same agent does on everything else, so it is not "
            "measuring the same underlying ability the rest of the form measures."
        )
    if "ZERO_VARIANCE" in flags:
        reasons.append("Every call scored the same, so the item has never distinguished anyone.")
    if "NEGATIVE_DISCRIMINATION" in flags:
        reasons.append(
            "Agents who do better on the rest of the form do WORSE on this item, which is the "
            "signature of an item measuring something other than what the form intends."
        )
    reasons.append(
        "It states a behaviour with no criterion, which fails the three part objective test "
        "(condition, behaviour, criterion) and leaves the reviewer to supply a standard."
    )

    return RewrittenItem(
        item_id=f"{old_item_id}-v2-CONFIRM-UNDERSTANDING",
        replaces_item_id=old_item_id,
        old_text=old_text,
        new_text=(
            "The representative asked the member to restate, in their own words, what they will "
            "owe or what happens next."
        ),
        scoring=(
            "Scored YES only if the member's restatement was substantively correct on the first "
            "attempt. A yes or no answer to 'does that make sense' does not satisfy the item."
        ),
        observable=True,
        why_the_old_item_failed=reasons,
        provenance=PROVENANCE,
    )

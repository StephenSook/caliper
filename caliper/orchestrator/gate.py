"""The human approval gate.

The gate is a workflow step, not a disclaimer. Nothing downstream of a diagnosis
runs until a human records a decision, and the decision itself is persisted
before generation begins, so the approval survives the process that asked for it.

Four actions, because "approve or not" is not how a reviewer actually thinks:
APPROVE, EDIT, REJECT, REQUEST_MORE_EVIDENCE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .run_state import DECISIONS, RunState, RunStore


class GateNotSatisfied(RuntimeError):
    """Raised when generation is attempted before a human has approved."""


@dataclass
class GatePrompt:
    run_id: str
    diagnosis_id: str
    behavior: str
    root_cause_primary: str
    root_cause_secondary: str | None
    confidence: str
    observed: dict
    alternatives_rejected: list[dict]
    individual_attribution: dict
    recommended_intervention_class: str
    is_training_intervention: bool
    actions: list[str]


def open_gate(store: RunStore, run_id: str, diagnosis: dict) -> GatePrompt:
    """Pause the run and surface everything the human needs on one screen."""
    store.transition(
        run_id,
        RunState.AWAITING_APPROVAL,
        actor="system",
        note=f"awaiting human decision on {diagnosis['diagnosis_id']}",
        merge={"diagnosis": diagnosis},
    )
    return GatePrompt(
        run_id=run_id,
        diagnosis_id=diagnosis["diagnosis_id"],
        behavior=diagnosis["behavior"],
        root_cause_primary=diagnosis["root_cause_primary"],
        root_cause_secondary=diagnosis.get("root_cause_secondary"),
        confidence=diagnosis["confidence"],
        observed=diagnosis["observed"],
        alternatives_rejected=diagnosis["alternatives_rejected"],
        individual_attribution=diagnosis["individual_attribution"],
        recommended_intervention_class=diagnosis["recommended_intervention_class"],
        is_training_intervention=diagnosis["is_training_intervention"],
        actions=sorted(DECISIONS),
    )


def record_decision(
    store: RunStore,
    run_id: str,
    decision: str,
    actor: str,
    note: str = "",
    edited_diagnosis: dict | None = None,
    actor_verified: bool = False,
) -> RunState:
    if decision not in DECISIONS:
        raise ValueError(f"unknown decision {decision}. Legal: {sorted(DECISIONS)}")
    if store.state(run_id) is not RunState.AWAITING_APPROVAL:
        raise GateNotSatisfied(f"run {run_id} is {store.state(run_id).value}, not awaiting approval")

    merge = {
        "human_decision": decision,
        "decided_by": actor,
        # Recorded NEXT TO the name, never instead of it. A product that refuses
        # to over assert about a workforce has no business over asserting about
        # its own audit trail, so an approval whose actor could not be proven is
        # stored as a claim and labelled as one.
        "decided_by_verified": actor_verified,
        "approved_at": datetime.now(UTC).isoformat(),
    }
    if decision == "APPROVE":
        target = RunState.APPROVED
    elif decision == "EDIT":
        if edited_diagnosis is None:
            raise ValueError("EDIT requires the edited diagnosis")
        merge["diagnosis"] = edited_diagnosis
        target = RunState.APPROVED
    elif decision == "REJECT":
        target = RunState.REJECTED
    else:
        target = RunState.DIAGNOSED  # more evidence requested, re diagnose

    store.transition(
        run_id,
        target,
        actor=actor,
        note=f"{decision}: {note}",
        merge=merge,
        actor_verified=actor_verified,
    )

    # Requesting more evidence has to leave the gate OPEN.
    #
    # It moved the run to DIAGNOSED and nothing ever reopened the gate, because
    # open_gate is only called once, from pipeline.start. So the fourth button on
    # the approval screen permanently stranded the run: every later decision and
    # the generate call all raised GateNotSatisfied, and the interface had
    # already hidden the buttons. A judge pressing it mid demonstration had no
    # way forward but a full re audit.
    #
    # It also made two judge facing statements false. The architecture diagram
    # draws a self loop on AWAITING_APPROVAL for this action, and the docs say
    # "the gate stays shut", when in fact it closed and could not be reopened.
    #
    # Reopening here makes the drawn behaviour the real behaviour. The ledger
    # keeps both steps, so the request and the reopening are both visible rather
    # than one silently undoing the other.
    if target is RunState.DIAGNOSED:
        store.transition(
            run_id,
            RunState.AWAITING_APPROVAL,
            actor=actor,
            note="gate reopened pending further evidence",
            actor_verified=actor_verified,
        )
        return RunState.AWAITING_APPROVAL

    return target


def require_approved(store: RunStore, run_id: str) -> dict:
    """Called by generation. Refuses rather than proceeding unapproved."""
    state = store.state(run_id)
    if state not in {
        RunState.APPROVED,
        RunState.INTERVENTION_GENERATED,
        RunState.PRACTICE_SCORED,
        RunState.COMPLETE,
    }:
        raise GateNotSatisfied(
            f"generation refused: run {run_id} is {state.value}. A human must approve the "
            "diagnosis before any training content is produced, because polished content built "
            "on an unconfirmed diagnosis is the exact downstream rework the case describes."
        )
    payload = store.payload(run_id)
    if payload.get("human_decision") not in {"APPROVE", "EDIT"}:
        raise GateNotSatisfied(f"generation refused: no approval recorded on run {run_id}")
    return payload["diagnosis"]

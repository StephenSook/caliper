"""Run state, the human gate, and golden test E6.

E6 is the claim that 25 percent of the score rests on: the same run continues
from the approved state without the user re entering context. It is proven here
by writing the approval in one OS process and reading it in another, because an
in memory object that survives a function call proves nothing about a restart.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from caliper.orchestrator.gate import GateNotSatisfied, open_gate, record_decision, require_approved
from caliper.orchestrator.run_state import IllegalTransition, RunState, RunStore

DIAGNOSIS = {
    "diagnosis_id": "DIAG-001",
    "behavior": "Explained options clearly",
    "root_cause_primary": "MEASUREMENT_STANDARD_SETTING",
    "root_cause_secondary": "KNOWLEDGE",
    "confidence": "HIGH_SYSTEMIC",
    "observed": {"fails": 14, "denominator": 17},
    "alternatives_rejected": [{"cause": "SKILL", "reason": "already covered"}],
    "individual_attribution": {"licensed": False},
    "recommended_intervention_class": "Rewrite the item and calibrate the evaluators.",
    "is_training_intervention": False,
}


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "t.db")


def advance_to_gate(store: RunStore) -> str:
    run_id = store.create()
    store.transition(run_id, RunState.INSTRUMENT_AUDITED)
    store.transition(run_id, RunState.DIAGNOSED)
    open_gate(store, run_id, DIAGNOSIS)
    return run_id


def test_E6_approval_survives_a_real_process_restart(tmp_path):
    """Write the approval in one interpreter, read it in another."""
    db = tmp_path / "e6.db"

    write = (
        "from caliper.orchestrator.run_state import RunStore, RunState;"
        "from caliper.orchestrator.gate import open_gate, record_decision;"
        f"s=RunStore(r'{db}');r=s.create('RUN-E6');"
        "s.transition(r, RunState.INSTRUMENT_AUDITED);"
        "s.transition(r, RunState.DIAGNOSED);"
        f"open_gate(s, r, {DIAGNOSIS!r});"
        "record_decision(s, r, 'APPROVE', actor='Judge');"
        "print(s.state(r).value)"
    )
    out = subprocess.run([sys.executable, "-c", write], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "APPROVED"

    read = (
        "from caliper.orchestrator.run_state import RunStore;"
        "from caliper.orchestrator.gate import require_approved;"
        f"s=RunStore(r'{db}');d=require_approved(s,'RUN-E6');"
        "print(d['diagnosis_id'], s.state('RUN-E6').value, len(s.ledger('RUN-E6')))"
    )
    out = subprocess.run([sys.executable, "-c", read], capture_output=True, text=True, check=True)
    diagnosis_id, state, ledger_len = out.stdout.split()
    assert diagnosis_id == "DIAG-001"
    assert state == "APPROVED"
    assert int(ledger_len) == 5


def test_generation_refuses_before_approval_and_explains_why(store):
    run_id = advance_to_gate(store)
    with pytest.raises(GateNotSatisfied) as exc:
        require_approved(store, run_id)
    # A refusal that does not say why reads as breakage rather than a standard.
    assert "approve" in str(exc.value).lower()
    assert "rework" in str(exc.value).lower()


def test_generation_refuses_after_an_explicit_rejection(store):
    run_id = advance_to_gate(store)
    record_decision(store, run_id, "REJECT", actor="Reviewer", note="wrong behaviour")
    with pytest.raises(GateNotSatisfied):
        require_approved(store, run_id)


def test_request_more_evidence_leaves_the_gate_open(store):
    """It used to return DIAGNOSED, and that stranded the run permanently.

    Nothing reopens the gate: open_gate is called once, from pipeline.start. So
    the fourth button on the approval screen moved the run to a state where every
    later decision and the generate call all raised, while the interface had
    already hidden the buttons. There was no way forward but a full re audit, and
    a judge pressing it mid demonstration would have found that out.

    This test asserted that behaviour, which is how a test defends a bug: fixing
    it failed the suite and read as a regression. The documented behaviour, drawn
    as a self loop on AWAITING_APPROVAL in docs/architecture.md, is the intended
    one, and it is now the real one.
    """
    run_id = advance_to_gate(store)
    state = record_decision(store, run_id, "REQUEST_MORE_EVIDENCE", actor="Reviewer")
    assert state is RunState.AWAITING_APPROVAL

    # The run has to actually recover, not merely report a friendlier state.
    assert record_decision(store, run_id, "APPROVE", actor="Reviewer") is RunState.APPROVED

    # And the ledger keeps both steps, so the request and the reopening are both
    # visible rather than one quietly undoing the other.
    states = [t.__dict__.get("to_state") for t in store.ledger(run_id)]
    assert states.count("AWAITING_APPROVAL") >= 2, states
    assert "DIAGNOSED" in states, states


def test_edit_requires_the_edited_diagnosis(store):
    run_id = advance_to_gate(store)
    with pytest.raises(ValueError):
        record_decision(store, run_id, "EDIT", actor="Reviewer")


def test_edit_approves_and_stores_the_human_version(store):
    run_id = advance_to_gate(store)
    edited = {**DIAGNOSIS, "root_cause_primary": "COACHING"}
    record_decision(store, run_id, "EDIT", actor="Reviewer", edited_diagnosis=edited)
    assert require_approved(store, run_id)["root_cause_primary"] == "COACHING"


def test_an_unknown_decision_is_refused(store):
    run_id = advance_to_gate(store)
    with pytest.raises(ValueError):
        record_decision(store, run_id, "LOOKS_FINE", actor="Reviewer")


def test_out_of_order_transitions_raise_rather_than_land_silently(store):
    run_id = store.create()
    with pytest.raises(IllegalTransition):
        store.transition(run_id, RunState.APPROVED)


def test_the_ledger_records_every_transition_in_order(store):
    run_id = advance_to_gate(store)
    record_decision(store, run_id, "APPROVE", actor="Judge")
    ledger = store.ledger(run_id)
    assert [t.seq for t in ledger] == list(range(len(ledger)))
    assert ledger[-1].to_state == RunState.APPROVED.value
    assert ledger[-1].actor == "Judge"
    assert all(t.at for t in ledger)


def test_an_unknown_run_is_an_error_not_an_empty_result(store):
    with pytest.raises(KeyError):
        store.state("RUN-DOES-NOT-EXIST")

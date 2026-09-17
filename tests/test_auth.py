"""Operator identity, and the audit trail telling the truth about itself.

The product's whole argument is that a system should not assert what its evidence
cannot support. These tests hold it to that about its OWN records: an approval
whose actor could not be proven is stored as a claim and labelled as one, rather
than appearing in the ledger as a confirmed human decision.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from caliper.api.auth import (
    allowed_origins,
    auth_required,
    check_websocket_origin,
    resolve_operator,
    resolve_operator_ws,
)
from caliper.orchestrator.gate import open_gate, record_decision
from caliper.orchestrator.run_state import RunState, RunStore

DIAGNOSIS = {
    "diagnosis_id": "DIAG-001",
    "behavior": "b",
    "root_cause_primary": "MEASUREMENT_STANDARD_SETTING",
    "root_cause_secondary": None,
    "confidence": "HIGH_SYSTEMIC",
    "observed": {},
    "alternatives_rejected": [],
    "individual_attribution": {"licensed": False},
    "recommended_intervention_class": "x",
    "is_training_intervention": False,
}


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "auth.db")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("CALIPER_OPERATOR_TOKEN", raising=False)
    monkeypatch.delenv("CALIPER_OPERATOR_ROSTER", raising=False)
    monkeypatch.delenv("CALIPER_ALLOWED_ORIGINS", raising=False)


def at_gate(store: RunStore) -> str:
    run_id = store.create()
    store.transition(run_id, RunState.INSTRUMENT_AUDITED)
    store.transition(run_id, RunState.DIAGNOSED)
    open_gate(store, run_id, DIAGNOSIS)
    return run_id


def test_without_a_configured_token_the_actor_is_recorded_as_unverified():
    """Fails OPEN for local development, but never pretends the name is proven."""
    assert auth_required() is False
    operator = resolve_operator("Judge", authorization=None)
    assert operator.verified is False
    assert "unverified" in operator.label


def test_a_matching_shared_token_verifies_the_actor(monkeypatch):
    monkeypatch.setenv("CALIPER_OPERATOR_TOKEN", "s3cret-token")
    assert auth_required() is True
    operator = resolve_operator("Dana", authorization="Bearer s3cret-token")
    assert operator.verified is True
    assert operator.name == "Dana"


def test_a_roster_token_supplies_the_name_rather_than_the_caller(monkeypatch):
    """The strongest form: the name comes from what the token proves, so a caller
    cannot approve a diagnosis under somebody else's name."""
    monkeypatch.setenv("CALIPER_OPERATOR_ROSTER", "tok-a:Lead Designer,tok-b:QA Manager")
    operator = resolve_operator("I am totally the QA Manager", authorization="Bearer tok-a")
    assert operator.verified is True
    assert operator.name == "Lead Designer"


def test_a_wrong_or_missing_token_is_refused_once_auth_is_configured(monkeypatch):
    monkeypatch.setenv("CALIPER_OPERATOR_TOKEN", "s3cret-token")
    for header in (None, "Bearer wrong", "s3cret-token", ""):
        with pytest.raises(HTTPException) as exc:
            resolve_operator("Judge", authorization=header)
        assert exc.value.status_code == 401


def test_the_ledger_stores_whether_the_actor_was_proven(store):
    run_id = at_gate(store)
    record_decision(store, run_id, "APPROVE", actor="Judge", actor_verified=False)
    entry = store.ledger(run_id)[-1]
    assert entry.actor == "Judge"
    assert entry.actor_verified is False
    assert store.payload(run_id)["decided_by_verified"] is False


def test_a_verified_approval_is_marked_verified(store):
    run_id = at_gate(store)
    record_decision(store, run_id, "APPROVE", actor="Lead Designer", actor_verified=True)
    assert store.ledger(run_id)[-1].actor_verified is True
    assert store.payload(run_id)["decided_by_verified"] is True


def test_verification_is_never_stored_instead_of_the_name(store):
    """Recorded NEXT TO the name, not in place of it, so the trail still says who
    claimed the decision even when it could not prove them."""
    run_id = at_gate(store)
    record_decision(store, run_id, "APPROVE", actor="Someone", actor_verified=False)
    payload = store.payload(run_id)
    assert payload["decided_by"] == "Someone"
    assert payload["decided_by_verified"] is False


def test_cors_is_never_a_wildcard():
    """A wildcard origin on an endpoint that records approvals lets any page a
    reviewer has open drive the audit trail."""
    origins = allowed_origins()
    assert "*" not in origins
    assert all(o.startswith("http") for o in origins)


def test_cors_allowlist_is_configurable(monkeypatch):
    monkeypatch.setenv("CALIPER_ALLOWED_ORIGINS", "https://caliper.example, https://demo.example")
    assert allowed_origins() == ["https://caliper.example", "https://demo.example"]


# --------------------------------------------------------------------------
# WebSocket handshake. A socket is NOT covered by CORS, so the browser same
# origin policy never sees it and the Origin check IS the control rather than a
# second layer of one. This socket also mutates run state, so it cannot be
# treated like the read only evidence endpoints.
# --------------------------------------------------------------------------


def test_a_disallowed_origin_is_refused_even_with_a_valid_token(monkeypatch):
    monkeypatch.setenv("CALIPER_OPERATOR_TOKEN", "tok")
    assert check_websocket_origin("https://evil.example") is False
    assert check_websocket_origin("http://localhost:5173") is True


def test_a_missing_origin_is_allowed_only_when_no_secret_is_configured(monkeypatch):
    """A non browser client (the smoke test, a CLI) sends no Origin and must work
    on a laptop. A deployed instance with a secret configured must refuse it."""
    assert check_websocket_origin(None) is True
    monkeypatch.setenv("CALIPER_OPERATOR_TOKEN", "tok")
    assert check_websocket_origin(None) is False


def test_the_websocket_token_verifies_an_operator(monkeypatch):
    monkeypatch.setenv("CALIPER_OPERATOR_TOKEN", "tok")
    assert resolve_operator_ws("tok").verified is True
    assert resolve_operator_ws("wrong") is None
    assert resolve_operator_ws(None) is None
    assert resolve_operator_ws("") is None


def test_a_roster_token_names_the_websocket_operator(monkeypatch):
    monkeypatch.setenv("CALIPER_OPERATOR_ROSTER", "tk:QA Manager")
    op = resolve_operator_ws("tk", claimed_name="whoever")
    assert op is not None and op.verified is True and op.name == "QA Manager"


def test_without_a_secret_the_websocket_operator_is_unverified_not_refused(monkeypatch):
    """Fails open on a laptop so the demo needs no ceremony, but the practice
    score it writes is recorded as a claim rather than a verified record."""
    op = resolve_operator_ws(None)
    assert op is not None
    assert op.verified is False


def test_same_origin_is_always_allowed_because_the_hostname_is_not_knowable(monkeypatch):
    """The interface is served by this same server, so on a tunnel or any deploy
    the Origin is whatever hostname the client reached us on, which cannot be
    listed in advance. Comparing Origin to Host is exactly the same origin test
    and does not widen anything: a hostile page is on a different origin by
    definition."""
    monkeypatch.setenv("CALIPER_OPERATOR_TOKEN", "tok")
    tunnel = "caliper-demo.trycloudflare.com"
    assert check_websocket_origin(f"https://{tunnel}", host=tunnel) is True
    assert check_websocket_origin("https://evil.example", host=tunnel) is False
    assert check_websocket_origin(f"https://{tunnel}", host="other.host") is False

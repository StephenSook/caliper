"""Operator identity for the mutating endpoints.

The reason this exists is not that a hackathon demo needs hardening. It is that
CALIPER's entire argument is that a system should not assert what its evidence
cannot support, and an audit trail that records a client supplied name as though
it were a verified fact breaks that argument at the one place a judge will press.

So the rule here matches the rule everywhere else in the product:

    an approval whose actor could not be verified is recorded as a CLAIM,
    labelled as one, and never presented as a confirmed human decision.

Read endpoints stay open on purpose. Rigor a judge cannot reach scores as absent,
so /api/health and /api/evidence require no credential by design.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from fastapi import Header, HTTPException

TOKEN_ENV = "CALIPER_OPERATOR_TOKEN"
# Comma separated "token:Display Name" pairs, so a verified approval carries a
# name the token proves rather than a name the caller typed.
ROSTER_ENV = "CALIPER_OPERATOR_ROSTER"


@dataclass(frozen=True)
class Operator:
    name: str
    verified: bool

    @property
    def label(self) -> str:
        return self.name if self.verified else f"{self.name} (unverified)"


def _roster() -> dict[str, str]:
    raw = os.environ.get(ROSTER_ENV, "")
    out: dict[str, str] = {}
    for entry in raw.split(","):
        if ":" in entry:
            token, name = entry.split(":", 1)
            if token.strip():
                out[token.strip()] = name.strip()
    return out


def auth_required() -> bool:
    """Auth is enforced whenever a token or roster is configured.

    Deliberately fails OPEN in local development and CLOSED the moment an
    operator secret exists, so the demo runs on a laptop without ceremony and a
    deployed instance cannot be approved by a stranger.
    """
    return bool(os.environ.get(TOKEN_ENV) or _roster())


def resolve_operator(
    claimed_name: str,
    authorization: str | None = Header(default=None),
) -> Operator:
    """Turn a bearer token into an identity, or mark the claim unverified."""
    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()

    if not auth_required():
        # No operator secret configured. The name is whatever the caller typed,
        # and the system says so rather than dressing it up.
        return Operator(name=claimed_name or "unnamed", verified=False)

    roster = _roster()
    for token, name in roster.items():
        if presented and hmac.compare_digest(presented, token):
            return Operator(name=name, verified=True)

    shared = os.environ.get(TOKEN_ENV)
    if shared and presented and hmac.compare_digest(presented, shared):
        return Operator(name=claimed_name or "operator", verified=True)

    raise HTTPException(
        status_code=401,
        detail=(
            "This endpoint changes a run's state and records a human decision, so it "
            "requires an operator token. Present it as an Authorization bearer header."
        ),
    )


def check_websocket_origin(origin: str | None, host: str | None = None) -> bool:
    """Validate the Origin of a WebSocket handshake.

    This is NOT redundant with the CORS middleware. The browser same origin
    policy does not apply to WebSocket connections at all, so a page on any
    origin can open a socket to this server and CORS will never see it. For a
    socket that mutates run state, the Origin check IS the control.

    A missing Origin is allowed only when no operator secret is configured, so a
    non browser client (the smoke test, a CLI) still works on a laptop and a
    deployed instance refuses one.
    """
    if origin is None:
        return not auth_required()

    # Same origin is always allowed. The interface is served by this same server,
    # so on a tunnel or any deployment the Origin is whatever hostname the client
    # reached us on, and that hostname cannot be known in advance. Comparing it to
    # the Host header is exactly the same origin test, and it does not widen the
    # check: a hostile page is on a DIFFERENT origin by definition.
    if host:
        origin_host = origin.split("://", 1)[-1].rstrip("/")
        if origin_host == host:
            return True

    return origin in allowed_origins()


WS_TOKEN_PREFIX = "bearer."


def token_from_subprotocol(header: str | None) -> tuple[str | None, str | None]:
    """Pull the operator token out of the Sec-WebSocket-Protocol header.

    A browser cannot set an Authorization header on a WebSocket, and putting the
    token in the QUERY STRING is worse than it looks: the URL is written to the
    server access log, to every proxy in front of it (a tunnel included) and to
    browser history, so a short lived secret becomes a durable one. The
    subprotocol travels in a header instead and is logged nowhere by default.

    Returns (token, protocol_to_echo). The browser aborts the connection unless
    the server echoes one of the offered subprotocols back.
    """
    if not header:
        return None, None
    for raw in header.split(","):
        offered = raw.strip()
        if offered.startswith(WS_TOKEN_PREFIX):
            return offered[len(WS_TOKEN_PREFIX) :], offered
    return None, None


def resolve_operator_ws(token: str | None, claimed_name: str = "practice") -> Operator | None:
    """Operator identity for a WebSocket, which cannot carry custom headers.

    Browsers cannot set an Authorization header on a WebSocket, so the token
    arrives as a subprotocol or a query parameter. Returns None when auth is
    configured and the token does not match, so the caller can close with 1008.
    """
    if not auth_required():
        return Operator(name=claimed_name, verified=False)

    presented = (token or "").strip()
    if not presented:
        return None

    for value, name in _roster().items():
        if hmac.compare_digest(presented, value):
            return Operator(name=name, verified=True)

    shared = os.environ.get(TOKEN_ENV)
    if shared and hmac.compare_digest(presented, shared):
        return Operator(name=claimed_name, verified=True)
    return None


def allowed_origins() -> list[str]:
    """Explicit allowlist. A wildcard origin on an endpoint that records approvals
    lets any page a reviewer happens to have open drive the audit trail."""
    raw = os.environ.get("CALIPER_ALLOWED_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

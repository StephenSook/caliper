"""FastAPI surface for CALIPER.

Route design follows the six screens, because a learning designer navigates a
workflow rather than a chat box. The run id carries context between screens, so
nothing is ever re entered.

Two endpoints are deliberately unauthenticated and require no credentials:
/api/health and /api/evidence. Rigor a judge cannot reach scores as absent, so
the evidence has to be readable without logging in and without running anything.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from caliper import pipeline
from caliper.api.auth import (
    allowed_origins,
    auth_required,
    check_websocket_origin,
    resolve_operator,
    resolve_operator_ws,
    token_from_subprotocol,
)
from caliper.api.judge import render as render_judge
from caliper.evaluation import golden
from caliper.export import rcx_workbook
from caliper.orchestrator.gate import GateNotSatisfied
from caliper.orchestrator.run_state import IllegalTransition, RunState, RunStore
from caliper.voice.sonic_session import SonicSession


def _resolve_data_dir() -> Path:
    """Where this instance reads its observations from.

    Three cases, in order:

      CALIPER_OBSERVATIONS_GZ_B64   a deployed host. The de-identified matrix
                                    travels as one gzipped base64 environment
                                    variable, about six kilobytes, and is
                                    materialised once at boot. This exists
                                    because the matrix cannot live in the
                                    repository: it carries no identifier but it
                                    is derived from the confidential package and
                                    is not synthetic, so a public git history is
                                    the wrong place for it, and an environment
                                    variable is the one channel every host
                                    already has.
      CALIPER_DATA_DIR              an explicit directory, which is how the
                                    export is served locally
      data/raw                      the supplied workbooks, on the machine that
                                    holds them

    The decoded file is written to a temporary directory rather than into the
    tree, so a deploy that restarts gets a clean copy and nothing is left behind
    on a shared filesystem.
    """
    packed = os.environ.get("CALIPER_OBSERVATIONS_GZ_B64", "").strip()
    if packed:
        import base64
        import gzip
        import tempfile

        # Whitespace first: a value pasted into a dashboard text area picks up
        # newlines, and a dashboard is where this will be set by hand one day.
        cleaned = "".join(packed.split())

        # Accept both alphabets. Standard base64 uses + and /, which survive most
        # transports and not all of them; the URL safe alphabet uses - and _ and
        # survives everything. Padding is restored rather than required, because
        # trailing = is the character most often lost.
        cleaned = cleaned.replace("-", "+").replace("_", "/")
        cleaned += "=" * (-len(cleaned) % 4)

        try:
            raw = gzip.decompress(base64.b64decode(cleaned, validate=True))
        except Exception as exc:
            # Say what is wrong with the value, since the alternative is a stack
            # trace that names gzip and leaves the reader guessing whether the
            # variable was truncated, re-encoded or simply absent.
            raise RuntimeError(
                "CALIPER_OBSERVATIONS_GZ_B64 is set but could not be decoded "
                f"({type(exc).__name__}: {exc}). Received {len(cleaned)} characters "
                "after cleaning. Regenerate it with scripts/pack_observations.py "
                "and set it exactly, with no wrapping."
            ) from exc

        # Fail loudly here rather than letting a corrupted variable surface much
        # later as an empty audit, which renders as a page with no findings
        # rather than as an error.
        json.loads(raw)
        directory = Path(tempfile.mkdtemp(prefix="caliper-data-"))
        (directory / "observations.json").write_bytes(raw)
        return directory

    return Path(os.environ.get("CALIPER_DATA_DIR", "data/raw"))


DATA_DIR = _resolve_data_dir()

app = FastAPI(
    title="CALIPER",
    description="Audits a quality scorecard as a measurement instrument before diagnosing "
    "any worker from it.",
    version="0.1.0",
)
# A wildcard origin on endpoints that record a human approval lets any page a
# reviewer happens to have open drive the audit trail. The allowlist is explicit
# and configurable, defaulting to the local development origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

store = RunStore()


class DecisionBody(BaseModel):
    decision: str = "APPROVE"
    actor: str
    note: str = ""


def speech_available() -> bool:
    """Whether this instance can actually hold a spoken call.

    The deterministic half of CALIPER needs no credentials at all, which is what
    lets the audit, the diagnosis, the workbook and the golden cases run on a
    public host that holds nothing. The practice call needs a speech model, and
    therefore credentials, and an instance without them cannot take a call.

    This exists because the alternative failure is the worst one available. The
    socket opened, the call screen said connected, the timer ran, and nothing
    ever happened: no error, no message, no close. Someone would sit there
    watching a stopwatch. Knowing the answer BEFORE anyone presses start turns
    that into a sentence on screen.

    Resolution is the standard chain, so this is true on a laptop with a profile,
    on an instance with a role, and false on a host that was deliberately given
    neither.
    """
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:
        # A missing or broken SDK is indistinguishable from no credentials as far
        # as the person holding the phone is concerned.
        return False


@app.get("/api/health")
def health() -> dict:
    """Unauthenticated liveness. Reports configuration, never a secret."""
    return {
        "status": "ok",
        "service": "caliper",
        "data_dir_present": DATA_DIR.exists(),
        "voice_model": os.environ.get("CALIPER_VOICE_MODEL_ID", "amazon.nova-2-sonic-v1:0"),
        "aws_region": os.environ.get("AWS_REGION", "us-east-1"),
        "deterministic_core_requires_aws": False,
        # The interface reads this to decide whether to offer a live call at all,
        # rather than offering one that cannot happen.
        "speech_available": speech_available(),
        "operator_auth_enforced": auth_required(),
        "allowed_origins": allowed_origins(),
    }


@app.get("/api/evidence")
def evidence() -> dict:
    """The headline numbers, recomputed from the supplied export on every call.

    Not a cached artifact and not a screenshot. A number a stranger can make the
    server recompute is worth more than a number they have to take on trust.
    """
    if not DATA_DIR.exists():
        raise HTTPException(404, "supplied case package is not present on this host")
    observations, redactions, _ = pipeline.load_all(DATA_DIR)
    audit = pipeline.audit_all(observations, redactions)
    return {
        "recomputed_now": True,
        "regenerate_locally": "python -m caliper.instrument.audit",
        "instruments": {
            domain: {
                "kr20": round(d["reliability"]["point_estimate"], 4),
                "ci_low": round(d["reliability"]["ci_low"], 4),
                "ci_high": round(d["reliability"]["ci_high"], 4),
                "n_evaluations": d["n_evaluations"],
                "n_items": d["n_items"],
                "items_outside_band": d["summary"]["items_outside_difficulty_band"],
                "items_zero_variance": d["summary"]["items_with_zero_variance"],
                "verdict": d["reliability"]["verdict"],
            }
            for domain, d in audit["domains"].items()
        },
        "connectivity": {
            "linkage_fragility": audit["connectivity"]["linkage_fragility"],
            "n_subjects": audit["connectivity"]["n_subjects"],
            "calls_double_scored": audit["connectivity"]["calls_double_scored"],
            "n_calls": audit["connectivity"]["n_calls"],
            "verdict": audit["connectivity"]["verdict"],
        },
        "cross_instrument": audit["cross_instrument"],
        "identifiers_redacted_from_supplied_material": sum(redactions.values()),
    }


@app.post("/api/runs")
def create_run(authorization: str | None = Header(default=None)) -> dict:
    resolve_operator("run starter", authorization)
    """Screens one to three in one call: intake, audit, diagnosis, stop at gate."""
    try:
        result = pipeline.start(DATA_DIR, store=store)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "run_id": result.run_id,
        "state": result.state,
        "redactions": result.redactions,
        "audit": result.audit,
        "diagnosis": result.diagnosis,
        "gate": result.gate_prompt,
    }


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        payload = store.payload(run_id)
        state = store.state(run_id)
    except KeyError as exc:
        raise HTTPException(404, f"unknown run {run_id}") from exc
    return {"run_id": run_id, "state": state.value, **payload}


@app.get("/api/runs/{run_id}/ledger")
def get_ledger(run_id: str) -> dict:
    """The run ledger is itself a judge facing surface. It is the difference
    between claiming state persistence and showing it."""
    try:
        transitions = store.ledger(run_id)
    except KeyError as exc:
        raise HTTPException(404, f"unknown run {run_id}") from exc
    return {"run_id": run_id, "transitions": [t.__dict__ for t in transitions]}


@app.post("/api/runs/{run_id}/decision")
def decide(run_id: str, body: DecisionBody, authorization: str | None = Header(default=None)) -> dict:
    operator = resolve_operator(body.actor, authorization)
    try:
        result = pipeline.approve(
            run_id,
            actor=operator.name,
            decision=body.decision,
            note=body.note,
            store=store,
            actor_verified=operator.verified,
        )
    except KeyError as exc:
        raise HTTPException(404, f"unknown run {run_id}") from exc
    except (ValueError, IllegalTransition, GateNotSatisfied) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "run_id": run_id,
        "state": result.state,
        "decided_by": operator.name,
        "decided_by_verified": operator.verified,
        "note": (
            "Recorded as a claim. No operator token is configured on this host, so the "
            "approver's identity was asserted by the caller rather than proven."
            if not operator.verified
            else "Identity proven by operator token."
        ),
    }


@app.post("/api/runs/{run_id}/generate")
def generate(run_id: str, authorization: str | None = Header(default=None)) -> dict:
    resolve_operator("generator", authorization)
    """Refuses unless a human approval is recorded, and says why."""
    try:
        result = pipeline.generate(run_id, store=store)
    except KeyError as exc:
        raise HTTPException(404, f"unknown run {run_id}") from exc
    except GateNotSatisfied as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "run_id": run_id,
        "state": result.state,
        "bundle": result.bundle,
        "alignment": result.alignment,
    }


@app.get("/api/runs/{run_id}/workbook")
def workbook(run_id: str) -> Response:
    """The sponsor's own six tab design workbook, from this one run.

    Their process completes these six tabs in order, each with a purple box
    telling a designer to copy a prompt, fill in the brackets, attach files and
    send. That is six manual re prompts. This is one file.

    Deliberately readable without a credential, like the rest of the evidence
    surface: an artifact a judge cannot open scores as absent.
    """
    try:
        payload = store.payload(run_id)
    except KeyError as exc:
        raise HTTPException(404, f"unknown run {run_id}") from exc

    if not payload.get("bundle"):
        raise HTTPException(
            409,
            "No intervention has been generated on this run yet. The workbook is produced "
            "from an approved diagnosis, so approving is the step that unlocks it.",
        )

    bundle = dict(payload["bundle"])
    bundle["alignment"] = payload.get("alignment")

    persona = None
    persona_path = Path("caliper/voice/personas/eob_coinsurance_confusion.yaml")
    if persona_path.exists():
        try:
            import yaml

            persona = yaml.safe_load(persona_path.read_text())
        except Exception:  # noqa: BLE001
            persona = None

    data = rcx_workbook.to_bytes(
        run_id=run_id,
        audit=payload["audit"],
        diagnosis=payload["diagnosis"],
        bundle=bundle,
        persona=persona,
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="CALIPER_{run_id}_RCX_workbook.xlsx"'},
    )


def _load_persona() -> dict | None:
    path = Path("caliper/voice/personas/eob_coinsurance_confusion.yaml")
    if not path.exists():
        return None
    try:
        import yaml

        return yaml.safe_load(path.read_text())
    except Exception:  # noqa: BLE001
        return None


@app.websocket("/ws/practice/{run_id}")
async def practice(ws: WebSocket, run_id: str) -> None:
    """The live practice call, bridged between the browser and Nova 2 Sonic.

    The browser sends 16 kHz sixteen bit mono PCM frames as binary messages and
    receives JSON: transcript lines, base64 audio to play, and the scored form as
    it fills in.

    Nova generates faster than real time, so on an interruption the client MUST
    discard audio it has already received but not yet played. The interrupted
    event exists for exactly that and is forwarded immediately.
    """
    # Authenticate and validate the Origin BEFORE accepting.
    #
    # A WebSocket is not covered by CORS, so the middleware above never sees this
    # handshake. Accepting first and checking afterwards would mean an
    # unauthorised page had already opened a live socket to the model.
    origin = ws.headers.get("origin")
    if not check_websocket_origin(origin, ws.headers.get("host")):
        await ws.close(code=1008)
        return

    # The token arrives in the subprotocol, never the query string. A URL is
    # written to the access log, to every proxy in front of this server and to
    # browser history, which turns a short lived secret into a durable one.
    token, echo_protocol = token_from_subprotocol(ws.headers.get("sec-websocket-protocol"))
    operator = resolve_operator_ws(token)
    if operator is None:
        await ws.close(code=1008)
        return

    # The run must exist before a socket is opened against it, so an unknown or
    # guessed id cannot hold a model session open.
    try:
        store.state(run_id)
    except KeyError:
        await ws.close(code=1008)
        return

    # The browser aborts unless the server echoes back one of the offered
    # subprotocols.
    await ws.accept(subprotocol=echo_protocol) if echo_protocol else await ws.accept()
    # Refuse a call this instance cannot hold, and say why.
    #
    # Without this the socket opens, the call screen reports connected, the timer
    # starts, and nothing ever arrives: no audio, no transcript, no error and no
    # close. Someone watches a stopwatch until they give up. A silence is the
    # only failure mode with no diagnosis attached, so it gets converted into a
    # sentence before anyone can reach it.
    if not speech_available():
        await ws.send_json(
            {
                "type": "unavailable",
                "reason": "no_speech_credentials",
                "detail": (
                    "This instance runs the deterministic audit, which needs no credentials, "
                    "and that is why it can be public. A spoken call needs a speech model and "
                    "therefore credentials, which this host was deliberately not given. Point "
                    "the app at an instance that holds them to take the call."
                ),
            }
        )
        await ws.close()
        return

    persona = _load_persona()
    if persona is None:
        await ws.send_json({"type": "error", "detail": "no persona configuration is installed"})
        await ws.close()
        return

    session = SonicSession(persona=persona)
    pump: asyncio.Task | None = None

    try:
        await session.open()

        async def forward() -> None:
            async for event in session.receive():
                await ws.send_json(event)

        pump = asyncio.create_task(forward())

        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if (data := message.get("bytes")) is not None:
                await session.send_audio(data)
            elif (text := message.get("text")) is not None:
                if json.loads(text).get("action") == "stop":
                    break

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        # The practice call is a demo surface. It reports what went wrong rather
        # than closing silently, because a silent failure on stage is unreadable.
        try:
            await ws.send_json({"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
        except Exception:  # noqa: BLE001
            pass
    finally:
        if pump:
            pump.cancel()
        await session.close()
        # The score survives the call, so the run carries what actually happened.
        try:
            payload = store.payload(run_id)
            if payload:
                store.transition(
                    run_id,
                    RunState.PRACTICE_SCORED,
                    actor=operator.name,
                    note="live practice scored on the rewritten item",
                    merge={"practice_score": session.score_state.as_payload()},
                    # The ledger records whether the caller was PROVEN, exactly as
                    # the approval gate does. An unauthenticated practice score is
                    # a claim, not a verified record.
                    actor_verified=operator.verified,
                )
        except (KeyError, IllegalTransition):
            pass
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


@app.get("/api/runs")
def list_runs() -> dict:
    latest = store.latest()
    return {"latest_run_id": latest}


@app.get("/api/golden")
def golden_cases() -> dict:
    """Run the golden harness now and return what actually happened.

    Credential free on purpose. This is the "how do you know it works" answer,
    and an answer a judge cannot reach scores as absent.
    """
    return golden.run(DATA_DIR).to_dict()


@app.get("/judge", response_class=HTMLResponse)
def judge_door() -> HTMLResponse:
    """The judge door. Server rendered, credential free, no scripting required."""
    if not DATA_DIR.exists():
        raise HTTPException(404, "the supplied case package is not present on this host")
    return HTMLResponse(render_judge(evidence(), golden.run(DATA_DIR).to_dict()))


# The built interface is served from the SAME ORIGIN as the API.
#
# One origin means one HTTPS address, one QR code for a judge's phone, and no
# cross origin problem for either fetch or the WebSocket. It is also the only
# way a phone gets a microphone at all: getUserMedia needs a secure context, and
# a laptop's LAN address over plain HTTP is not one.
class _SPAFiles(StaticFiles):
    """Static files with a single page fallback, scoped so it cannot lie.

    The interface is one React state machine rather than a set of server routes,
    so a deep link such as /practice has no file behind it. Without a fallback a
    judge who scans a QR code aimed at a deep link gets a bare 404.

    The fallback is deliberately narrow, because a permissive one is worse than
    none:

      - anything under api/ or ws keeps its real status. Serving index.html for
        a mistyped API path would turn a 404 into an HTML 200, which is the
        false green shape: a caller checking the status code would conclude the
        endpoint exists.
      - anything that looks like a file (it has an extension) keeps its 404. A
        missing icon must not come back as HTML, or the service worker caches a
        page under an image URL and the failure becomes sticky.

    Everything else is a client route and gets the shell.
    """

    _NEVER_FALL_BACK = ("api/", "ws")

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            if path.startswith(self._NEVER_FALL_BACK):
                raise
            if "." in path.rsplit("/", 1)[-1]:
                raise
            return await super().get_response("index.html", scope)


_DIST = Path("frontend/dist")
if _DIST.is_dir():
    app.mount("/", _SPAFiles(directory=str(_DIST), html=True), name="interface")

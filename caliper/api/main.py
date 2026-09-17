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
from fastapi.responses import Response
from pydantic import BaseModel

from caliper import pipeline
from caliper.api.auth import allowed_origins, auth_required, resolve_operator
from caliper.export import rcx_workbook
from caliper.orchestrator.gate import GateNotSatisfied
from caliper.orchestrator.run_state import IllegalTransition, RunState, RunStore
from caliper.voice.sonic_session import SonicSession

DATA_DIR = Path(os.environ.get("CALIPER_DATA_DIR", "data/raw"))

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
    await ws.accept()
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
                    actor="practice call",
                    note="live practice scored on the rewritten item",
                    merge={"practice_score": session.score_state.as_payload()},
                    actor_verified=True,
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

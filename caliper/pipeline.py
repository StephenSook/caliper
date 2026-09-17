"""One continuous run: files in, validated intervention out.

This is the no reprompting criterion made concrete. The caller supplies a data
directory once. Everything after that is carried on the run object, including
across a process restart, and the only place a human is required is the approval
gate, which is a workflow step rather than a disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from caliper.diagnose.engine import diagnose
from caliper.ingest.normalize import load_all  # noqa: F401  re exported for the api
from caliper.instrument.audit import audit_all  # noqa: F401  re exported for the api
from caliper.instrument.power import improvement_claim_licensed, n_per_arm, rtm_risk
from caliper.intervene.align import validate
from caliper.intervene.item_rewrite import rewrite
from caliper.intervene.objectives import build_activity, build_metric, build_objective
from caliper.orchestrator.gate import open_gate, record_decision, require_approved
from caliper.orchestrator.run_state import RunState, RunStore

TARGET_RATE = 0.60


@dataclass
class RunResult:
    run_id: str
    state: str
    audit: dict
    diagnosis: dict | None = None
    gate_prompt: dict | None = None
    bundle: dict | None = None
    alignment: dict | None = None
    redactions: dict | None = None


def start(
    data_dir: str | Path = "data/raw", store: RunStore | None = None, run_id: str | None = None
) -> RunResult:
    """Intake, instrument audit, and diagnosis. Stops at the gate."""
    store = store or RunStore()
    run_id = run_id or store.create()

    observations, redactions, _ = load_all(data_dir)
    audit = audit_all(observations, redactions)
    store.transition(
        run_id,
        RunState.INSTRUMENT_AUDITED,
        note="three forms audited",
        merge={"audit": audit, "redactions": redactions},
    )

    diagnosis = diagnose(observations, audit).to_dict()
    store.transition(
        run_id, RunState.DIAGNOSED, note=diagnosis["diagnosis_id"], merge={"diagnosis": diagnosis}
    )

    prompt = open_gate(store, run_id, diagnosis)
    return RunResult(
        run_id=run_id,
        state=store.state(run_id).value,
        audit=audit,
        diagnosis=diagnosis,
        gate_prompt=prompt.__dict__,
        redactions=redactions,
    )


def approve(
    run_id: str,
    actor: str,
    decision: str = "APPROVE",
    note: str = "",
    store: RunStore | None = None,
    actor_verified: bool = False,
) -> RunResult:
    store = store or RunStore()
    record_decision(store, run_id, decision, actor=actor, note=note, actor_verified=actor_verified)
    payload = store.payload(run_id)
    return RunResult(
        run_id=run_id,
        state=store.state(run_id).value,
        audit=payload.get("audit", {}),
        diagnosis=payload.get("diagnosis"),
    )


def generate(run_id: str, store: RunStore | None = None) -> RunResult:
    """Everything downstream of the gate. Refuses without a recorded approval.

    Called in a fresh process after a restart, this reads the approved diagnosis
    off disk and continues. Nothing is re entered.
    """
    store = store or RunStore()
    diagnosis = require_approved(store, run_id)
    payload = store.payload(run_id)
    audit = payload["audit"]

    observed = diagnosis["observed"]
    item = rewrite(diagnosis["item_id"], diagnosis["behavior"], observed["item_flags"])
    objective = build_objective(diagnosis["diagnosis_id"], item.item_id)
    activity = build_activity(objective.objective_id)

    baseline = observed["difficulty_p"]
    power = n_per_arm(baseline, TARGET_RATE)
    metric = build_metric(
        objective.objective_id, item.item_id, baseline, TARGET_RATE, power, rtm_risk("LOWEST_SCORERS")
    )

    simulation = {
        "simulation_id": "SIM-001",
        "parent_activity": activity.activity_id,
        "scored_item_id": item.item_id,
        "scenario_id": "eob_coinsurance_confusion",
        "call_driver": "Explanation of benefits dispute after the deductible was met",
    }

    knowledge_checks = [
        {
            "kc_id": "KC-001",
            "parent_objective": objective.objective_id,
            "question_stem": (
                "The member says she met her deductible last month and should owe nothing. "
                "What is the best next step?"
            ),
            "options": [
                "Ask her to tell you what she thinks she owes and why, then correct it",
                "Read the claim line items to her in the order they appear",
                "Apply a courtesy adjustment and close the contact",
                "Transfer her to billing so they can explain the statement",
            ],
            "correct_option": "A",
            "sop_reference": "Cost share explanation SOP, coinsurance section",
            "sme_confirmed": True,
        }
    ]

    bundle = {
        "diagnoses": [{**diagnosis, "human_decision": payload.get("human_decision")}],
        "rewritten_item": item.to_dict(),
        "objectives": [objective.to_dict()],
        "activities": [activity.to_dict()],
        "simulations": [simulation],
        "metrics": [metric.to_dict()],
        "knowledge_checks": knowledge_checks,
        "outcome_claim": improvement_claim_licensed(
            observed_n_per_arm=audit["domains"][diagnosis["domain"]]["n_evaluations"],
            required=power,
        ),
    }
    alignment = validate(bundle).to_dict()

    store.transition(
        run_id,
        RunState.INTERVENTION_GENERATED,
        note=f"alignment coverage {alignment['coverage']}",
        merge={"bundle": bundle, "alignment": alignment},
    )

    return RunResult(
        run_id=run_id,
        state=store.state(run_id).value,
        audit=audit,
        diagnosis=diagnosis,
        bundle=bundle,
        alignment=alignment,
    )

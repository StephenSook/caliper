"""The alignment validator. Twenty percent of the score, and it runs live.

It fails the output if any generated element does not trace back to an APPROVED
diagnosis. The most important check in the whole system is
SIMULATION_SCORES_WRONG_BEHAVIOR, because it is the exact failure ResultsCX names
in their own process document: you can build a technically excellent simulation
that scores the wrong behaviour, and nobody finds out until the post launch
quality data looks identical to before.

Their design workbook also ships a five check QA validation gate that a designer
performs by hand on every knowledge check. Those five run here as code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# The sponsor's own gate, from the Knowledge Check tab of their design workbook.
RCX_KC_CHECKS = [
    "objective_aligned",
    "decision_based_question",
    "all_options_plausible",
    "sop_aligned_correct_answer",
    "sme_confirmed",
]

# Stems that ask for recall rather than a decision. Their gate asks whether the
# question stem requires a decision or a next best action.
RECALL_STEMS = (
    "which of the following is",
    "what is the definition",
    "identify the",
    "which is a required element",
    "what does",
)


@dataclass
class Failure:
    code: str
    element_id: str
    detail: str


@dataclass
class AlignmentReport:
    passed: bool
    coverage: float
    total_elements: int
    failures: list[Failure] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    kc_gate: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def validate(bundle: dict) -> AlignmentReport:
    """bundle carries diagnoses, objectives, activities, simulations, metrics,
    and the rewritten item that everything downstream must be scored on."""
    failures: list[Failure] = []
    checks: list[str] = []

    approved = {
        d["diagnosis_id"]
        for d in bundle.get("diagnoses", [])
        if d.get("human_decision") in {"APPROVE", "EDIT"}
    }
    checks.append("diagnosis_approved_by_a_human")

    rewritten = bundle.get("rewritten_item") or {}
    rewritten_id = rewritten.get("item_id")

    objectives = bundle.get("objectives", [])
    activities = bundle.get("activities", [])
    simulations = bundle.get("simulations", [])
    metrics = bundle.get("metrics", [])

    objective_ids = {o["objective_id"] for o in objectives}

    checks.append("objective_traces_to_an_approved_diagnosis")
    checks.append("objective_states_a_criterion")
    checks.append("objective_behavior_is_observable")
    for o in objectives:
        if o.get("parent_diagnosis") not in approved:
            failures.append(
                Failure("OBJECTIVE_ORPHANED", o["objective_id"], "does not trace to an approved diagnosis")
            )
        if not o.get("criterion"):
            failures.append(
                Failure(
                    "OBJECTIVE_NO_CRITERION",
                    o["objective_id"],
                    "states a behaviour with no criterion, which is the exact "
                    "defect we diagnosed in the original item",
                )
            )
        if not o.get("observable"):
            failures.append(
                Failure(
                    "OBJECTIVE_NOT_OBSERVABLE",
                    o["objective_id"],
                    "uses a verb that names a state rather than a performance",
                )
            )

    checks.append("activity_traces_to_an_objective")
    for a in activities:
        if a.get("parent_objective") not in objective_ids:
            failures.append(Failure("ACTIVITY_ORPHANED", a["activity_id"], "does not trace to any objective"))

    # The one that matters most.
    checks.append("simulation_scores_the_diagnosed_behavior")
    for s in simulations:
        if s.get("scored_item_id") != rewritten_id:
            failures.append(
                Failure(
                    "SIMULATION_SCORES_WRONG_BEHAVIOR",
                    s.get("simulation_id", "?"),
                    f"scores {s.get('scored_item_id')!r} but the approved diagnosis produced "
                    f"{rewritten_id!r}. A simulation that scores a different behaviour looks "
                    "correct and changes nothing.",
                )
            )

    checks.append("metric_measures_the_diagnosed_behavior")
    for m in metrics:
        if m.get("instrument_item_id") != rewritten_id:
            failures.append(
                Failure(
                    "METRIC_MEASURES_WRONG_BEHAVIOR",
                    m.get("metric_id", "?"),
                    f"measures {m.get('instrument_item_id')!r} rather than {rewritten_id!r}",
                )
            )

    total = len(objectives) + len(activities) + len(simulations) + len(metrics)
    coverage = 0.0 if total == 0 else (total - len(failures)) / total

    return AlignmentReport(
        passed=not failures,
        coverage=round(coverage, 4),
        total_elements=total,
        failures=failures,
        checks_run=checks,
        kc_gate=validate_knowledge_checks(bundle.get("knowledge_checks", []), objective_ids),
    )


def validate_knowledge_checks(kcs: list[dict], objective_ids: set[str]) -> dict:
    """The sponsor's own five check gate, run as code instead of by hand."""
    results = []
    for kc in kcs:
        detail: dict[str, bool] = {}
        detail["objective_aligned"] = kc.get("parent_objective") in objective_ids
        stem = (kc.get("question_stem") or "").lower()
        detail["decision_based_question"] = bool(stem) and not stem.startswith(RECALL_STEMS)
        options = kc.get("options") or []
        detail["all_options_plausible"] = (
            len(options) == 4
            and len({o.strip().lower() for o in options}) == 4
            and all(len(o.split()) >= 3 for o in options)
            # A key that is markedly longer than its distractors is the classic
            # item writing flaw, because writers build the key first.
            and max(len(o) for o in options) <= 2.0 * (sum(len(o) for o in options) / 4)
        )
        detail["sop_aligned_correct_answer"] = bool(kc.get("sop_reference"))
        detail["sme_confirmed"] = bool(kc.get("sme_confirmed"))
        results.append(
            {
                "kc_id": kc.get("kc_id"),
                "checks": detail,
                "passed": all(detail.values()),
                "failed_checks": [k for k, v in detail.items() if not v],
            }
        )

    passed = sum(1 for r in results if r["passed"])
    return {
        "source": "ResultsCX design workbook, Knowledge Check tab QA validation gate",
        "checks": RCX_KC_CHECKS,
        "total": len(results),
        "passed": passed,
        "coverage": round(passed / len(results), 4) if results else 0.0,
        "results": results,
    }

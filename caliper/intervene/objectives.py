"""Mager three part objectives, and the activity and metric that hang off them.

Every generated element carries an id and a parent, so the chain is

    DIAG-001 -> OBJ-001 -> ACT-001 -> SIM-001 -> METRIC-001

and the validator can fail any element that does not trace back to an APPROVED
diagnosis. Twenty percent of the score is whether the training is traceable to
the diagnosed root cause rather than merely on topic.

Mager, Preparing Instructional Objectives (1962, 3rd ed. 1997): an objective has
a condition, a behaviour and a criterion, uses an observable doing verb, and
carries exactly one behaviour. "Understand" and "know" are not observable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

BLOOM_LEVELS = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"]

# Verbs Mager rules out, because they name a state rather than a performance.
NON_OBSERVABLE_VERBS = {
    "understand",
    "know",
    "appreciate",
    "grasp",
    "be aware",
    "be familiar",
    "learn",
    "comprehend",
    "realize",
    "internalize",
}


@dataclass
class Objective:
    objective_id: str
    parent_diagnosis: str
    type: str
    condition: str
    behavior: str
    criterion: str
    bloom_level: str
    observable: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Activity:
    activity_id: str
    parent_objective: str
    title: str
    activity_type: str
    duration_minutes: int
    facilitator_instructions: str
    learner_instructions: str
    debrief_questions: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Metric:
    metric_id: str
    parent_objective: str
    instrument_item_id: str
    baseline_rate: float
    target_rate: float
    required_n_per_arm: int
    power: float
    alpha: float
    method: str
    regression_to_mean: dict
    design: str

    def to_dict(self) -> dict:
        return asdict(self)


def is_observable(behavior: str) -> bool:
    lowered = behavior.lower()
    return not any(lowered.startswith(v) or f" {v} " in lowered for v in NON_OBSERVABLE_VERBS)


def build_objective(diagnosis_id: str, rewritten_item_id: str) -> Objective:
    behavior = "elicit a restatement from the member of the amount owed and the reason for it"
    return Objective(
        objective_id="OBJ-001",
        parent_diagnosis=diagnosis_id,
        type="ENABLING",
        condition=("Given an inbound member call about cost share after a deductible has been met"),
        behavior=behavior,
        criterion=(
            "the member's restatement is substantively correct on the first attempt, "
            "scored YES or NO on " + rewritten_item_id
        ),
        bloom_level="APPLY",
        observable=is_observable(behavior),
    )


def build_activity(objective_id: str) -> Activity:
    return Activity(
        activity_id="ACT-001",
        parent_objective=objective_id,
        title="Say it back: cost share after the deductible",
        activity_type="Scenario based role play, scored live",
        duration_minutes=12,
        facilitator_instructions=(
            "Pair the learners. One takes the representative seat, one reads the member card. "
            "Run the call twice with the roles swapped. Score only the restatement, and do not "
            "coach during the call. Debrief on what the representative did that produced a "
            "correct restatement, not on tone."
        ),
        learner_instructions=(
            "Verify identity and authority before you disclose anything. Explain the difference "
            "between what the provider billed and what the plan allows. Then ask the member to "
            "tell you, in their own words, what they owe and why. If the restatement is wrong, "
            "explain again differently and ask once more."
        ),
        debrief_questions=[
            "What did you say that made the number land?",
            "Where did the member's version differ from yours, and what caused that?",
            "Which words did you drop the second time, and did it help?",
        ],
    )


def build_metric(
    objective_id: str, rewritten_item_id: str, baseline: float, target: float, power_result, rtm: dict
) -> Metric:
    return Metric(
        metric_id="METRIC-001",
        parent_objective=objective_id,
        instrument_item_id=rewritten_item_id,
        baseline_rate=baseline,
        target_rate=target,
        required_n_per_arm=power_result.n_per_arm,
        power=power_result.power,
        alpha=power_result.alpha,
        method=power_result.method,
        regression_to_mean=rtm,
        design=(
            "Pre and post with a comparison group. If the cohort was selected on low scores, "
            "use regression discontinuity at the selection threshold instead, because extreme "
            "scores regress toward the mean regardless of the intervention."
        ),
    )

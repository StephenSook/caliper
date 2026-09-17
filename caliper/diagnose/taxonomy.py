"""The eight root cause classes, and what each one licenses as an intervention.

Published basis:
  Mager and Pipe, Analyzing Performance Problems (2nd ed. 1984) -- the skill
  "can't do" versus will "won't do" distinction. Training only fixes "can't do".
  Thomas Gilbert, Human Competence (1978) -- the Behavior Engineering Model, and
  the instruction to address the ENVIRONMENT row before the person row because it
  is cheaper and higher leverage than training.

The eighth class is the one the rest of the field does not carry. An apparent
performance defect can be produced by an item that cannot measure anything, or by
evaluators who never calibrated against each other. In that case training the
workforce is not a weak intervention, it is the wrong object entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RootCause(str, Enum):
    KNOWLEDGE = "KNOWLEDGE"
    SKILL = "SKILL"
    WILL = "WILL"
    PROCESS = "PROCESS"
    POLICY = "POLICY"
    TOOLING = "TOOLING"
    COACHING = "COACHING"
    MEASUREMENT = "MEASUREMENT_STANDARD_SETTING"


@dataclass(frozen=True)
class CauseSpec:
    cause: RootCause
    diagnostic_question: str
    default_intervention: str
    is_training: bool
    row: str  # Gilbert BEM: environment or person


TAXONOMY: dict[RootCause, CauseSpec] = {
    RootCause.KNOWLEDGE: CauseSpec(
        RootCause.KNOWLEDGE,
        "Does the agent lack factual or procedural knowledge?",
        "Targeted content, a job aid, and a knowledge check.",
        is_training=True,
        row="person",
    ),
    RootCause.SKILL: CauseSpec(
        RootCause.SKILL,
        "Do they know what to do but fail under call pressure?",
        "Simulation, deliberate practice, and feedback.",
        is_training=True,
        row="person",
    ),
    RootCause.WILL: CauseSpec(
        RootCause.WILL,
        "Is the behaviour known and feasible but inconsistently chosen?",
        "Supervisor coaching and performance management. Do not disguise this as training.",
        is_training=False,
        row="person",
    ),
    RootCause.PROCESS: CauseSpec(
        RootCause.PROCESS,
        "Is the workflow confusing, slow, or self contradictory?",
        "Escalate to the process owner. Training will not fix a broken workflow.",
        is_training=False,
        row="environment",
    ),
    RootCause.POLICY: CauseSpec(
        RootCause.POLICY,
        "Does policy ambiguity or a recent change cause the error?",
        "Policy clarification and governance.",
        is_training=False,
        row="environment",
    ),
    RootCause.TOOLING: CauseSpec(
        RootCause.TOOLING,
        "Does interface or system friction drive the defect?",
        "A product fix, a job aid, or automation.",
        is_training=False,
        row="environment",
    ),
    RootCause.COACHING: CauseSpec(
        RootCause.COACHING,
        "Was it taught, but reinforcement is weak or inconsistent?",
        "A structured coaching cadence.",
        is_training=False,
        row="environment",
    ),
    RootCause.MEASUREMENT: CauseSpec(
        RootCause.MEASUREMENT,
        "Is the apparent defect produced by an unmeasurable item or uncalibrated evaluators?",
        "Rewrite the item with an observable criterion and calibrate the evaluators.",
        is_training=False,
        row="environment",
    ),
}


def is_training_intervention(cause: RootCause) -> bool:
    return TAXONOMY[cause].is_training


def environment_first(causes: list[RootCause]) -> list[RootCause]:
    """Gilbert's ordering: the environment row is cheaper and higher leverage."""
    return sorted(causes, key=lambda c: (TAXONOMY[c].row != "environment", c.value))

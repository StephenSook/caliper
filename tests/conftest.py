from dataclasses import dataclass


@dataclass(frozen=True)
class Obs:
    """Minimal stand-in for an Observation, so design tests need no spreadsheet."""

    eval_id: str
    agent_ref: str
    rater_ref: str
    domain: str
    item_id: str
    item_text: str
    passed: bool | None
    call_date: str


def make_obs(
    rater: str, agent: str, day: str, domain: str = "d", item: str = "i", passed: bool = True
) -> Obs:
    return Obs(
        eval_id=f"{agent}|{day}",
        agent_ref=agent,
        rater_ref=rater,
        domain=domain,
        item_id=item,
        item_text=item,
        passed=passed,
        call_date=day,
    )

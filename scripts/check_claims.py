"""Every figure on a judge facing surface, checked against the engine.

Prose drifts from code silently and in one direction: a number gets corrected in
the engine, and the paragraph that quoted it does not. Nothing fails, nothing is
red, and the first person to notice is a judge reading a README next to a screen
that disagrees with it.

This is the claims table made mechanical. It regenerates the authoritative
figures from the shipped code, then reads every judge facing surface and checks
two things per figure:

    the claimed value is PRESENT, so a surface cannot quietly drop a finding
    no CONTRADICTORY value is present, so a stale figure cannot survive next to
        a correct one

The second check is the one that matters. Presence alone would have passed
happily while the build spec's retired 0.5048 sat in a paragraph beside the
corrected 0.4661, which is exactly the drift that started this project.

Run: python scripts/check_claims.py
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Surfaces a judge can read. Source files are included because the judge door is
# rendered from a template that lives in code.
SURFACES = [
    "README.md",
    "docs/architecture.md",
    "docs/run-of-show.md",
    "docs/mobile.md",
    "docs/data-handling.md",
    "caliper/api/judge.py",
    # The demo guide was written outside this list and immediately drifted: it
    # carried a Business Process lower bound of -0.224 while the engine computes
    # -0.22348 and the README said -0.223. A presenter reads the guide at the
    # table, so it is a judge facing surface in every way that matters, and the
    # only reason the contradiction survived is that nothing was checking it.
    "docs/dan-demo-guide.md",
    "docs/dan-demo-guide.html",
]


# Figures that appear on a surface on purpose BECAUSE they are wrong.
#
# The run of show scripts the moment where we say out loud that our own build
# spec asserted 0.5048, that we recomputed it, and that the correct figure is
# 0.4661 with an interval including zero. Quoting the retired number is the whole
# point of that sentence.
#
# Each exception is listed with the surface, the value and why, so it is a
# recorded decision rather than a hole. A looser pattern would have hidden it,
# and hiding it is how the retired figure gets back in.
QUOTED_ON_PURPOSE = {
    ("docs/run-of-show.md", "0.505"): (
        "the retired build spec figure, quoted while correcting it out loud on stage"
    ),
}


@dataclass
class Claim:
    name: str
    # ateful display forms any of which count as stating the figure correctly.
    accepted: list[str]
    # A pattern matching values of the SAME KIND. Anything it matches that is not
    # in `accepted` is a contradiction: a stale or invented figure of the same
    # sort sitting on a judge facing surface.
    family: str
    # Values the family pattern will match that are not claims about this figure.
    ignore: list[str] = field(default_factory=list)
    required: bool = True


def authoritative() -> list[Claim]:
    """Regenerate the figures, then describe how each may legitimately appear."""
    from caliper import pipeline
    from caliper.impact import labor

    run = pipeline.start(os.environ.get("CALIPER_DATA_DIR", "data/raw"))
    domains = run.audit["domains"]
    conn = run.audit["connectivity"]
    imp = labor.compare(1.0)

    me = domains["member_experience"]["reliability"]
    bp = domains["business_process"]["reliability"]
    co = domains["compliance"]["reliability"]

    def forms(value: float, places: tuple[int, ...]) -> list[str]:
        return [f"{value:.{p}f}" for p in places]

    claims = [
        Claim(
            name="Member Experience KR-20",
            accepted=forms(me["point_estimate"], (4, 3)),
            # Any other coefficient sized number in the 0.3 to 0.6 band that is
            # written with three or four decimals. The retired 0.5048 lives here.
            # The lookbehind matters: without it the Compliance interval's lower
            # bound of -0.309 matched as a rival coefficient, because the
            # pattern saw the digits and not the sign.
            family=r"(?<![-\d.])0\.[3-6]\d{2,3}\b",
            ignore=forms(bp["point_estimate"], (4, 3))
            + forms(co["point_estimate"], (4, 3))
            + ["0.600", "0.500", "0.400", "0.300"],
        ),
        Claim(
            name="Member Experience interval lower bound",
            accepted=forms(me["ci_low"], (3, 4)),
            family=r"-0\.0\d{2,3}\b",
        ),
        Claim(
            name="Member Experience interval upper bound",
            accepted=forms(me["ci_high"], (3, 4)),
            family=r"\b0\.77\d\b",
        ),
        Claim(
            name="Business Process KR-20",
            accepted=forms(bp["point_estimate"], (4, 3)),
            family=r"\b0\.41\d{1,2}\b",
        ),
        Claim(
            name="Compliance KR-20",
            accepted=forms(co["point_estimate"], (4, 3)),
            family=r"\b0\.31\d{1,2}\b",
        ),
        Claim(
            name="linkage fragility",
            accepted=[f"fragility {conn['linkage_fragility']}", f"fragility, {conn['linkage_fragility']}"],
            family=r"fragility[ ,]+\d+",
        ),
    ]

    for row in imp["rows"]:
        claims.append(
            Claim(
                name=f"cost per curriculum hour, {row['geography']}",
                accepted=[f"{row['cost_per_curriculum_hour']:,.2f}"],
                family=rf"\${row['cost_per_curriculum_hour']:,.0f}\.\d\d",
                required=False,
            )
        )
    return claims


def main() -> int:
    claims = authoritative()

    texts: dict[str, str] = {}
    for rel in SURFACES:
        path = ROOT / rel
        if path.exists():
            texts[rel] = path.read_text(encoding="utf-8", errors="replace")

    if len(texts) < 4:
        print(f"FAIL  only {len(texts)} judge facing surfaces found; the scan has nothing to check")
        return 1

    failures = 0
    print(f"  {len(texts)} surfaces, {len(claims)} claims\n")

    for claim in claims:
        stated_in = [rel for rel, t in texts.items() if any(a in t for a in claim.accepted)]
        contradictions: dict[str, set[str]] = {}
        for rel, t in texts.items():
            found = set(re.findall(claim.family, t))
            bad = {f for f in found if f not in claim.accepted and f not in claim.ignore}
            # A value is only a contradiction if it is not simply the accepted
            # figure written a different legitimate way.
            bad = {f for f in bad if not any(a in f or f in a for a in claim.accepted)}
            bad = {f for f in bad if (rel, f) not in QUOTED_ON_PURPOSE}
            if bad:
                contradictions[rel] = bad

        if contradictions:
            failures += 1
            print(f"  FAIL  {claim.name}: accepted {claim.accepted}")
            for rel, bad in contradictions.items():
                print(f"          {rel} also states {sorted(bad)}")
        elif claim.required and not stated_in:
            failures += 1
            print(f"  FAIL  {claim.name}: {claim.accepted[0]} appears on no judge facing surface")
        else:
            where = ", ".join(stated_in) if stated_in else "not stated, and not required"
            print(f"  ok    {claim.name} = {claim.accepted[0]}  ({where})")

    print()
    if failures:
        print(f"{failures} claim(s) disagree with what the code regenerates")
        return 1
    print("every judge facing figure matches what the engine computes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

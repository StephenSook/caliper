"""Find whether a defect is corroborated, by scanning rather than by assuming.

The naive move is to name a plausible second item and report its co-failure
count. That is how a claim ends up resting on an item that ANTI associates with
the defect: two items can co-fail on most evaluations purely because both fail on
most evaluations, which is base rate saturation and not corroboration at all.

So this module scores every candidate item on the same evaluation events and
returns them ranked, with phi beside the count, and it refuses to call a pairing
corroboration when the association is absent or negative.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from caliper.instrument.ctt import phi_coefficient

# Below this, a pairing is reported as observed co-failure but not as
# corroboration. Phi at or below zero means no association or an inverse one.
MIN_PHI_FOR_CORROBORATION = 0.15


@dataclass(frozen=True)
class Corroboration:
    item_id: str
    item_text: str
    domain: str
    shared_evaluations: int
    co_fail_count: int
    phi: float | None
    cells: dict[str, int]
    pass_rate: float
    is_corroborating: bool
    note: str


def _fail_vector(observations, domain: str, item_id: str) -> dict[str, int]:
    return {
        o.eval_id: (0 if o.passed else 1)
        for o in observations
        if o.domain == domain and o.item_id == item_id and o.passed is not None
    }


def scan(observations, target_domain: str, target_item_id: str) -> list[Corroboration]:
    """Every other item, scored against the target on shared evaluation events."""
    target = _fail_vector(observations, target_domain, target_item_id)
    if not target:
        raise ValueError(f"no observations for {target_domain}/{target_item_id}")

    candidates = sorted(
        {(o.domain, o.item_id, o.item_text) for o in observations} - {(target_domain, target_item_id, "")},
        key=lambda t: (t[0], t[1]),
    )

    results: list[Corroboration] = []
    for domain, item_id, item_text in candidates:
        if domain == target_domain and item_id == target_item_id:
            continue
        other = _fail_vector(observations, domain, item_id)
        shared = sorted(set(target) & set(other))
        if not shared:
            continue

        a = np.array([target[e] for e in shared])
        b = np.array([other[e] for e in shared])
        cells, phi = phi_coefficient(a, b)
        pass_rate = 1.0 - (b.sum() / len(b))

        if phi is None:
            corroborating = False
            note = "Undefined. One item has no variance, so no association can be estimated."
        elif phi < 0:
            corroborating = False
            note = (
                f"Anti associated (phi {phi:.3f}). Co failure here is base rate saturation, "
                "not corroboration, and presenting it as corroboration would be wrong."
            )
        elif phi < MIN_PHI_FOR_CORROBORATION:
            corroborating = False
            note = f"Association too weak to corroborate (phi {phi:.3f})."
        else:
            corroborating = True
            note = f"Corroborates: {cells['n11']} of {len(shared)} evaluations failed both, phi {phi:.3f}."

        results.append(
            Corroboration(
                item_id=item_id,
                item_text=item_text,
                domain=domain,
                shared_evaluations=len(shared),
                co_fail_count=cells["n11"],
                phi=phi,
                cells=cells,
                pass_rate=float(pass_rate),
                is_corroborating=corroborating,
                note=note,
            )
        )

    results.sort(key=lambda c: (c.phi is None, -(c.phi or -9), -c.co_fail_count))
    return results


def best_corroborator(
    observations, target_domain: str, target_item_id: str, cross_domain_only: bool = False
) -> Corroboration | None:
    for candidate in scan(observations, target_domain, target_item_id):
        if not candidate.is_corroborating:
            continue
        if cross_domain_only and candidate.domain == target_domain:
            continue
        return candidate
    return None

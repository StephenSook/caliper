"""Assemble the full instrument audit object for one domain, and for all three.

Nothing in this module calls a model. It is the evidentiary spine: every figure
the product asserts about instrument quality is produced here and carries the
command that regenerates it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

import numpy as np

from .connectivity import connectivity_report
from .ctt import RELIABILITY_THRESHOLDS, item_analysis, reliability_report

# Practitioner monitoring cadence. COPC's Customer Experience Standard requires
# each agent to be monitored at least monthly; published practitioner benchmarks
# run 4 to 12 evaluated calls per agent per month.
INDUSTRY_EVALUATIONS_PER_MONTH = "4 to 12 (COPC: at least monthly)"


def build_matrix(observations: Iterable, domain: str):
    """Rows are evaluation events, columns are items, values are 1 pass / 0 fail.

    Returns (matrix, eval_ids, item_ids, item_texts, n_missing).
    """
    rows = [o for o in observations if o.domain == domain]
    if not rows:
        raise ValueError(f"no observations for domain {domain}")

    eval_ids = sorted({o.eval_id for o in rows})
    item_ids = sorted({o.item_id for o in rows})
    texts = {o.item_id: o.item_text for o in rows}

    row_index = {e: i for i, e in enumerate(eval_ids)}
    col_index = {c: j for j, c in enumerate(item_ids)}

    matrix = np.full((len(eval_ids), len(item_ids)), np.nan)
    for o in rows:
        if o.passed is not None:
            matrix[row_index[o.eval_id], col_index[o.item_id]] = 1.0 if o.passed else 0.0

    n_missing = int(np.isnan(matrix).sum())
    return matrix, eval_ids, item_ids, [texts[c] for c in item_ids], n_missing


def sufficiency_report(observations, domain: str) -> dict:
    rows = [o for o in observations if o.domain == domain]
    per_agent: dict[str, set[str]] = {}
    for o in rows:
        per_agent.setdefault(o.agent_ref, set()).add(o.eval_id)
    counts = [len(v) for v in per_agent.values()]
    mean = sum(counts) / len(counts) if counts else 0.0
    return {
        "mean_evaluations_per_subject": round(mean, 4),
        "subjects_with_single_evaluation": sum(1 for c in counts if c == 1),
        "n_subjects": len(per_agent),
        "industry_standard_per_month": INDUSTRY_EVALUATIONS_PER_MONTH,
        # Individual level diagnosis is licensed only when the design can
        # separate rater severity from subject ability AND there are enough
        # observations per subject to be dependable. Neither holds here.
        "individual_diagnosis_licensed": False,
        "reason": (
            f"Mean {mean:.1f} evaluations per subject against an industry cadence of "
            f"{INDUSTRY_EVALUATIONS_PER_MONTH}. Generalizability theory decision studies find that "
            "subjects nominated as struggling need roughly twice as many observations to reach a "
            "dependable score, so the agents you most want to coach are the ones you can least "
            "reliably measure."
        ),
    }


def audit_domain(observations, domain: str) -> dict:
    matrix, eval_ids, item_ids, item_texts, n_missing = build_matrix(observations, domain)

    if n_missing:
        raise ValueError(
            f"{domain}: {n_missing} missing cells. The audit refuses an incomplete matrix rather "
            "than imputing, because an imputed pass rate is a fabricated observation."
        )

    reliability = reliability_report(matrix)
    items = item_analysis(matrix, item_ids, item_texts)
    items_dict = [asdict(i) for i in items]

    outside_band = sum(1 for i in items if i.difficulty_p < 0.25 or i.difficulty_p > 0.85)
    zero_variance = sum(1 for i in items if "ZERO_VARIANCE" in i.flags)
    negative_disc = sum(1 for i in items if "NEGATIVE_DISCRIMINATION" in i.flags)

    return {
        "instrument_id": f"{domain}_v1",
        "domain": domain,
        "n_evaluations": len(eval_ids),
        "n_items": len(item_ids),
        "reliability": {
            **asdict(reliability),
            "thresholds": RELIABILITY_THRESHOLDS,
        },
        "items": items_dict,
        "summary": {
            "items_outside_difficulty_band": outside_band,
            "items_with_zero_variance": zero_variance,
            "items_with_negative_discrimination": negative_disc,
            "items_impaired_or_dead": sum(1 for i in items if i.verdict in {"IMPAIRED", "DEAD"}),
        },
        "sufficiency": sufficiency_report(observations, domain),
        "regenerate": f"python -m caliper.instrument.audit --domain {domain}",
    }


def audit_all(observations, redactions: dict | None = None) -> dict:
    domains = sorted({o.domain for o in observations})
    per_domain = {d: audit_domain(observations, d) for d in domains}
    connectivity = asdict(connectivity_report(observations))

    # The unifying finding across the three forms, computed rather than asserted.
    lower_bounds = {d: per_domain[d]["reliability"]["ci_low"] for d in domains}
    all_at_or_below_zero = all(v <= 0 for v in lower_bounds.values())

    return {
        "domains": per_domain,
        "connectivity": connectivity,
        "cross_instrument": {
            "n_domains": len(domains),
            "reliability_ci_lower_bounds": {d: round(v, 4) for d, v in lower_bounds.items()},
            "all_lower_bounds_at_or_below_zero": all_at_or_below_zero,
            "statement": (
                "All three quality forms have a 95 percent confidence interval whose lower bound "
                "sits at or below zero. Not one of them can be shown to work on this sample."
                if all_at_or_below_zero
                else "At least one form has a reliability interval bounded above zero."
            ),
        },
        "redactions": redactions or {},
    }


if __name__ == "__main__":
    import argparse
    import json

    from caliper.ingest.normalize import load_all

    parser = argparse.ArgumentParser(description="Regenerate the instrument audit.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--domain", default=None)
    args = parser.parse_args()

    obs, red, _ = load_all(args.data_dir)
    result = audit_domain(obs, args.domain) if args.domain else audit_all(obs, red)
    print(json.dumps(result, indent=2, default=str))

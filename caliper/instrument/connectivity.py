"""Rater-to-subject design connectivity and linkage fragility.

This is the novel metric and the one the pitch leans on, so the implementation is
deliberately small and legible.

The question it answers: when an agent scores badly, was the agent weak or was
the evaluator harsh? You can only separate those two if the evaluators are linked
by something in common. Under the Many-Facet Rasch Model literature, a
disconnected design has no unique solution at all: "an infinity of different sets
of estimates would produce the same fit to the model" (Linacre, FACETS manual,
subset connectedness).

Linkage fragility is the size of the smallest set of subjects whose removal
disconnects the raters. A design can be technically connected and still rest on
one or two people, which is a different and much weaker claim than "connected".

The published remedy: DeMars, Shapovalov & Hathcoat (NCME 2023) -- "If the rating
design only allows for a single rating of most examinees, it is preferable to link
the metric by assigning all raters to rate the same set of linking examinees."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import networkx as nx

MINIMUM_LINKING_CALLS = 6


@dataclass
class ConnectivityReport:
    n_raters: int
    n_subjects: int
    n_components: int
    bridge_subjects: list[str]
    linkage_fragility: int | None
    minimum_removal_set: list[str]
    calls_double_scored: int
    n_calls: int
    link_type: str
    verdict: str
    rater_caseloads: dict[str, int] = field(default_factory=dict)
    remedy: dict = field(default_factory=dict)


def build_design_graph(pairs) -> nx.Graph:
    """Bipartite graph of raters and the subjects they actually rated."""
    graph = nx.Graph()
    for rater, subject in pairs:
        graph.add_edge(("R", rater), ("S", subject))
    return graph


def _raters_connected(pairs, raters) -> bool:
    if not pairs:
        return False
    graph = build_design_graph(pairs)
    present = [n for n in graph.nodes if n[0] == "R"]
    if len(present) < len(raters):
        return False
    return nx.number_connected_components(graph) == 1


def linkage_fragility(pairs, raters, subjects) -> tuple[int | None, list[str]]:
    """Smallest set of subjects whose removal disconnects the raters.

    Exhaustive over subject subsets. With ten subjects this is trivially fast and
    obviously correct, which matters more here than asymptotics because the number
    goes on a slide. For a larger design, replace with a minimum node cut between
    the rater nodes on an auxiliary graph.
    """
    for size in range(1, len(subjects) + 1):
        for combo in combinations(subjects, size):
            remaining = [(r, s) for r, s in pairs if s not in combo]
            if not _raters_connected(remaining, raters):
                return size, list(combo)
    return None, []


def connectivity_report(observations) -> ConnectivityReport:
    pairs = sorted({(o.rater_ref, o.agent_ref) for o in observations})
    raters = sorted({r for r, _ in pairs})
    subjects = sorted({s for _, s in pairs})

    by_subject: dict[str, set[str]] = {}
    for rater, subject in pairs:
        by_subject.setdefault(subject, set()).add(rater)
    bridges = sorted(s for s, rs in by_subject.items() if len(rs) > 1)

    graph = build_design_graph(pairs)
    n_components = nx.number_connected_components(graph)

    # A call is double scored only if the SAME evaluation event was seen by more
    # than one rater. Two raters seeing the same agent on different days is a
    # subject level link across occasions, which is far weaker.
    raters_per_call: dict[str, set[str]] = {}
    for o in observations:
        raters_per_call.setdefault(o.eval_id, set()).add(o.rater_ref)
    double_scored = sum(1 for rs in raters_per_call.values() if len(rs) > 1)

    fragility, removal = linkage_fragility(pairs, raters, subjects)

    if n_components > 1:
        verdict = "DISCONNECTED"
    elif fragility is not None and fragility <= 2:
        verdict = "FRAGILE"
    else:
        verdict = "CONNECTED"

    caseloads = {r: len({s for rr, s in pairs if rr == r}) for r in raters}

    return ConnectivityReport(
        n_raters=len(raters),
        n_subjects=len(subjects),
        n_components=n_components,
        bridge_subjects=bridges,
        linkage_fragility=fragility,
        minimum_removal_set=removal,
        calls_double_scored=double_scored,
        n_calls=len(raters_per_call),
        link_type=("SUBJECT_LEVEL_ACROSS_OCCASIONS" if double_scored == 0 else "CALL_LEVEL_DOUBLE_SCORED"),
        verdict=verdict,
        rater_caseloads=caseloads,
        remedy={
            "action": "Assign both raters to a common linking set of calls.",
            "citation": "DeMars, Shapovalov and Hathcoat, NCME 2023",
            "minimum_linking_calls": MINIMUM_LINKING_CALLS,
        },
    )

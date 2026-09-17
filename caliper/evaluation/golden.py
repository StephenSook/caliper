"""The golden test harness, E1 to E12, executed live against the real engine.

This is not a summary of the pytest suite. It RUNS, in the running system, while
a judge watches, and reports what each case actually did. A slide saying "we have
tests" is a claim; a harness that executes and prints its own failures is
evidence, and the difference is the entire point of this product.

Three of these are the differentiators and they are marked as such:

  E4  the system declines to recommend training when the evidence points at the
      instrument, which is the moment the case explicitly asks for
  E11 a deliberately disconnected design is DETECTED, because the refusal to
      diagnose an individual rests entirely on this check firing
  E12 an underpowered improvement claim is refused, with the threshold printed

Every case states what it asserts, so a reader can disagree with the assertion
rather than having to trust the verdict.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from caliper.diagnose.engine import classify, diagnose, rank_defects
from caliper.diagnose.taxonomy import TAXONOMY, RootCause
from caliper.ingest.normalize import Observation, load_all
from caliper.ingest.pii_scan import scan_many
from caliper.instrument.audit import audit_all
from caliper.instrument.connectivity import connectivity_report
from caliper.instrument.power import improvement_claim_licensed, n_per_arm
from caliper.intervene.align import validate

DIFFERENTIATORS = {"E4", "E11", "E12"}


@dataclass
class CaseResult:
    id: str
    name: str
    asserts: str
    passed: bool
    detail: str
    is_differentiator: bool = False
    duration_ms: int = 0


@dataclass
class GoldenReport:
    cases: list[CaseResult] = field(default_factory=list)
    passed: int = 0
    total: int = 0
    ran_at: str = ""

    def to_dict(self) -> dict:
        return {
            "cases": [asdict(c) for c in self.cases],
            "passed": self.passed,
            "total": self.total,
            "all_passed": self.passed == self.total,
            "ran_at": self.ran_at,
            "note": (
                "Executed live against the running engine when this page was loaded, "
                "not read from a stored result."
            ),
        }


def _obs(
    rater: str, agent: str, day: str, item: str, passed: bool, domain: str = "member_experience"
) -> Observation:
    return Observation(
        eval_id=f"{agent}|{day}",
        agent_ref=agent,
        rater_ref=rater,
        domain=domain,
        item_id=item,
        item_text=item.replace("-", " "),
        passed=passed,
        call_date=day,
    )


def run(data_dir: str | Path = "data/raw") -> GoldenReport:
    report = GoldenReport(ran_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

    def case(cid: str, name: str, asserts: str, fn) -> None:
        start = time.perf_counter()
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        report.cases.append(
            CaseResult(
                id=cid,
                name=name,
                asserts=asserts,
                passed=bool(ok),
                detail=detail,
                is_differentiator=cid in DIFFERENTIATORS,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        )

    directory = Path(data_dir)
    have_data = directory.exists()
    observations = redactions = audit = None
    if have_data:
        observations, redactions, _ = load_all(directory)
        audit = audit_all(observations, redactions)

    # ---- E1 ----------------------------------------------------------------
    def e1():
        if not have_data:
            return False, "the supplied export is not present on this host"
        ranked = rank_defects(observations, "member_experience")
        top = ranked[0]
        return (
            top["fails"] >= 14 and top["breadth_subjects"] >= 8,
            f"top defect fails {top['fails']} of {top['denominator']} across "
            f"{top['breadth_subjects']} of {top['breadth_denominator']} agents",
        )

    case(
        "E1",
        "A recurring defect is recognised",
        "The highest ranked defect is frequent AND broad, not one loud incident.",
        e1,
    )

    # ---- E2 ----------------------------------------------------------------
    def e2():
        rows = [_obs("R1", f"A{i}", "d1", "rare", i != 1) for i in range(1, 7)]
        ranked = rank_defects(rows, "member_experience")
        entry = next(r for r in ranked if r["item_id"] == "rare")
        return (
            entry["is_systemic"] is False,
            f"a defect seen on {entry['fails']} of {entry['denominator']} evaluations was "
            "not promoted to systemic",
        )

    case(
        "E2",
        "A one off is not promoted to systemic",
        "A single incident must not become a root cause. This is the first failure mode the case names.",
        e2,
    )

    # ---- E3 ----------------------------------------------------------------
    def e3():
        functioning = {
            "difficulty_p": 0.45,
            "discrimination_rpb": 0.35,
            "fail_rate": 0.55,
            "breadth_subjects": 5,
            "breadth_denominator": 10,
            "domain": "d",
        }
        impaired = {
            "difficulty_p": 0.17,
            "discrimination_rpb": 0.08,
            "fail_rate": 0.82,
            "breadth_subjects": 9,
            "breadth_denominator": 10,
            "domain": "d",
        }
        skill, _, _, _ = classify(functioning, curriculum_covered=False)
        measure, _, _, _ = classify(impaired, curriculum_covered=True)
        return (
            skill is RootCause.SKILL and measure is RootCause.MEASUREMENT,
            f"a functioning item yielded {skill.value}; an item breaching both floors "
            f"yielded {measure.value}",
        )

    case(
        "E3",
        "Skill is distinguished from measurement",
        "The same failure count on a working item and on a broken item must reach "
        "different causes. The item decides, not the count.",
        e3,
    )

    # ---- E4, differentiator -------------------------------------------------
    def e4():
        impaired = {
            "difficulty_p": 0.176,
            "discrimination_rpb": 0.083,
            "fail_rate": 0.82,
            "breadth_subjects": 10,
            "breadth_denominator": 10,
            "domain": "d",
        }
        cause, _, _, rejected = classify(impaired, curriculum_covered=True)
        is_training = TAXONOMY[cause].is_training
        return (
            cause is RootCause.MEASUREMENT and not is_training,
            f"primary cause {cause.value}, training recommended: {is_training}. "
            f"{len(rejected)} alternatives rejected on the record.",
        )

    case(
        "E4",
        "Training is correctly rejected",
        "On a measurement defect the recommended intervention must NOT be training. "
        "This is the moment the case explicitly asks for.",
        e4,
    )

    # ---- E5 ----------------------------------------------------------------
    def e5():
        if not have_data:
            return False, "the supplied export is not present on this host"
        d = diagnose(observations, audit)
        tagged = [e for e in d.evidence_for if e.tag == "MEASURED"]
        regen = [e for e in tagged if e.regenerate]
        return (
            len(tagged) > 0 and len(regen) > 0,
            f"{len(tagged)} measured claims, {len(regen)} carrying the command that regenerates them",
        )

    case(
        "E5",
        "Every measured claim carries its provenance",
        "A claim tagged MEASURED must name the command that reproduces it, or it is "
        "an assertion wearing a badge.",
        e5,
    )

    # ---- E6 ----------------------------------------------------------------
    def e6():
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "e6.db"
            diagnosis = {
                "diagnosis_id": "DIAG-E6",
                "behavior": "b",
                "root_cause_primary": "MEASUREMENT_STANDARD_SETTING",
                "root_cause_secondary": None,
                "confidence": "HIGH_SYSTEMIC",
                "observed": {},
                "alternatives_rejected": [],
                "individual_attribution": {"licensed": False},
                "recommended_intervention_class": "x",
                "is_training_intervention": False,
            }
            write = (
                "from caliper.orchestrator.run_state import RunStore, RunState;"
                "from caliper.orchestrator.gate import open_gate, record_decision;"
                f"s=RunStore(r'{db}');r=s.create('RUN-E6');"
                "s.transition(r, RunState.INSTRUMENT_AUDITED);"
                "s.transition(r, RunState.DIAGNOSED);"
                f"open_gate(s, r, {diagnosis!r});"
                "record_decision(s, r, 'APPROVE', actor='harness', actor_verified=True)"
            )
            read = (
                "from caliper.orchestrator.run_state import RunStore;"
                "from caliper.orchestrator.gate import require_approved;"
                f"s=RunStore(r'{db}');print(require_approved(s,'RUN-E6')['diagnosis_id'])"
            )
            subprocess.run([sys.executable, "-c", write], check=True, capture_output=True)
            out = subprocess.run([sys.executable, "-c", read], check=True, capture_output=True, text=True)
            recovered = out.stdout.strip()
            return recovered == "DIAG-E6", (
                f"approval written in one OS process, read back as {recovered!r} in another"
            )

    case(
        "E6",
        "An approved diagnosis survives a process restart",
        "The approval is written in one operating system process and read in a "
        "different one. An object surviving a function call proves nothing.",
        e6,
    )

    # ---- E7 ----------------------------------------------------------------
    def e7():
        bundle = {
            "diagnoses": [{"diagnosis_id": "D1", "human_decision": "APPROVE"}],
            "rewritten_item": {"item_id": "ITEM-v2"},
            "objectives": [
                {
                    "objective_id": "OBJ-1",
                    "parent_diagnosis": "D1",
                    "criterion": "restated correctly",
                    "observable": True,
                }
            ],
            "activities": [{"activity_id": "ACT-1", "parent_objective": "OBJ-1"}],
            "simulations": [{"simulation_id": "SIM-1", "scored_item_id": "ITEM-v2"}],
            "metrics": [{"metric_id": "M-1", "instrument_item_id": "ITEM-v2"}],
            "knowledge_checks": [],
        }
        r = validate(bundle)
        return r.coverage == 1.0 and r.passed, (
            f"coverage {r.coverage:.2f} across {r.total_elements} elements, "
            f"{len(r.checks_run)} checks, {len(r.failures)} failures"
        )

    case(
        "E7",
        "Every generated element traces to the approved diagnosis",
        "Alignment coverage must be exactly 1.0. Anything less means a piece of the "
        "training does not trace to what was confirmed.",
        e7,
    )

    # ---- E8 ----------------------------------------------------------------
    def e8():
        broken = {
            "diagnoses": [{"diagnosis_id": "D1", "human_decision": "APPROVE"}],
            "rewritten_item": {"item_id": "ITEM-v2"},
            "objectives": [],
            "activities": [],
            "simulations": [{"simulation_id": "SIM-1", "scored_item_id": "SOMETHING-ELSE"}],
            "metrics": [],
            "knowledge_checks": [],
        }
        r = validate(broken)
        codes = {f.code for f in r.failures}
        return "SIMULATION_SCORES_WRONG_BEHAVIOR" in codes, (
            f"a simulation scoring a different item was caught: {sorted(codes) or 'nothing was caught'}"
        )

    case(
        "E8",
        "A simulation scoring the wrong behaviour is caught",
        "The failure ResultsCX names in their own process document: an excellent "
        "simulation that scores the wrong behaviour, found only when the quality "
        "data looks identical to before.",
        e8,
    )

    # ---- E9 ----------------------------------------------------------------
    def e9():
        if not have_data:
            return False, "the supplied export is not present on this host"
        blob = json.dumps([o.as_dict() for o in observations], default=str)
        blob += json.dumps(audit, default=str)
        patterns = [
            (r"\bAgent\s*\d+\b", "supplied agent label"),
            (r"\bQA\s*\d+\b", "supplied evaluator label"),
            (r"\b\d{4}-\d{2}-\d{2}\b", "date of service"),
        ]
        found = {label: len(re.findall(p, blob)) for p, label in patterns if re.search(p, blob)}
        total_redacted = sum((redactions or {}).values())
        return not found, (
            f"{len(blob):,} bytes of rendered output scanned, no supplied identifier "
            f"present; {total_redacted} identifiers were found and redacted at intake"
            if not found
            else f"LEAKED: {found}"
        )

    case(
        "E9",
        "No supplied identifier reaches a rendered surface",
        "Every byte the interface would render is scanned for personnel labels and dates of service.",
        e9,
    )

    # ---- E10 ---------------------------------------------------------------
    def e10():
        if not have_data:
            return False, "the supplied export is not present on this host"
        d = diagnose(observations, audit)
        attribution = d.individual_attribution
        has_remedy = bool(attribution.get("remedy", {}).get("minimum_linking_calls"))
        return (
            attribution["licensed"] is False and has_remedy,
            "individual diagnosis declined, and the decline carries the corrective "
            f"protocol: {attribution['remedy']['action']}"
            if has_remedy
            else "declined WITHOUT a remedy attached",
        )

    case(
        "E10",
        "Ambiguous evidence defers, with the fix attached",
        "The system must decline an individual finding it cannot support, and must "
        "never render a decline without the remedy beside it.",
        e10,
    )

    # ---- E11, differentiator ------------------------------------------------
    def e11():
        disconnected = [
            _obs("R1", "A1", "d1", "i", True),
            _obs("R1", "A2", "d2", "i", True),
            _obs("R2", "A3", "d3", "i", True),
            _obs("R2", "A4", "d4", "i", True),
        ]
        r = connectivity_report(disconnected)
        live = connectivity_report(observations) if have_data else None
        detail = (
            f"a deliberately disconnected design returned {r.n_components} components and verdict {r.verdict}"
        )
        if live:
            detail += (
                f"; the supplied design returned {live.n_components} component with "
                f"linkage fragility {live.linkage_fragility} of {live.n_subjects}"
            )
        return r.n_components > 1 and r.verdict == "DISCONNECTED", detail

    case(
        "E11",
        "A disconnected design is detected",
        "Fed a design where two evaluators share no subject, the system must report "
        "it. The refusal to diagnose an individual rests entirely on this firing.",
        e11,
    )

    # ---- E12, differentiator ------------------------------------------------
    def e12():
        required = n_per_arm(0.176, 0.60)
        verdict = improvement_claim_licensed(observed_n_per_arm=17, required=required)
        return (
            verdict["licensed"] is False and verdict["verdict"] == "INSUFFICIENT_POWER",
            f"{verdict['statement']} Method: {required.method}",
        )

    case(
        "E12",
        "An underpowered improvement claim is refused",
        "Given fewer calls than the detection threshold requires, the system refuses "
        "to declare improvement AND prints the threshold rather than hiding it.",
        e12,
    )

    # ---- intake scanner is not vacuous -------------------------------------
    def scanner():
        if not have_data:
            return False, "the supplied export is not present on this host"
        counts = scan_many(["call ref 1025276", "seen 03/14/2026"]).counts
        return sum(counts.values()) >= 2, (f"planted identifiers were detected: {counts}")

    case(
        "E13",
        "The identifier scanner is not vacuous",
        "A scanner is proven by planting a violation, never by a clean run. A scan "
        "that matches nothing reports clean in the same words as one that works.",
        scanner,
    )

    report.total = len(report.cases)
    report.passed = sum(1 for c in report.cases if c.passed)
    return report


if __name__ == "__main__":
    result = run()
    for c in result.cases:
        mark = "PASS" if c.passed else "FAIL"
        star = " *" if c.is_differentiator else "  "
        print(f"[{mark}]{star} {c.id:<4} {c.name}")
        print(f"          {c.detail}")
    print(f"\n{result.passed} of {result.total} passed")
    sys.exit(0 if result.passed == result.total else 1)

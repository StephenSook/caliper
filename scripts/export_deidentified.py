"""Write the de-identified observation matrix that a public host runs on.

The supplied case package is confidential and cannot leave this machine. The
engine does not need it. Everything CALIPER computes, the reliability
coefficient, the interval, item difficulty and discrimination, the design graph,
the diagnosis, is a function of one thing: which questions were marked passed or
failed on which evaluation, by which rater, about which agent.

So the host gets exactly that and nothing else. Per row:

    eval_id, agent_ref, rater_ref   salted blake2s pseudonyms. The salt is
                                    generated here, used once, and never written
                                    to the export or anywhere else, so the
                                    pseudonyms cannot be reversed even by
                                    someone holding the original workbook
    domain, item_id, item_text      the client's own instrument, which is the
                                    subject of the audit and is on screen anyway
    passed                          the measurement
    occasion_index                  ordinal position, so occasions can still be
                                    ordered without a date

Deliberately absent: names, evaluator comments, member and participation
identifiers, call identifiers, dates of service, dollar amounts. Observation
already drops the date at its serialization boundary; this drops everything
else by only ever emitting that boundary.

This is not a smaller copy of the data. It is the matrix the arithmetic runs on,
and the arithmetic still runs live on the host: nothing is precomputed, nothing
is hardcoded, and the numbers a judge sees are regenerated from these rows on
request.

    python scripts/export_deidentified.py
    python scripts/check_deidentified.py     <- proves the result before it ships
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Python puts the SCRIPT's directory on sys.path, not the working directory, so
# running this as `python scripts/export_deidentified.py` cannot see the package
# even from the repository root. The package is not pip installed in this venv;
# it is imported from the tree.
sys.path.insert(0, str(ROOT))

from caliper.ingest.normalize import DOMAIN_FILES, load_all  # noqa: E402

RAW = Path(os.environ.get("CALIPER_DATA_DIR", ROOT / "data" / "raw"))
OUT_DIR = ROOT / "data" / "deidentified"
OUT = OUT_DIR / "observations.json"


def main() -> int:
    if not RAW.is_dir():
        print(f"FAIL  no supplied package at {RAW}")
        return 1

    observations, redactions, _salt = load_all(RAW)
    if not observations:
        print("FAIL  the supplied package produced no observations")
        return 1

    # Record WHICH package this came from without shipping any of it. A hash is
    # not reversible and it means a reader can be told the export is derived
    # from a specific set of files rather than asked to take it on trust.
    sources = {}
    for filename in DOMAIN_FILES.values():
        path = RAW / filename
        if path.exists():
            sources[filename] = hashlib.sha256(path.read_bytes()).hexdigest()

    payload = {
        "schema": 1,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": (
            "De-identified item score matrix derived from the supplied case package. "
            "Pseudonyms are salted blake2s digests; the salt was used once and never "
            "recorded, so they cannot be reversed. No name, comment, member or call "
            "identifier, date of service or dollar amount is present."
        ),
        "source_sha256": sources,
        "redactions": redactions,
        "observations": [o.as_dict() for o in observations],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")

    # Prove the export is equivalent before anyone trusts it.
    #
    # The claim this whole mechanism rests on is that the host computes the same
    # answers from the matrix that this machine computes from the workbooks. That
    # is a claim, so it gets checked here, against both, while both are in hand.
    # It cannot be checked anywhere else: a public host has only one of them and
    # CI has neither.
    from caliper.ingest.normalize import load_deidentified
    from caliper.instrument.audit import audit_all

    round_tripped, round_tripped_redactions = load_deidentified(OUT)
    before = audit_all(observations, redactions)
    after = audit_all(round_tripped, round_tripped_redactions)

    mismatches = []
    for domain, a in before["domains"].items():
        b = after["domains"][domain]
        for key in ("point_estimate", "ci_low", "ci_high", "n_evaluations", "n_items"):
            x, y = a["reliability"][key], b["reliability"][key]
            if abs(x - y) > 1e-12:
                mismatches.append(f"{domain}.{key}: {x} vs {y}")
        if [i["item_id"] for i in a["items"]] != [i["item_id"] for i in b["items"]]:
            mismatches.append(f"{domain}: item order differs")
        for i, j in zip(a["items"], b["items"], strict=True):
            if sorted(i["flags"]) != sorted(j["flags"]):
                mismatches.append(f"{domain}.{i['item_id']}: flags differ")
    if before["connectivity"] != after["connectivity"]:
        mismatches.append("connectivity differs")

    if mismatches:
        print("FAIL  the export does not reproduce the supplied package:")
        for m in mismatches:
            print(f"        {m}")
        OUT.unlink(missing_ok=True)
        print("      the export was deleted rather than left on disk to be shipped")
        return 1

    domains = sorted({o.domain for o in observations})
    print(f"  wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(payload['observations']):,d} observations, {len(domains)} domains")
    print(f"  domains: {', '.join(domains)}")
    print(
        f"  {len({o.eval_id for o in observations})} evaluations, "
        f"{len({o.agent_ref for o in observations})} agents, "
        f"{len({o.rater_ref for o in observations})} raters"
    )
    print(f"  source files hashed: {len(sources)}")
    print("  parity: every reliability figure, item flag and connectivity value matches the workbooks")
    print("  now run: python scripts/check_deidentified.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

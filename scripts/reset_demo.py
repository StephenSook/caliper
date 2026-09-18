"""Put the demonstration back to a clean start.

Between run throughs the run store fills with half finished runs, and the phone
attaches to whichever was most recent. That is fine while rehearsing and wrong
the moment it is the real thing.

This removes every REHEARSAL run and leaves real ones alone, then reports what a
second device would now find. It is deliberately not a database wipe: a run that
a human approved is evidence, and evidence does not get deleted to tidy up.

    python scripts/reset_demo.py            report and clear rehearsals
    python scripts/reset_demo.py --all      also clear real runs, asks first
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from caliper.orchestrator.run_state import RunStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="also remove real runs")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation for --all")
    a = ap.parse_args()

    store = RunStore()

    before_any = store.latest(include_rehearsals=True)
    before_real = store.latest()
    cleared = store.clear_rehearsals()
    print(f"  cleared {cleared} rehearsal run(s)")

    if a.all:
        if not a.yes:
            print("\n  --all removes runs a human approved, which are evidence.")
            print("  Re run with --yes if that is really what you want.")
            return 1
        import sqlite3
        from contextlib import closing

        with closing(sqlite3.connect(store.db_path)) as conn, conn:
            n = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            conn.execute("DELETE FROM ledger")
            conn.execute("DELETE FROM runs")
        print(f"  cleared {n} real run(s) as well")

    after = store.latest()
    print()
    print(f"  before: latest overall {before_any or 'none'}, latest real {before_real or 'none'}")
    print(f"  now:    a second device would attach to {after or 'nothing, which is a clean start'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pack the de-identified matrix into one environment variable value.

A deployed host holds no case package and no export file. It is handed the
matrix as a single variable and recomputes every figure from it.

The URL safe base64 alphabet is used deliberately. The standard alphabet
contains + and /, and a value carrying those survives most transports and not
all of them: the first attempt at this reached the host corrupted and died with
"CRC check failed", which is a true statement about gzip and tells you nothing
about which of a dozen hops altered the string. The URL safe alphabet has no
character that anything rewrites.

    python scripts/pack_observations.py            print the value
    python scripts/pack_observations.py --verify   round trip it first
"""

from __future__ import annotations

import base64
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "data" / "deidentified" / "observations.json"


def main() -> int:
    if not EXPORT.exists():
        print(f"FAIL  no export at {EXPORT}", file=sys.stderr)
        print("      run: python scripts/export_deidentified.py", file=sys.stderr)
        return 1

    raw = EXPORT.read_bytes()
    packed = base64.urlsafe_b64encode(gzip.compress(raw, 9)).decode().rstrip("=")

    # Round trip exactly the way the server does, so a value that cannot be read
    # is never printed in the first place.
    restored = packed.replace("-", "+").replace("_", "/")
    restored += "=" * (-len(restored) % 4)
    check = gzip.decompress(base64.b64decode(restored, validate=True))
    if check != raw:
        print("FAIL  the packed value does not round trip", file=sys.stderr)
        return 1
    n = len(json.loads(check)["observations"])

    if "--verify" in sys.argv:
        print(f"ok    {len(packed)} characters, round trips to {n} observations", file=sys.stderr)
        return 0

    print(packed)
    print(
        f"\n{len(packed)} characters, URL safe alphabet, round trips to {n} observations",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

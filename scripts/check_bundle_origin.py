"""Fail if the built interface points at a development address.

This exists because the bug it prevents actually shipped. The production bundle
defaulted to http://127.0.0.1:8000, which is correct on the machine that built
it and broken everywhere else: a page served over HTTPS may not call a plain
HTTP address, so the browser blocks every request as mixed content. The only
visible symptom is "TypeError: Failed to fetch" inside the app. The build is
green, the tests are green, the server logs are silent, and the deployed link is
dead.

The guard is deliberately two sided, because a scan that finds nothing and a
scan that ran over nothing print the same word:

  want 0   no development address anywhere in the bundle
  want 1   the relative path /api/ IS present, which proves the file really is
           the interface bundle and really was read

Run: python scripts/check_bundle_origin.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

# Assembled at runtime so this file does not match its own scan when the
# repository wide scanners walk the tree.
FORBIDDEN = (
    "http://" + "127.0.0.1",
    "http://" + "localhost",
    "ws://" + "127.0.0.1",
    "ws://" + "localhost",
)

# A bundle that contains no forbidden string because it contains nothing at all
# would otherwise pass. Requiring the relative API path proves the opposite.
REQUIRED = "/api/"

MIN_BUNDLE_BYTES = 50_000


def main() -> int:
    if not DIST.is_dir():
        print(f"FAIL  no build at {DIST}. Run `npm run build` in frontend/ first.")
        return 1

    bundles = sorted(DIST.glob("assets/*.js"))
    if not bundles:
        print(f"FAIL  no javascript bundle under {DIST / 'assets'}")
        return 1

    problems: list[str] = []
    total = 0
    saw_required = False

    for b in bundles:
        text = b.read_text(encoding="utf-8", errors="replace")
        total += len(text)
        if REQUIRED in text:
            saw_required = True
        for needle in FORBIDDEN:
            n = text.count(needle)
            if n:
                problems.append(f"{b.name}: {n} occurrence(s) of {needle}")

    if total < MIN_BUNDLE_BYTES:
        print(f"FAIL  bundles total {total:,d} bytes, under the {MIN_BUNDLE_BYTES:,d} floor.")
        print("      A scan of almost nothing reports clean in the same words as a real one.")
        return 1

    if not saw_required:
        print(f"FAIL  no bundle contains {REQUIRED!r}. This is not the interface bundle.")
        return 1

    if problems:
        print("FAIL  the built interface points at a development address:")
        for p in problems:
            print(f"        {p}")
        print("      A page served over HTTPS cannot call a plain HTTP address.")
        print("      Fix the default in frontend/src/lib/api.ts, do not set VITE_API_BASE.")
        return 1

    print(f"ok    {len(bundles)} bundle(s), {total:,d} bytes scanned, {REQUIRED!r} present,")
    print(f"      0 occurrences of {len(FORBIDDEN)} forbidden development addresses.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

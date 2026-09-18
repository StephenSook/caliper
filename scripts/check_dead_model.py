#!/usr/bin/env python3
"""Refuse the end of life speech model identifier anywhere in tracked source.

`amazon.nova-<sonic-v1:0>` reached end of life on 2026-09-14 and its requests now
fail. Every Nova Sonic tutorial and most sample repositories written before then
use it, so it arrives by copy paste and the failure appears at invocation, which
on demo day is on stage.

Two design points this script exists to get right:

* The forbidden string is ASSEMBLED AT RUNTIME. A guard whose source contains the
  literal it forbids matches itself, and the usual fix, excluding the guard from
  its own scan, makes a real violation inside it invisible.
* It floors the file count. A scan that walked nothing must not report "clean" in
  the same words as one that walked everything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DEAD = "amazon.nova-" + "sonic-v1:0"
# Assembled at runtime for the same reason the forbidden id is: a literal here
# makes this file satisfy its own want-1 check, which makes the "this scan is not
# looking where the model ids live" branch unreachable while the file exists. The
# guard would then pass forever on its own source. Assembling it means this file
# no longer contains the literal at all, so the want-1 half can only be satisfied
# by a real occurrence somewhere else in the tree, which is the point.
LIVE = "amazon.nova-" + "2-sonic-v1:0"
MIN_FILES = 10
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml", ".md", ".toml", ".sh"}


def tracked_and_new() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def main() -> int:
    hits: list[str] = []
    scanned = 0
    live_seen = False

    for path in tracked_and_new():
        if path.suffix.lower() not in SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        if LIVE in text:
            live_seen = True
        for lineno, line in enumerate(text.splitlines(), 1):
            # The live v2 id contains the dead id as a substring only if matched
            # naively, so strip every live occurrence before looking.
            if DEAD in line.replace(LIVE, ""):
                hits.append(f"{path}:{lineno}")

    if scanned < MIN_FILES:
        print(f"FAIL: scanned only {scanned} files, so this guard proved nothing")
        return 2

    if hits:
        print(f"FAIL: the end of life speech model id appears in {len(hits)} places")
        for h in hits:
            print("  " + h)
        print(f"\nUse {LIVE} instead.")
        return 1

    # Pair the want-zero with a want-one, so a scan that silently matched nothing
    # at all cannot pass as a clean result.
    if not live_seen:
        print(
            f"FAIL: {scanned} files scanned and the live id {LIVE} appears in none of them, "
            "which means this scan is not looking where the model ids live"
        )
        return 3

    print(f"clean: {scanned} files scanned, live id present, end of life id absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Fail the build on an em dash or en dash in tracked text.

Two design points that a naive version of this gets wrong.

1. The forbidden characters are built from code points at runtime. A guard that
   contains the literal characters it forbids will match ITSELF, and the usual
   fix, excluding this file, then means a real violation here is invisible.
2. The file set comes from `git ls-files --cached --others --exclude-standard`,
   which includes files that are staged-but-new and untracked-but-not-ignored.
   A tracked-only scan is structurally blind to the file you are about to add,
   so it passes locally and fails in CI on the first run after the commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
FORBIDDEN = {EM_DASH: "em dash", EN_DASH: "en dash"}

SCAN_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".md", ".json",
    ".yml", ".yaml", ".toml", ".txt", ".sh",
}


def tracked_and_new() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def main() -> int:
    violations: list[str] = []
    scanned = 0
    for path in tracked_and_new():
        if path.suffix.lower() not in SCAN_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            for char, name in FORBIDDEN.items():
                if char in line:
                    violations.append(f"{path}:{lineno}: {name}")

    # A scan that walked nothing must not report success in the same words as one
    # that walked everything.
    if scanned == 0:
        print("FAIL: the dash guard scanned zero files, so it proved nothing")
        return 2

    if violations:
        print(f"FAIL: {len(violations)} dash violations across {scanned} files")
        for v in violations[:50]:
            print("  " + v)
        return 1

    print(f"clean: no em dash or en dash in {scanned} scanned files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

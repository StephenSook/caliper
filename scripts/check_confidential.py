#!/usr/bin/env python3
"""Refuse to let competition confidential material become trackable.

The supplied ResultsCX case package, the sponsor case study, the internal build
spec and the research corpus are all confidential. `.gitignore` is the control,
and this script is the check that the control actually holds, because a
`.gitignore` that silently stops matching looks exactly like one that works.

Design notes, each of which is a defect this would otherwise have:

* It asserts on the set git would ACTUALLY stage, not on a glob of the working
  directory, because those two differ precisely when a pattern has stopped
  matching.
* It floors the number of files inspected. A scan that walks nothing reports
  "clean" in the same words as one that walks everything.
* It checks file CONTENT for supplied personnel labels as well as filenames,
  because a screenshot or a fixture can carry the data without carrying the name.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MIN_TRACKED_FILES = 10

# Filenames that must never be staged, matched case insensitively.
FORBIDDEN_NAMES = [
    re.compile(r"resultscx.*confidential", re.I),
    re.compile(r"caliper_build_spec", re.I),
    re.compile(r"caliper_team_briefing", re.I),
    re.compile(r"ai competition case study", re.I),
    re.compile(r"^frontend doc$", re.I),
    re.compile(r"labor_cost_curriculum", re.I),
    re.compile(r"rcx_isd_process", re.I),
    re.compile(r"rcx_design_templates", re.I),
    re.compile(r"training outline and qa", re.I),
    re.compile(r"\.(xlsx|xls|docx|doc|pptx|zip|pdf)$", re.I),
]

# Supplied personnel labels and identifier shapes that must not appear in any
# tracked text file. Synthetic fixtures use pseudonyms, so these are violations.
FORBIDDEN_CONTENT = [
    (re.compile(r"\bTeam Lead\s*\d+\b"), "supplied team leader label"),
    (re.compile(r"\bWDSK[A-Z0-9]{4,}\b"), "participation id"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "social security number"),
]

TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt",
                 ".yml", ".yaml", ".toml", ".csv", ".html", ".css", ".sh"}

# This file names the patterns it forbids, so it must exclude itself by git
# pathspec rather than by a string filter whose anchors could behave differently.
SELF = "scripts/check_confidential.py"


def staged_or_tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
         "--", ".", f":(exclude){SELF}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def main() -> int:
    files = staged_or_tracked()
    problems: list[str] = []

    for path in files:
        name = path.name
        for pattern in FORBIDDEN_NAMES:
            if pattern.search(name) or pattern.search(str(path)):
                problems.append(f"FILENAME  {path}  matches {pattern.pattern}")
                break

    inspected = 0
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        inspected += 1
        for pattern, label in FORBIDDEN_CONTENT:
            if pattern.search(text):
                problems.append(f"CONTENT   {path}  contains {label}")

    if len(files) < MIN_TRACKED_FILES:
        print(f"FAIL: only {len(files)} files visible to the guard; it proved nothing")
        return 2

    if problems:
        print(f"FAIL: {len(problems)} confidentiality violations")
        for p in problems:
            print("  " + p)
        print("\nThese must never be committed. Fix .gitignore, do not use git add -A.")
        return 1

    print(
        f"clean: {len(files)} tracked or stageable files, {inspected} text files inspected, "
        "no confidential artifact and no supplied identifier"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

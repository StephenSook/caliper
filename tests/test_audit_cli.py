"""The audit command is what the README tells a stranger to run.

The case package is competition confidential and is deliberately not in this
repository, so a clean clone has no data and this command is the first thing a
judge hits. Two things must hold there and neither is covered by testing
audit_all directly: the failure has to be legible rather than a traceback, and
it must not print the supplied export's filename, which names the client
relationship, into a stranger's terminal.

Found by cloning the public repo into an empty directory and running the README
in order, which is the only way this class of defect shows up: every developer
machine has the data, so the happy path is the only path anyone ever exercises.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MISSING = "/nonexistent/path/a/judge/does/not/have"


def _run_without_data() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "caliper.instrument.audit", "--data-dir", MISSING],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
    )


def test_missing_case_package_exits_cleanly_rather_than_raising():
    result = _run_without_data()
    assert result.returncode == 2, (
        f"expected a deliberate exit code 2, got {result.returncode}. "
        "Exit 1 with a traceback is what an unhandled error looks like."
    )
    assert "Traceback" not in result.stderr, (
        "a stranger following the README must not be shown a traceback:\n" + result.stderr
    )


def test_missing_case_package_does_not_print_the_supplied_filename():
    """The export's filename carries the client relationship, so it is not
    something to print at someone who just cloned a public repository."""
    result = _run_without_data()
    combined = (result.stdout + result.stderr).lower()
    for fragment in ("healthcare partner", "qa raw data", ".xlsx"):
        assert fragment not in combined, f"{fragment!r} leaked to a stranger's terminal"


def test_missing_case_package_says_what_to_do_instead():
    """A refusal that does not hand over the next step is only half an answer,
    and the live instance needs neither the package nor a credential."""
    result = _run_without_data()
    assert "caliper-77ma.onrender.com" in result.stderr
    assert "CALIPER_DATA_DIR" in result.stderr
    assert MISSING in result.stderr, "say which path was actually looked at"

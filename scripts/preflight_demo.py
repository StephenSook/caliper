"""One command that answers: is everything a judge will touch working right now.

Run this before the presentation, and again if anything is changed after the
freeze. It exits non zero if any check fails, so it can be trusted as a gate
rather than read as a report.

Every check verifies CONTENT rather than a status code, because the failures that
matter here all return 200: a host serving a stale bundle, a page that renders
with no findings because its data went missing, a release asset that silently
changed. A 200 is not evidence that the right thing came back.

    python scripts/preflight_demo.py
    python scripts/preflight_demo.py --local http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from caliper.ingest.pii_scan import PATTERNS  # noqa: E402

DEPLOYED = "https://caliper-77ma.onrender.com"
REPO = "StephenSook/caliper"

# The evidence spine. These are the figures on the slides, in the narration and
# in the repository, and the whole product is an argument about not asserting a
# number you cannot regenerate. If a surface disagrees with these, the surface is
# wrong and this must say so before a judge finds it.
SPINE = {
    "member_experience_kr20": 0.4661,
    "member_experience_ci_low": -0.019,
    "member_experience_ci_high": 0.776,
    "linkage_fragility": 2,
}
TOLERANCE = 0.0006

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)
    return ok


def fetch(url: str, timeout: int = 45) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


def check_instance(label: str, base: str) -> None:
    print(f"\n{label}  {base}")

    status, body = fetch(base + "/api/health")
    if not check("health answers", status == 200, f"HTTP {status}"):
        return
    health = json.loads(body)
    check("the host has its observations", health.get("data_dir_present") is True)

    # Whether a call can happen, and on which account.
    #
    # This is here because the failure it catches broke the centerpiece and was
    # completely silent: the voice layer resolved a default AWS profile whose
    # session had expired, the socket opened, the timer ran, and the model never
    # answered. A public host is EXPECTED to report false, so it is reported
    # rather than asserted; what is asserted is that the host has an opinion and
    # can explain it.
    speech = health.get("speech") or {}
    check(
        "the host reports whether it can take a call",
        bool(speech.get("reason")),
        f"profile={speech.get('profile')} account={speech.get('account')}",
    )
    print(
        f"        speech: {'available' if health.get('speech_available') else 'NOT available'}"
        f"  {speech.get('reason', '')[:90]}"
    )

    status, body = fetch(base + "/judge", timeout=60)
    judge = body.decode(errors="replace")
    check("judge door answers", status == 200, f"HTTP {status}")
    # A page can be 200 and empty. Require the finding to be on it.
    check("judge door carries the finding", "0.466" in judge and "-0.019" in judge)
    check("judge door is not trivially short", len(judge) > 6000, f"{len(judge):,d} bytes")

    status, body = fetch(base + "/api/evidence", timeout=60)
    if check("evidence recomputes", status == 200, f"HTTP {status}"):
        ev_obj = json.loads(body)
        # Read each value at its own key. The previous version searched the whole
        # evidence document as one string for ANY number near the target, so it
        # was never bound to the key it named: member_experience could drift to
        # anything while business_process still carried the old value somewhere
        # in the payload, and all four spine checks passed. The integer branch
        # was worse, a substring test for "2" against a JSON document full of
        # counts. This is the one guard between the engine and every figure we
        # say out loud, so it has to fail when the thing it names is wrong.
        try:
            actual = {
                "member_experience_kr20": ev_obj["instruments"]["member_experience"]["kr20"],
                "member_experience_ci_low": ev_obj["instruments"]["member_experience"]["ci_low"],
                "member_experience_ci_high": ev_obj["instruments"]["member_experience"]["ci_high"],
                "linkage_fragility": ev_obj["connectivity"]["linkage_fragility"],
            }
        except (KeyError, TypeError) as exc:
            check(f"spine: evidence has the expected shape ({exc})", False)
            actual = {}

        for key, want in SPINE.items():
            if key not in actual:
                continue
            got = actual[key]
            if isinstance(want, float):
                ok = isinstance(got, int | float) and abs(float(got) - want) < TOLERANCE
            else:
                ok = got == want
            check(f"spine: {key} = {want}", ok, f"got {got!r}")

    status, body = fetch(base + "/api/golden", timeout=90)
    if check("golden harness answers", status == 200, f"HTTP {status}"):
        g = json.loads(body)
        cases = g.get("cases", g.get("results", []))
        passed = sum(1 for c in cases if c.get("passed") or c.get("status") == "PASS")
        check("golden cases all pass", cases and passed == len(cases), f"{passed} of {len(cases)}")

    # The interface bundle has to be the CURRENT one, and has to be reachable.
    import re

    html = fetch(base + "/")[1].decode(errors="replace")
    m = re.search(r"/assets/index-[A-Za-z0-9_-]+\.js", html)
    if check("interface bundle is referenced", m is not None):
        status, js = fetch(base + m.group(0), timeout=60)
        check("interface bundle is served", status == 200 and len(js) > 100_000, f"{len(js):,d} bytes")
        check(
            "no development address in the served bundle",
            b"127.0.0.1" not in js and b"//localhost" not in js,
        )

    corpus = judge + html
    hits = {k: len(p.findall(corpus)) for k, p in PATTERNS if p.findall(corpus)}
    check("no identifier on any judge facing surface", not hits, str(hits) if hits else "")


def check_release() -> None:
    print("\nPublished Android build")
    out = subprocess.run(
        ["gh", "release", "view", "--repo", REPO, "--json", "tagName,assets"],
        capture_output=True,
        text=True,
    )
    if not check("a release exists", out.returncode == 0, out.stderr.strip()[:80]):
        return
    rel = json.loads(out.stdout)
    assets = rel.get("assets", [])
    check(
        "the release carries an apk",
        any(a["name"].endswith(".apk") for a in assets),
        f"{rel.get('tagName')}: {[a['name'] for a in assets]}",
    )
    for a in assets:
        if a["name"].endswith(".apk"):
            check("the apk is a plausible size", a["size"] > 1_000_000, f"{a['size']:,d} bytes")


def check_local_voice(base: str) -> None:
    """The laptop instance is the one that has to take a live call."""
    print(f"\nVoice, on the instance that will demonstrate it  {base}")
    status, body = fetch(base.rstrip("/") + "/api/health")
    if not check("health answers", status == 200, f"HTTP {status}"):
        return
    health = json.loads(body)
    speech = health.get("speech") or {}
    ok = check(
        "this instance can take a live call",
        health.get("speech_available") is True,
        speech.get("reason", "")[:120],
    )
    if ok:
        check(
            "credentials belong to an account",
            bool(speech.get("account")),
            f"profile={speech.get('profile')} account={speech.get('account')}",
        )
        print("        run `python scripts/smoke_voice.py` to exercise the call itself")


def check_claims() -> None:
    """Prose drifts from code silently and in one direction.

    A figure gets corrected in the engine and the paragraph quoting it does not.
    Nothing goes red, and the first person to notice is a judge reading a README
    beside a screen that disagrees with it.
    """
    print("\nJudge facing figures against the engine")
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_claims.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    ok = check("every claimed figure matches what the code regenerates", out.returncode == 0)
    if not ok:
        for line in out.stdout.splitlines():
            if "FAIL" in line or "also states" in line:
                print(f"        {line.strip()}")


def check_repo() -> None:
    print("\nRepository")
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout
    check("working tree is clean", not dirty.strip(), f"{len(dirty.splitlines())} changed")

    subprocess.run(["git", "fetch", "--quiet"], capture_output=True)
    local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    remote = subprocess.run(
        ["git", "rev-parse", "origin/main"], capture_output=True, text=True
    ).stdout.strip()
    check("local matches origin/main", local == remote, f"{local[:8]} vs {remote[:8]}")

    # The per SHA check runs API is the verdict. A watch command's exit code is
    # not, and neither is the newest run, which can belong to a different commit.
    # Read status and conclusion together. Three states have to stay distinct:
    # green, actually failing, and still running. A run in progress has a null
    # conclusion, so a bare `conclusion != "success"` filter reports it as
    # failing, which is a false alarm minutes before a demo. And zero check runs
    # produces empty output, which reads as green, so the count is floored: that
    # is the want-1 the want-0 needs.
    out = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{REPO}/commits/{local}/check-runs",
            "--jq",
            '.check_runs[] | "\\(.status)\\t\\(.conclusion // "")\\t\\(.name)"',
        ],
        capture_output=True,
        text=True,
    )
    runs = [line.split("\t") for line in out.stdout.strip().splitlines() if line.strip()]
    failing = [name for status, concl, name in runs if status == "completed" and concl != "success"]
    pending = [name for status, _, name in runs if status != "completed"]

    if out.returncode != 0:
        check("CI green on this exact commit", False, "could not read the check runs API")
    elif not runs:
        check(
            "CI green on this exact commit",
            False,
            "no check runs exist for this commit yet, so nothing has been built",
        )
    elif failing:
        check("CI green on this exact commit", False, f"failing: {', '.join(failing)}")
    elif pending:
        check(
            "CI green on this exact commit",
            False,
            f"still running, not yet green: {', '.join(pending)}",
        )
    else:
        check("CI green on this exact commit", True, f"{len(runs)} check run(s) all success")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deployed", default=DEPLOYED)
    ap.add_argument("--local", default=None, help="also check a laptop instance, e.g. the tunnel")
    ap.add_argument("--skip-repo", action="store_true")
    a = ap.parse_args()

    check_instance("Deployed instance", a.deployed.rstrip("/"))
    if a.local:
        check_instance("Local instance", a.local.rstrip("/"))
        check_local_voice(a.local)
    check_release()
    check_claims()
    if not a.skip_repo:
        check_repo()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("everything a judge will touch is answering correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

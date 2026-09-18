"""Prove the practice call works, without needing a person to speak.

The live call is the centerpiece of the demonstration and the most fragile thing
in the system: it crosses a credential chain, a transport that has to be selected
by hand, a bidirectional stream, an endpointing rule, and a scorer. Any one of
them can fail in a way that looks like silence, and silence is the failure mode
with no diagnosis attached.

Checking it used to mean finding a human, putting on a headset and talking. That
is not a check anybody runs five times before a demonstration, so it did not get
run. This does the same thing with synthesised speech, through the SHIPPED
WebSocket rather than around it, and it can run as often as you like.

The synthesised voice is a TEST INPUT and nothing else. It is never demo
evidence, it is never recorded, and no figure anywhere is computed from it. It
exists so that "the call works" is a thing that was verified rather than a thing
that was true yesterday.

    python scripts/smoke_voice.py
    python scripts/smoke_voice.py --base http://127.0.0.1:8000 --say "your line"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# A scripted call that exercises all three criteria, in the order a real one
# would. The figures are the persona's and they are internally consistent: the
# plan allows 1425 of a 1700 bill, the 275 difference is a network adjustment the
# member never owes, and 20 percent coinsurance on the allowed amount is 285.
#
# Turn one satisfies the identity criterion, which needs a name plus TWO further
# identifiers. That is not arbitrary strictness: it is the same bar as the
# Compliance form's own "validate three pieces of HIPAA" item, the one that has
# never distinguished anyone. Turn two distinguishes billed from allowed. Turn
# three asks for the teach back, which is the only criterion the MEMBER has to
# satisfy, and the code checks whether she was right rather than whether she
# sounded convincing.
SCRIPT = [
    (
        "identity",
        "Thanks for calling, my name is Sam. Before I can go over any plan details I need to "
        "verify who I am speaking with. Can I get your full name, your date of birth, and the "
        "member ID number from the front of your card?",
    ),
    (
        "explanation",
        "Thank you, you are verified. So the hospital billed seventeen hundred dollars, but the "
        "allowed amount your plan negotiated for that service is fourteen hundred and twenty "
        "five. You are never responsible for the difference between what they billed and what "
        "the plan allows. That two hundred and seventy five dollars is a network adjustment and "
        "it gets written off. Your deductible is already met, so you owe twenty percent "
        "coinsurance on the allowed amount, and that comes to two hundred and eighty five "
        "dollars.",
    ),
    (
        "teach back",
        "Before we finish, and this is just so I know I explained it clearly, can you tell me in "
        "your own words what you owe and why?",
    ),
]


def synthesise(line: str) -> bytes:
    """macOS speech, resampled to exactly what the stream expects.

    16 kHz, sixteen bit, mono, little endian. Any other rate produces audio the
    model accepts and cannot understand, which reads as the model ignoring you.
    """
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "line.aiff"
        raw = Path(tmp) / "line.raw"
        subprocess.run(["say", "-o", str(aiff), line], check=True, capture_output=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(aiff),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                str(raw),
            ],
            check=True,
            capture_output=True,
        )
        return raw.read_bytes()


async def run(base: str, turns: list[tuple[str, str]], quiet_seconds: float) -> int:
    import websockets

    http = base.rstrip("/")
    ws_url = http.replace("http", "ws", 1) + "/ws/practice/"

    health = json.loads(urllib.request.urlopen(http + "/api/health", timeout=20).read())
    speech = health.get("speech", {})
    print(f"  host           {http}")
    print(f"  speech profile {speech.get('profile')}  account {speech.get('account')}")
    if not health.get("speech_available"):
        print(f"  FAIL  this host cannot take a call: {speech.get('reason')}")
        return 1

    # Always a FRESH run, never the latest one.
    #
    # Attaching to latest_run_id meant rehearsing wrote the synthesised call's
    # score into the very run about to be demonstrated, stamped the ledger with
    # this script as the actor, and left the screen showing the rehearsal's
    # result. Inviting anyone to run this as often as they like made that a
    # certainty rather than a risk.
    req = urllib.request.Request(
        http + "/api/runs",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    run_id = json.loads(urllib.request.urlopen(req, timeout=240).read())["run_id"]
    print(f"  run            {run_id}  (fresh, so the demonstrated run is untouched)")

    print(f"  script         {len(turns)} turn(s)")

    seen: dict[str, int] = {}
    transcripts: list[tuple[str, str]] = []
    criteria: list[dict] = []

    async with websockets.connect(ws_url + run_id, origin=http, open_timeout=45) as ws:

        async def pump() -> None:
            async for raw in ws:
                event = json.loads(raw)
                kind = event.get("type", "?")
                seen[kind] = seen.get(kind, 0) + 1
                if kind == "transcript" and event.get("content", "").strip():
                    transcripts.append((event.get("role", "?"), event["content"]))
                elif kind in ("score", "ready"):
                    criteria[:] = event.get("criteria", criteria)
                elif kind in ("error", "unavailable"):
                    print(f"  server said: {json.dumps(event)[:200]}")

        task = asyncio.create_task(pump())
        await asyncio.sleep(1.0)

        frame = 1024
        silence = bytes(frame)

        for label, text in turns:
            audio = synthesise(text)
            print(f"  turn: {label}  ({len(audio) / 32000:.1f}s of speech)")

            # Real time pacing. The model endpoints on silence, so audio
            # delivered faster than real time is treated as one long utterance.
            for i in range(0, len(audio), frame):
                await ws.send(audio[i : i + frame])
                await asyncio.sleep(0.030)

            # The pause is not optional. Without silence after the speech the
            # model never hears the turn end and waits forever, which is
            # indistinguishable from the call being broken.
            for _ in range(int(quiet_seconds / 0.032)):
                await ws.send(silence)
                await asyncio.sleep(0.030)

            # Let the member answer before the next line is spoken over her.
            await asyncio.sleep(8.0)
            passing = [c["id"] for c in criteria if c.get("state") == "PASS"]
            print(f"        passing after this turn: {passing or 'none yet'}")

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=20)
        except TimeoutError:
            pass
        task.cancel()

    print()
    print(f"  events         {seen or 'none'}")
    for role, text in transcripts[:6]:
        print(f"    [{role}] {text[:110]}")
    if criteria:
        for c in criteria:
            print(f"    {c.get('state', '?'):8s} {str(c.get('label', c.get('id', '')))[:70]}")

    failures = []
    if not seen.get("ready"):
        failures.append("the socket never said ready, so open() did not complete cleanly")
    if not transcripts:
        failures.append("no transcript came back, so the model did not hear the speech")
    if not seen.get("audio"):
        failures.append("no audio came back, so the member never spoke")

    print()
    if failures:
        for f in failures:
            print(f"  FAIL  {f}")
        return 1
    print("  the practice call works end to end")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--say", default=None, help="one line instead of the scripted call")
    ap.add_argument("--quiet", type=float, default=2.5, help="seconds of silence after the speech")
    a = ap.parse_args()
    turns = [("custom", a.say)] if a.say else SCRIPT
    return asyncio.run(run(a.base, turns, a.quiet))


if __name__ == "__main__":
    sys.exit(main())

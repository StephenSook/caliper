#!/usr/bin/env python3
"""Live smoke test of the practice call against the real Nova 2 Sonic model.

This exists because a green unit suite proves the event builders are shaped
right and proves nothing about whether the model answers. The ninety seconds this
supports is the part of the demo a judge describes to somebody else afterwards,
so it gets exercised against the real endpoint, repeatedly, before the room.

Speech is synthesised locally with macOS `say` and resampled to the 16 kHz the
API requires, so the test needs no microphone and can run unattended.

Pass condition, and it is deliberately strict:
  1. the stream opens
  2. the member speaks first, unprompted
  3. our spoken turns produce a toolUse, which produces a toolResult
  4. at least one criterion moves off PENDING
A run that merely connects is NOT a pass.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from caliper.voice.sonic_session import SonicSession

PERSONA = Path("caliper/voice/personas/eob_coinsurance_confusion.yaml")
FRAME_BYTES = 1024  # about 32 ms at 16 kHz sixteen bit mono

TURNS = [
    "Thank you for calling member services. Can I get your full name, "
    "your date of birth, and the member id on your card please?",
    "Thank you. I can see the claim. The hospital billed one thousand seven hundred dollars, "
    "but the amount your plan allows for that service is one thousand four hundred and "
    "twenty five. Your plan paid eleven forty, and your share is twenty percent of the "
    "allowed amount, which is two hundred and eighty five dollars.",
    "Just so I know I explained that clearly, can you tell me in your own words what you owe and why?",
]


def synth(text: str) -> bytes:
    """macOS `say` to 16 kHz sixteen bit mono little endian PCM."""
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "t.aiff"
        raw = Path(tmp) / "t.raw"
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(aiff),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "s16le",
                str(raw),
            ],
            check=True,
        )
        return raw.read_bytes()


async def one_round(persona: dict, index: int, total: int) -> bool:
    """One full call. Extracted so the reader closure binds this round's state
    rather than a loop variable, which would silently share it across rounds."""
    print(f"\n=== round {index} of {total} ===")
    seen = {"opened": False, "member_spoke": False, "tool_fired": False, "moved": False}
    transcript: list[str] = []
    audio_chunks = 0

    session = SonicSession(persona=persona)

    async def pump() -> None:
        nonlocal audio_chunks
        async for event in session.receive():
            kind = event["type"]
            if kind == "transcript" and event.get("content", "").strip():
                seen["member_spoke"] = True
                transcript.append(event["content"])
            elif kind == "audio":
                audio_chunks += 1
            elif kind == "score":
                seen["tool_fired"] = True
                states = {c["id"]: c["state"] for c in event["criteria"]}
                if any(v != "PENDING" for v in states.values()):
                    seen["moved"] = True
                print(f"  scored: {states}")
            elif kind == "error":
                print(f"  stream error: {event}")

    reader = None
    try:
        await session.open()
        seen["opened"] = True
        print("  stream open")

        reader = asyncio.create_task(pump())
        await asyncio.sleep(3.0)  # let the member open the call

        for i, line in enumerate(TURNS, 1):
            pcm = synth(line)
            print(f"  turn {i}: speaking {len(pcm) / 32000:.1f}s")
            for off in range(0, len(pcm), FRAME_BYTES):
                await session.send_audio(pcm[off : off + FRAME_BYTES])
                await asyncio.sleep(0.03)
            # Endpointing needs to HEAR the pause. Simply stopping the frames
            # leaves the model waiting forever for the turn to end.
            await session.send_silence(2.0)
            await asyncio.sleep(6.0)  # let her answer

        await asyncio.sleep(2.0)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {type(exc).__name__}: {exc}")
    finally:
        if reader:
            reader.cancel()
        await session.close()

    print(f"  audio chunks received: {audio_chunks}")
    if transcript:
        print(f"  member said: {' '.join(transcript)[:220]}")
    final = {c["id"]: c["state"] for c in session.score_state.as_payload()["criteria"]}
    print(f"  final form: {final}")

    for name, value in seen.items():
        print(f"  [{'PASS' if value else 'FAIL'}] {name}")
    ok = all(seen.values())
    print(f"  round {index}: {'PASS' if ok else 'FAIL'}")
    return ok


async def main(rounds: int) -> int:
    persona = yaml.safe_load(PERSONA.read_text())
    results = [await one_round(persona, i, rounds) for i in range(1, rounds + 1)]
    passed = sum(results)
    print(f"\n{passed} of {rounds} rounds passed")
    return 0 if passed == rounds else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.rounds)))

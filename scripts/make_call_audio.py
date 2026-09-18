"""Render the scripted call to one WAV, for Chrome's fake microphone.

Chrome can be told to answer getUserMedia from a file instead of a device:

    --use-fake-ui-for-media-stream --use-fake-device-for-media-stream
    --use-file-for-fake-audio-capture=<path>.wav

That turns the practice call into something that can be driven with no person in
the room, through the REAL browser, the REAL AudioWorklet and the REAL socket,
which is the only way a recording of it is a recording of the product rather
than of a script talking to an API.

The silences between turns are not padding. The model endpoints on silence: with
the speech butted together it hears one long utterance and answers once at the
end, and with no trailing silence it waits forever. The gaps are also where the
member actually speaks, so they have to be long enough for her to finish.

    python scripts/make_call_audio.py --out artifacts/call.wav
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.smoke_voice import SCRIPT  # noqa: E402

RATE = 16_000
LEAD_IN = 1.5  # before the first word, so the socket is up and listening
GAP = 11.0  # after each turn: the member answers here
TAIL = 4.0


def silence(seconds: float) -> bytes:
    return bytes(int(RATE * seconds) * 2)  # sixteen bit mono


def synthesise(line: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "l.aiff"
        raw = Path(tmp) / "l.raw"
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
                str(RATE),
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "call.wav")
    ap.add_argument("--gap", type=float, default=GAP)
    a = ap.parse_args()

    chunks = [silence(LEAD_IN)]
    marks = []
    for label, text in SCRIPT:
        audio = synthesise(text)
        at = sum(len(c) for c in chunks) / (RATE * 2)
        marks.append((label, at, len(audio) / (RATE * 2)))
        chunks.append(audio)
        chunks.append(silence(a.gap))
    chunks.append(silence(TAIL))

    pcm = b"".join(chunks)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(a.out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)

    total = len(pcm) / (RATE * 2)
    print(f"  wrote {a.out}  {total:.1f}s, {len(pcm):,d} bytes, {RATE} Hz mono")
    for label, at, dur in marks:
        print(f"    {at:6.1f}s  {label:12s} speaks for {dur:.1f}s")

    if total < 30:
        print("FAIL  the call is implausibly short")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

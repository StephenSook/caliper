"""Record and verify the backup demo.

The live practice call is the strongest thing in the presentation and it is the
thing most likely to fail in a strange room: a conference network, an open room
microphone, an expired credential. A recording is the insurance, and it is only
insurance if it is one keypress away and known good.

"Known good" is the whole point of this script. A recording is not verified by
the file existing, by ffmpeg exiting zero, or by someone glancing at the first
frame. Every perceptual channel the artifact has gets measured:

    both streams present        an audio only or video only file plays as broken
    duration                    a capture that stopped early looks complete in a
                                file listing
    resolution                  a projector is unforgiving about 480p
    frames are not blank        a screen capture denied by macOS privacy records
                                a perfectly valid black video and reports success
    integrated loudness         narration at -37 LUFS is inaudible in a room, and
                                this has actually shipped on a previous project

Audio comes from the built in microphone rather than a loopback device, because
none is installed. With the laptop speakers on that captures both halves of the
conversation as a person in the room hears them, which is what the recording is
standing in for.

    python scripts/record_backup_demo.py record --seconds 150
    python scripts/record_backup_demo.py verify artifacts/backup-demo.mp4
    python scripts/record_backup_demo.py normalise artifacts/backup-demo.mp4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "backup-demo.mp4"

# EBU R128. Streaming platforms land around -14; -16 is comfortable for speech
# played into a room. Outside this band the recording is either inaudible at the
# back or clipping at the front.
LUFS_MIN, LUFS_MAX = -17.0, -13.0
MIN_WIDTH, MIN_HEIGHT = 1280, 720

# A frame is "blank" if its luma barely varies. A denied screen capture produces
# a perfectly valid file of solid black, and a solid colour has a luma range of
# almost nothing. This uses YMIN and YMAX rather than a standard deviation
# because ffmpeg 8's signalstats does not expose YSTD, and reading a key that is
# not there returned None for every frame, which the check then reported as
# "0 sampled" rather than as a pass. That is the right failure and it is how the
# bug was found, but the check is only useful once it measures something.
MIN_LUMA_RANGE = 24.0


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise SystemExit(f"ffprobe failed on {path}:\n{r.stderr.strip()}")
    return json.loads(r.stdout)


def record(seconds: int, out: Path, screen: str, mic: str) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        # Never silently overwrite a take. A previous good recording is the
        # thing this whole script exists to protect.
        keep = out.with_name(f"{out.stem}-previous{out.suffix}")
        out.replace(keep)
        print(f"  moved the existing take to {keep.name}")

    print(f"  recording {seconds}s of screen {screen} and audio device {mic}")
    print("  run the demo now")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "avfoundation",
        "-capture_cursor",
        "1",
        "-framerate",
        "30",
        "-i",
        f"{screen}:{mic}",
        "-t",
        str(seconds),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("  ffmpeg failed:")
        print("  " + "\n  ".join(proc.stderr.strip().splitlines()[-12:]))
        return 1
    print(f"  wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


def loudness(path: Path) -> float | None:
    """Integrated loudness in LUFS, measured with the R128 filter."""
    r = run(
        ["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"]
    )
    integrated = None
    for line in r.stderr.splitlines():
        s = line.strip()
        if s.startswith("I:") and "LUFS" in s:
            integrated = float(s.split()[1])
    return integrated


def frame_luma_range(path: Path, at: float) -> float | None:
    """Spread between the darkest and brightest luma in one frame.

    Near zero means a blank frame: solid black from a denied screen capture, or
    solid white from a page that never painted.
    """
    r = run(
        [
            "ffmpeg",
            "-nostats",
            "-ss",
            str(at),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "signalstats,metadata=print",
            "-f",
            "null",
            "-",
        ]
    )
    lo = hi = None
    for line in r.stderr.splitlines():
        if "lavfi.signalstats.YMIN=" in line:
            lo = float(line.split("=")[-1])
        elif "lavfi.signalstats.YMAX=" in line:
            hi = float(line.split("=")[-1])
    return None if lo is None or hi is None else hi - lo


def verify(path: Path, expect_seconds: float | None) -> int:
    if not path.exists():
        print(f"FAIL  {path} does not exist")
        return 1

    info = probe(path)
    streams = info["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)

    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
        if not ok:
            failures += 1

    check("video stream present", video is not None)
    check("audio stream present", audio is not None, "an audio only or video only file plays as broken")
    if video is None:
        return 1

    w, h = int(video["width"]), int(video["height"])
    check("resolution", w >= MIN_WIDTH and h >= MIN_HEIGHT, f"{w}x{h}")

    duration = float(info["format"]["duration"])
    if expect_seconds is not None:
        check(
            "duration",
            abs(duration - expect_seconds) <= max(3.0, expect_seconds * 0.05),
            f"{duration:.1f}s, expected about {expect_seconds}s",
        )
    else:
        check("duration is not trivial", duration >= 10.0, f"{duration:.1f}s")

    # Sample across the whole thing rather than only the opening. A capture that
    # died a third of the way in has a perfectly good first frame.
    sampled = 0
    blank = []
    for fraction in (0.08, 0.3, 0.5, 0.72, 0.92):
        at = duration * fraction
        spread = frame_luma_range(path, at)
        if spread is None:
            continue
        sampled += 1
        if spread < MIN_LUMA_RANGE:
            blank.append(f"{at:.0f}s(range={spread:.0f})")
    check(
        "frames carry an image",
        sampled >= 4 and not blank,
        f"{sampled} sampled" + (f", blank at {', '.join(blank)}" if blank else ""),
    )

    if audio is not None:
        lufs = loudness(path)
        if lufs is None:
            check("integrated loudness measured", False, "the R128 filter returned nothing")
        else:
            check(
                "integrated loudness",
                LUFS_MIN <= lufs <= LUFS_MAX,
                f"{lufs:.1f} LUFS, want {LUFS_MIN} to {LUFS_MAX}"
                + ("  (run: normalise)" if not (LUFS_MIN <= lufs <= LUFS_MAX) else ""),
            )

    print(f"\n{'verified' if failures == 0 else str(failures) + ' check(s) failed'}")
    return 1 if failures else 0


def normalise(path: Path) -> int:
    """Two pass loudnorm to the middle of the band, then re verify."""
    out = path.with_name(f"{path.stem}-normalised{path.suffix}")
    target = (LUFS_MIN + LUFS_MAX) / 2

    r = run(
        [
            "ffmpeg",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    blob = r.stderr[r.stderr.rfind("{") : r.stderr.rfind("}") + 1]
    try:
        m = json.loads(blob)
    except json.JSONDecodeError:
        print("FAIL  could not read the measurement pass")
        return 1

    r2 = run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-c:v",
            "copy",
            "-af",
            f"loudnorm=I={target}:TP=-1.5:LRA=11:"
            f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(out),
        ]
    )
    if r2.returncode != 0:
        print("FAIL  the normalise pass failed:")
        print("  " + "\n  ".join(r2.stderr.strip().splitlines()[-8:]))
        return 1
    print(f"  wrote {out}")
    return verify(out, None)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record")
    rec.add_argument("--seconds", type=int, default=150)
    rec.add_argument("--out", type=Path, default=DEFAULT_OUT)
    rec.add_argument("--screen", default="3", help="avfoundation video device index")
    rec.add_argument("--mic", default="1", help="avfoundation audio device index")

    ver = sub.add_parser("verify")
    ver.add_argument("path", type=Path, nargs="?", default=DEFAULT_OUT)
    ver.add_argument("--seconds", type=float, default=None)

    nor = sub.add_parser("normalise")
    nor.add_argument("path", type=Path, nargs="?", default=DEFAULT_OUT)

    a = p.parse_args()
    if a.cmd == "record":
        rc = record(a.seconds, a.out, a.screen, a.mic)
        return rc or verify(a.out, float(a.seconds))
    if a.cmd == "verify":
        return verify(a.path, a.seconds)
    return normalise(a.path)


if __name__ == "__main__":
    sys.exit(main())

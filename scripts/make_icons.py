"""Generate the CALIPER app icons.

The mark is the finding, drawn: a confidence interval whose lower bound crosses
the zero line. That is literally what CALIPER found in all three quality forms,
it is a glyph a measurement person recognises on sight, and it survives being
drawn at 32 pixels on a home screen.

An earlier attempt drew a pair of caliper jaws. It read as the letter H at small
sizes, so it was cut. Everything here is drawn as rectangles rather than as
strokes, because PIL's line primitive does no antialiasing at all and its stair
steps survive the downsample; axis aligned rectangles supersampled 8x and
resampled with Lanczos come out clean.

Three families are emitted because the platforms want different things:

  icon-<n>.png            the plain mark, used by the manifest
  icon-maskable-<n>.png   the same mark inset into the 80 percent safe zone,
                          because Android crops a maskable icon to whatever
                          shape the launcher prefers
  apple-touch-icon.png    180 square and fully opaque, because iOS composites a
                          transparent icon onto black and rounds it itself

Run: python scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

INK = (10, 11, 13, 255)  # --ink-900
SIGNAL = (74, 222, 154, 255)  # --signal
PAPER = (231, 231, 227, 255)
DIM = (124, 127, 135, 255)  # --paper-500

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public"

SUPERSAMPLE = 8


def draw_mark(size: int, inset: float = 0.0, opaque_bg: bool = True) -> Image.Image:
    """Draw the interval mark.

    inset shrinks the mark toward the centre so a launcher mask cannot clip it.
    """
    s = size * SUPERSAMPLE
    img = Image.new("RGBA", (s, s), INK if opaque_bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    lo, hi = inset, 1.0 - inset
    span = hi - lo

    def f(v: float) -> float:
        """Fraction of the whole canvas, after the inset is applied."""
        return (lo + v * span) * s

    def bar(x0: float, y0: float, x1: float, y1: float, fill) -> None:
        d.rectangle([f(x0), f(y0), f(x1), f(y1)], fill=fill)

    heavy = 0.052  # the interval bar and its end caps
    light = 0.022  # the zero reference

    mid = 0.5
    left, right = 0.175, 0.825
    cap_top, cap_bot = 0.300, 0.700

    # The zero reference, drawn first so the interval sits on top of it. It runs
    # the full height of the mark rather than only the height of the caps, so it
    # reads as an axis rather than as a third tick.
    bar(mid - light / 2, 0.140, mid + light / 2, 0.860, DIM)

    # The interval itself.
    bar(left, mid - heavy / 2, right, mid + heavy / 2, SIGNAL)

    # End caps. These are what make it an interval rather than an underline.
    for x in (left, right):
        bar(x, cap_top, x + heavy, cap_bot, SIGNAL)

    # The point estimate, offset to the positive side so the mark is
    # asymmetric and therefore obviously a measurement rather than a logo.
    est = 0.605
    bar(est - heavy * 0.72, mid - heavy * 1.55, est + heavy * 0.72, mid + heavy * 1.55, PAPER)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for n in (192, 512):
        p = OUT / f"icon-{n}.png"
        draw_mark(n).save(p)
        written.append(p)

        # Android crops a maskable icon; the spec guarantees only the middle
        # 80 percent survives, so the mark is inset by a tenth on every side.
        p = OUT / f"icon-maskable-{n}.png"
        draw_mark(n, inset=0.10).save(p)
        written.append(p)

    p = OUT / "apple-touch-icon.png"
    draw_mark(180, inset=0.05, opaque_bg=True).save(p)
    written.append(p)

    for path in written:
        rel = str(path.relative_to(OUT.parents[1]))
        print(f"  {rel:44s} {path.stat().st_size:>7,d} bytes")

    if len(written) != 5:
        raise SystemExit(f"expected 5 icons, wrote {len(written)}")


if __name__ == "__main__":
    main()

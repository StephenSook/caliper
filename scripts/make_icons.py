"""Generate the CALIPER app icons.

The mark has to do two jobs at once. It has to say "precision measuring
instrument" to somebody glancing at a home screen, and it has to survive being
drawn at sixty pixels, which is a geometry problem rather than a rendering one.
An icon is not a small illustration; it is a silhouette that still reads when
almost all of the detail is gone.

So the mark is a caliper closing on a measured gap: two heavy jaws facing each
other, tapering to tips, with a bright interval between them carrying end caps.
The jaws are the instrument and the interval is what it found. That is the whole
product in one glyph, and it is the sentence the project is named for.

Two earlier attempts are worth recording, because each failed for a reason that
is easy to repeat. Caliper jaws drawn as square brackets read as the letter H at
small sizes. A bare confidence interval read correctly to a statistician and as
nothing at all to anyone else.

Everything is drawn as filled polygons rather than strokes, supersampled eight
times and resampled with Lanczos: PIL's line primitive does no antialiasing and
its stair steps survive the downsample.

Three families, because the platforms want different things:

  icon-<n>.png            the plain mark, used by the web manifest
  icon-maskable-<n>.png   inset into the 80 percent safe zone Android guarantees
  apple-touch-icon.png    180 square and fully opaque, because iOS composites a
                          transparent icon onto black and rounds it itself

Run: python scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

INK = (10, 11, 13, 255)  # --ink-900
SIGNAL = (74, 222, 154, 255)  # --signal
PAPER = (247, 247, 245, 255)
GLOW = (74, 222, 154, 70)

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public"
SUPERSAMPLE = 8


def draw_mark(size: int, inset: float = 0.0, opaque_bg: bool = True) -> Image.Image:
    """Draw the caliper mark.

    `inset` shrinks the mark toward the centre so a launcher mask cannot clip it.
    """
    s = size * SUPERSAMPLE
    img = Image.new("RGBA", (s, s), INK if opaque_bg else (0, 0, 0, 0))

    lo, hi = inset, 1.0 - inset
    span = hi - lo

    def f(v: float) -> float:
        return (lo + v * span) * s

    # ---- the caliper ------------------------------------------------------
    #
    # The actual object, not an abstraction of it. A beam across the top with
    # two jaws hanging from it, one fixed at the end and one part way along, and
    # the gap between the jaw tips is the measurement.
    #
    # Two earlier versions drew symmetric tapering wedges. Both read as a solid
    # letter M or a bowtie, because a symmetric filled shape says "mass" and a
    # caliper is defined by its asymmetry: one jaw is fixed and one slides. Ten
    # seconds with the real object settles what ten minutes of abstraction did
    # not.
    glow_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    d = ImageDraw.Draw(img)

    beam_y = 0.255
    beam_h = 0.062
    # The beam overhangs the sliding jaw, because on a real caliper that is the
    # scale. It overhung much further in the first pass and the silhouette read
    # as a torii gate, so the overhang is now just enough to say "there is more
    # scale here" without becoming the subject.
    beam_x0, beam_x1 = 0.130, 0.800

    jaw_w = 0.082
    jaw_bottom = 0.790
    fixed_x = 0.170  # the fixed jaw, at the end of the beam
    slide_x = 0.520  # the sliding jaw, part way along: the asymmetry IS the tool

    def rect(x0: float, y0: float, x1: float, y1: float, fill, glow=True) -> None:
        box = [f(x0), f(y0), f(x1), f(y1)]
        d.rectangle(box, fill=fill)
        if glow:
            gd.rectangle(box, fill=GLOW)

    rect(beam_x0, beam_y, beam_x1, beam_y + beam_h, SIGNAL)
    rect(fixed_x, beam_y, fixed_x + jaw_w, jaw_bottom, SIGNAL)
    rect(slide_x, beam_y, slide_x + jaw_w, jaw_bottom, SIGNAL)

    # The sliding jaw is wider where it meets the beam, which is where the thumb
    # goes. It is what stops the two jaws reading as an interchangeable pair.
    # A first version put this block ABOVE the beam and the mark turned into a
    # letter T, so it sits flush instead.
    rect(slide_x - 0.026, beam_y, slide_x + jaw_w + 0.026, beam_y + beam_h * 2.1, SIGNAL)

    # ---- the measured gap -------------------------------------------------
    #
    # Paper rather than signal, so the eye reads the instrument first and the
    # measurement second, which is the order the product argues for.
    gap_left = fixed_x + jaw_w
    gap_right = slide_x
    mid = 0.630
    bar = 0.030
    d.rectangle([f(gap_left), f(mid - bar / 2), f(gap_right), f(mid + bar / 2)], fill=PAPER)

    cap = 0.150
    cap_w = 0.026
    for cx in (gap_left, gap_right):
        d.rectangle(
            [f(cx) - cap_w * s / 2, f(mid - cap / 2), f(cx) + cap_w * s / 2, f(mid + cap / 2)],
            fill=PAPER,
        )

    # A soft bloom behind the jaws. Subtle on purpose: enough to make the mark
    # feel lit rather than printed, not enough to survive as a blur at 60px.
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=s * 0.018))
    img = (
        Image.alpha_composite(glow_layer, img)
        if opaque_bg is False
        else Image.alpha_composite(Image.alpha_composite(Image.new("RGBA", (s, s), INK), glow_layer), img)
    )

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for n in (192, 512):
        p = OUT / f"icon-{n}.png"
        draw_mark(n).save(p)
        written.append(p)
        p = OUT / f"icon-maskable-{n}.png"
        draw_mark(n, inset=0.11).save(p)
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

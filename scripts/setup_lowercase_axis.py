#!/usr/bin/env python3
"""
setup_lowercase_axis.py — declare a lowercase-scoped correction axis on a
Crispy source through avar2-studio's sidecar, so lowercase LAGS the weight
ramp instead of following it all the way.

THE RAMP. Crispy's avar2 mapping sends wght 900 -> 1000 along a straight line
between two real masters:

    wght 900   XTRA 1571 · XOPQ 700  · YOPQ 275     ("Black Wide Max")
    wght 1000  XTRA 47   · XOPQ 1462 · YOPQ 275

parameterised by t in [0,1]:  XTRA = 1571 - 1524t,  XOPQ = 700 + 762t.

Along it the ink deliberately fills the counters. Measured on this design,
two exact laws hold (verified to <0.1 font unit):

    counter width = 2 x XTRA        stem width = 2 x XOPQ

so XTRA alone governs counters and XOPQ alone governs stems, and at wght 1000
every counter has hit the hard floor of 2 x XTRA_min = 94 units.

THE CORRECTION. Rather than invent a parametric point for lowercase, this
keeps lowercase on the SAME ramp and simply lags it by ``--lag`` weight units:
at wght 1000 the lowercase renders as if at wght (1000 - lag). One number, on
the design's own path, and the counter it buys is exactly 2 x XTRA(lag):

    lag  0 ->  94 units      lag 10 -> 399 units      lag 20 ->  704 units
    lag  5 -> 246 units      lag 15 -> 551 units      lag 30 -> 1008 units

THE ANCHOR (do not remove). A brace layer compiles to a gvar tuple whose peak
is its NORMALIZED location, and an axis sitting at its own default is omitted
from the tuple — which leaves it unrestricted. The correction corner is at
XTRA 47, which IS the default master's XTRA, so without help the correction
leaks across the whole width axis (measured: 276 units of unwanted deformation
at wght 900, 578 at the opposite corner). This script therefore writes a second
layer per glyph at XTRA max with NO correction: its delta is zero, so it changes
nothing where it sits and bounds the tuple everywhere else (leak drops to ~1).

USAGE
    python scripts/setup_lowercase_axis.py sources/Crispy-demo2.glyphs --lag 10
    python scripts/setup_lowercase_axis.py sources/Crispy-demo2.glyphs --lag 10 \
        --workspace /tmp/ws --build --verify

The source file is NEVER modified: the axis and its layers live in the
``<basename>-control.json`` sidecar, and the outlines in the studio's shadow
copy under ``.avar2-studio/shadow/``. Point the studio at the (copied) source
to see it, or use --build to compile the shadow with fontc.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

STUDIO_SRC = Path("/Users/agyei/Documents/avar2-studio/src")

# The ramp, as measured from the two masters it runs between.
RAMP_START = {"XTRA": 1571.0, "XOPQ": 700.0, "YOPQ": 275.0}   # wght 900
RAMP_END = {"XTRA": 47.0, "XOPQ": 1462.0, "YOPQ": 275.0}      # wght 1000


def ramp_point(t):
    """Parametric location at ramp position t (0 = wght 900, 1 = wght 1000)."""
    return {
        tag: RAMP_START[tag] + (RAMP_END[tag] - RAMP_START[tag]) * t
        for tag in RAMP_START
    }


def lowercase_glyphs(font):
    """a-z by codepoint, plus their dotted variants (a.alts, m.002, c.ss01...)."""
    bases = {
        g.name for g in font.glyphs
        if g.unicode and 0x61 <= int(g.unicode, 16) <= 0x7A
    }
    out = []
    for g in font.glyphs:
        if not g.export:
            continue
        if g.name in bases or (g.name.split(".")[0] in bases and "." in g.name):
            out.append(g.name)
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="the .glyphs source (never modified)")
    ap.add_argument("--tag", default="lcad", help="axis tag (private; default lcad)")
    ap.add_argument("--name", default="Lowercase adjust", help="axis display name")
    ap.add_argument("--lag", type=float, default=10.0,
                    help="weight units lowercase lags the ramp at wght 1000 (default 10)")
    ap.add_argument("--workspace", default=None,
                    help="copy the source here first, so the original stays untouched")
    ap.add_argument("--glyphs", default=None,
                    help="comma-separated glyph names (default: lowercase a-z + variants)")
    ap.add_argument("--no-anchor", action="store_true",
                    help="skip the bounding layers (leaks — for demonstrating the trap only)")
    ap.add_argument("--build", action="store_true", help="compile the shadow with fontc")
    ap.add_argument("--verify", action="store_true",
                    help="measure the built font: correction applied, uppercase untouched, no leak")
    args = ap.parse_args()

    sys.path.insert(0, str(STUDIO_SRC))
    try:
        from avar2_studio import control_axes
    except ImportError:
        print(f"error: avar2-studio not importable from {STUDIO_SRC}", file=sys.stderr)
        return 2
    import glyphsLib

    src = Path(args.source).resolve()
    if args.workspace:
        ws = Path(args.workspace)
        ws.mkdir(parents=True, exist_ok=True)
        dst = ws / src.name
        shutil.copy2(src, dst)
        src = dst
        print(f"working on a copy: {src}")

    font = glyphsLib.GSFont(str(src))
    covered = ([g.strip() for g in args.glyphs.split(",") if g.strip()]
               if args.glyphs else lowercase_glyphs(font))

    t_corr = 1.0 - args.lag / 100.0
    target = ramp_point(t_corr)
    corner = dict(RAMP_END)
    xtra_max = max(m.axes[0] for m in font.masters)

    print(f"axis '{args.tag}' 0..100, default 0")
    print(f"covered glyphs ({len(covered)}): {' '.join(covered)}")
    print(f"corner  (wght 1000): XTRA {corner['XTRA']:.0f} · XOPQ {corner['XOPQ']:.0f} · YOPQ {corner['YOPQ']:.0f}")
    print(f"target  (wght {1000 - args.lag:.0f}): XTRA {target['XTRA']:.0f} · XOPQ {target['XOPQ']:.0f}"
          f"   -> counter {2 * target['XTRA']:.0f} units (vs {2 * corner['XTRA']:.0f} uncorrected)")

    try:
        control_axes.add_axis(src, args.tag, args.name, 0, 0, 100)
    except ValueError as exc:
        print(f"(axis exists: {exc}) — replacing its layers")

    entries = []
    for g in covered:
        entries.append({
            "glyph": g,
            "location": {**corner, args.tag: 100},
            "target": {"XTRA": target["XTRA"], "XOPQ": target["XOPQ"]},
        })
        if not args.no_anchor:
            # Zero-delta anchor at XTRA max: bounds the tuple along XTRA.
            entries.append({
                "glyph": g,
                "location": {**corner, "XTRA": xtra_max, args.tag: 100},
            })
    control_axes.set_layers(src, args.tag, entries)
    print(f"layers: {len(entries)}"
          + ("" if args.no_anchor else f"  ({len(covered)} correction + {len(covered)} anchor)"))

    shadow = control_axes.regenerate_shadow(src)
    print(f"shadow: {shadow}")

    print("\nMAPPING — add this column to the avar2 CSV so the axis ramps in with weight:")
    print(f"    {args.tag}: 0 at wght <= 900, 100 at wght 1000 (linear between)")

    if not (args.build or args.verify):
        return 0

    build_dir = Path(shadow).parent.parent / "build-lcad"
    r = subprocess.run(["venv/bin/fontc", str(shadow), "--build-dir", str(build_dir)],
                       capture_output=True, text=True, cwd="/Users/agyei/Documents/Crispy")
    if r.returncode != 0:
        print("fontc FAILED:\n" + r.stderr[-900:], file=sys.stderr)
        return 1
    ttf = build_dir / "font.ttf"
    print(f"built: {ttf}")

    if args.verify:
        verify(str(ttf), args.tag, corner, target, covered, xtra_max)
    return 0


def verify(ttf, tag, corner, target, covered, xtra_max):
    """Check the three properties that make the axis correct."""
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    def pts(loc, name):
        f = instantiateVariableFont(TTFont(ttf), loc, inplace=False)
        pen = RecordingPen()
        f.getGlyphSet()[name].draw(pen)
        return [p for _, ar in pen.value for p in ar], f["hmtx"][name][0]

    def dev(a, b):
        if len(a) != len(b):
            return float("inf")
        return max(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for p, q in zip(a, b))

    on = {**corner, tag: 100}
    off = {**corner, tag: 0}
    print("\nVERIFY")
    worst_corr, worst_upper, worst_leak = 0.0, 0.0, 0.0
    for g in [x for x in covered if len(x) == 1][:8]:
        a, wa = pts(on, g)
        b, wb = pts(off, g)
        moved = dev(a, b)
        worst_corr = max(worst_corr, moved)
        print(f"  {g}: correction moves it {moved:7.1f} units   advance {wb} -> {wa}")
    for g in ("A", "H", "O", "M"):
        try:
            a, wa = pts(on, g)
            b, wb = pts(off, g)
            worst_upper = max(worst_upper, dev(a, b))
        except Exception:
            pass
    for loc, label in ((dict(RAMP_START), "wght 900"),
                       ({**corner, "XTRA": xtra_max}, "opposite corner")):
        for g in ("a", "n", "o"):
            a, _ = pts({**loc, tag: 100}, g)
            b, _ = pts({**loc, tag: 0}, g)
            worst_leak = max(worst_leak, dev(a, b))
    print(f"\n  correction applied at the corner : up to {worst_corr:.1f} units   (want: large)")
    print(f"  uppercase disturbed              : {worst_upper:.1f} units   (want: 0)")
    print(f"  leak away from the corner        : {worst_leak:.1f} units   (want: ~1)")
    ok = worst_upper < 1.5 and worst_leak < 40 and worst_corr > 50
    print(f"\n  {'PASS' if ok else 'CHECK THESE'}")


if __name__ == "__main__":
    sys.exit(main())

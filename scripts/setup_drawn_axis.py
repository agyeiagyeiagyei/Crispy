#!/usr/bin/env python3
"""
setup_drawn_axis.py — declare a glyph-scoped secondary axis whose layers are
DRAWN BY HAND in Fontra, not computed.

This is the counterpart to setup_lowercase_axis.py. That one writes a
``target`` on each layer, so the outline is computed as the glyph interpolated
somewhere else and is re-derived on every rebuild. This one writes PLAIN layers:
each is seeded with the glyph's natural shape at that location, so the axis is a
no-op until you open the layer in Fontra and draw. Use it when the correction is
a drawing decision the parametric axes cannot express — e.g. thickening the
horizontals of E e s S B K, which are more contrasted than their neighbours
through the light-to-regular range.

WHERE TO PUT THE POINTS. A brace layer's influence is a tent peaking at its own
location and falling to zero at the neighbouring masters, so the axis has full
authority only near the points you choose. Pick them where the problem is worst;
measure first rather than guessing.

THE ANCHOR. A gvar tuple omits any axis whose normalized peak is 0 — i.e. any
axis sitting at its default, which is the default master's coordinate. An
omitted axis is unrestricted, so a layer authored at such a point bleeds across
that whole axis. Where that happens this script adds a zero-delta anchor layer
at the axis maximum to bound it. LEAVE ANCHOR LAYERS UNDRAWN: their job is to be
identical to the natural shape.

OUTLINES LIVE IN THE SHADOW. Drawn outlines are stored in the studio's shadow
copy under ``.avar2-studio/shadow/``, not in the sidecar and not in your source.
Deleting ``.avar2-studio/`` loses them. Keep backups of that directory once you
have drawing invested in it.

Usage:
    python scripts/setup_drawn_axis.py sources/Crispy-demo2.glyphs \\
        --tag ymod --name "Horizontal correction" \\
        --glyphs "E,e,s,S,B,K" \\
        --at "XTRA=1715,XOPQ=263,YOPQ=104" \\
        --at "XTRA=47,XOPQ=117,YOPQ=86"
"""
import argparse
import sys
from pathlib import Path

STUDIO_SRC = Path("/Users/agyei/Documents/avar2-studio/src")


def parse_loc(text):
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        tag, _, val = part.partition("=")
        out[tag.strip()] = float(val)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--tag", required=True, help="axis tag (4 chars, private)")
    ap.add_argument("--name", default=None, help="axis display name")
    ap.add_argument("--glyphs", required=True, help="comma-separated glyph names, e.g. 'E,e,s,S,B,K'")
    ap.add_argument("--at", action="append", required=True, metavar="LOC",
                    help="a parametric location to author a layer at, e.g. "
                         "'XTRA=1715,XOPQ=263,YOPQ=104'. Repeat for each point.")
    ap.add_argument("--min", type=float, default=0)
    ap.add_argument("--max", type=float, default=100)
    ap.add_argument("--default", type=float, default=0)
    ap.add_argument("--workspace", default=None, help="copy the source here first")
    ap.add_argument("--no-anchor", action="store_true", help="skip the bounding layers")
    args = ap.parse_args()

    sys.path.insert(0, str(STUDIO_SRC))
    try:
        from avar2_studio import control_axes
    except ImportError:
        print(f"error: avar2-studio not importable from {STUDIO_SRC}", file=sys.stderr)
        return 2
    import glyphsLib
    import shutil

    src = Path(args.source).resolve()
    if args.workspace:
        ws = Path(args.workspace)
        ws.mkdir(parents=True, exist_ok=True)
        dst = ws / src.name
        shutil.copy2(src, dst)
        src = dst
        print(f"working on a copy: {src}")

    font = glyphsLib.GSFont(str(src))
    tags = [a.axisTag for a in font.axes]
    names = {g.name for g in font.glyphs}
    glyphs = [g.strip() for g in args.glyphs.split(",") if g.strip()]
    missing = [g for g in glyphs if g not in names]
    if missing:
        print(f"error: not in the font: {', '.join(missing)}", file=sys.stderr)
        return 2

    # The default master's coordinate on each axis == that axis's fvar default,
    # which is the value that makes a tuple omit the axis.
    defaults = {t: font.masters[0].axes[i] for i, t in enumerate(tags)}
    maxima = {t: max(m.axes[i] for m in font.masters) for i, t in enumerate(tags)}

    locations = [parse_loc(a) for a in args.at]
    # Fill unspecified axes with their default so each layer is a full N-D point.
    for loc in locations:
        for t in tags:
            loc.setdefault(t, defaults[t])

    try:
        control_axes.add_axis(src, args.tag, args.name or args.tag,
                              args.default, args.min, args.max)
    except ValueError as exc:
        print(f"(axis exists: {exc}) — replacing its layers")

    entries = []
    anchors_for = []
    for loc in locations:
        unpinned = [t for t in tags
                    if loc[t] == defaults[t] and maxima[t] > defaults[t]]
        for g in glyphs:
            entries.append({"glyph": g, "location": {**loc, args.tag: args.max}})
        if unpinned and not args.no_anchor:
            anchors_for.append((loc, unpinned))
            for t in unpinned:
                for g in glyphs:
                    entries.append({"glyph": g,
                                    "location": {**loc, t: maxima[t], args.tag: args.max}})

    control_axes.set_layers(src, args.tag, entries)

    print(f"\naxis '{args.tag}' {args.min}..{args.max} default {args.default}")
    print(f"glyphs ({len(glyphs)}): {' '.join(glyphs)}")
    print(f"\nDRAW AT THESE {len(locations)} POINT(S) — open each in Fontra from the studio panel:")
    for loc in locations:
        print("   " + " · ".join(f"{t} {loc[t]:g}" for t in tags) + f"  ·  {args.tag} {args.max:g}")
    if anchors_for:
        print("\nANCHOR layers added (LEAVE THESE UNDRAWN — they bound the tuple):")
        for loc, unpinned in anchors_for:
            for t in unpinned:
                pinned = " · ".join(f"{x} {maxima[t] if x==t else loc[x]:g}" for x in tags)
                print(f"   {pinned}   (bounds {t}, which sits at its default in the point above)")
    print(f"\ntotal layers: {len(entries)}  "
          f"({len(glyphs)*len(locations)} to draw, {len(entries)-len(glyphs)*len(locations)} anchors)")

    shadow = control_axes.regenerate_shadow(src)
    print(f"\nshadow: {shadow}")
    print("Layers start as the glyph's natural shape, so the axis does nothing until you draw.")
    print("Drawn outlines live ONLY in the shadow — back up .avar2-studio/ once you have work in it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

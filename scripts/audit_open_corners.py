#!/usr/bin/env python3
"""
audit_open_corners.py — find glyphs that fontc/Glyphs will reject as
"interpolation-incompatible" even though the master layers look
compatible in the edit view.

Both fontc and Glyphs' exporter run an *erase open corners* pass on every
layer before compiling. An open corner is the little self-crossing
triangle where an outline overshoots a corner; the pass collapses the two
overshoot nodes into the crossing point. When that collapse fires in some
masters but not others, the masters end up with different node counts at
compile time and the build fails — while the compatibility check in
Glyphs (which looks at the nodes as drawn) stays green.

For every exporting glyph this script runs the same erasure on each
master layer and reports the glyphs where the outcome differs, naming the
odd-one-out masters and the exact nodes that get erased there.

Usage:
    venv/bin/python scripts/audit_open_corners.py [sources/Crispy.glyphs]
"""
import sys
from collections import Counter, defaultdict

import glyphsLib
from glyphsLib.filters.eraseOpenCorners import EraseOpenCornersFilter
from ufoLib2.objects import Font as UFont


def layer_after_erasure(layer):
    """Node counts per contour and the point set after open-corner erasure."""
    ufo = UFont()
    ug = ufo.newGlyph("g")
    pen = ug.getPen()
    for path in layer.paths:
        pts = [(n.position.x, n.position.y) for n in path.nodes]
        if not pts:
            continue
        if path.closed:
            # Glyphs stores a closed contour's start node last.
            pen.moveTo(pts[-1])
            for pt in pts[:-1]:
                pen.lineTo(pt)
            pen.closePath()
        else:
            pen.moveTo(pts[0])
            for pt in pts[1:]:
                pen.lineTo(pt)
            pen.endPath()
    before = [[(p.x, p.y) for p in c] for c in ug.contours]
    EraseOpenCornersFilter(include={"g"})(ufo)
    after = [[(p.x, p.y) for p in c] for c in ug.contours]
    return before, after


def main(path):
    font = glyphsLib.GSFont(path)
    masters = {m.id: m.name for m in font.masters}
    problems = []
    for glyph in font.glyphs:
        if not glyph.export:
            continue
        results = {}
        for layer in glyph.layers:
            if layer.layerId not in masters:
                continue  # brace / backup layers don't take part here
            if any(n.type != "line" for p in layer.paths for n in p.nodes):
                # Curves need a curve-aware pen; this font is line-only.
                results = None
                break
            before, after = layer_after_erasure(layer)
            results[layer.layerId] = (tuple(len(c) for c in after), before, after)
        if not results:
            continue
        signatures = Counter(sig for sig, _, _ in results.values())
        if len(signatures) <= 1:
            continue
        majority = signatures.most_common(1)[0][0]
        odd = {mid: r for mid, r in results.items() if r[0] != majority}
        problems.append((glyph.name, majority, odd))

    if not problems:
        print("No open-corner divergence found — every glyph erases the same way in all masters.")
        return 0

    print(f"{len(problems)} glyph(s) diverge after open-corner erasure:\n")
    for name, majority, odd in problems:
        print(f"== {name}  (most masters keep {list(majority)} points per contour)")
        for mid, (sig, before, after) in odd.items():
            removed = [p for c in before for p in c if not any(p in c2 for c2 in after)]
            added = [p for c in after for p in c if not any(p in c2 for c2 in before)]
            print(f"   {masters[mid]:<32} -> {list(sig)} points   "
                  f"erased {removed} -> {added}")
        print()
    # Composites inherit the problem: fontc decomposes them, so a glyph
    # built from a diverging component fails too (and may be the one the
    # compiler names first). Nothing to fix there — fix the base glyph.
    bad = {name for name, _, _ in problems}
    dependants = defaultdict(set)
    for glyph in font.glyphs:
        for layer in glyph.layers:
            for comp in layer.components:
                if comp.name in bad:
                    dependants[comp.name].add(glyph.name)
    for base, users in sorted(dependants.items()):
        print(f"   ({base} is also used as a component by: {', '.join(sorted(users))} — fixed by fixing {base})")
    if dependants:
        print()
    print("Fix: in each named master, move the erased node pair so the corner no longer "
          "self-crosses (match the other masters), or make it cross in all masters.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sources/Crispy.glyphs"))

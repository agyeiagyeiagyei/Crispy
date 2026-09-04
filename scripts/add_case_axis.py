#!/usr/bin/env python3
"""
add_case_axis.py — add a glyph-scoped correction axis (e.g. XOLC for
lowercase) to a parametric .glyphs source as a SPARSE MASTER.

The idea: at one corner of the parametric box (say the wide-ultra corner
XTRA 1715 · XOPQ 1462 · YOPQ 1) the covered glyphs should read as if
they sat at a *different* parametric point L (say XOPQ 1100). A new
master is added at that corner with the new axis at its max, in which

  - every covered glyph is the font interpolated at L, and
  - every other glyph is a verbatim copy of the corner master,

so the axis moves only the covered glyphs, contributes nothing away from
that corner, and can be driven by an avar2 mapping column. Kerning and
the master's metrics/custom parameters are copied from the corner master.

This font is line-only, so "interpolated at L" is exact point-wise math
(fontTools' VariationModel over the master node coordinates — the same
model varLib uses, normalised against the first master as the origin,
which is Glyphs' default). Interpolating at an existing master's own
location reproduces that master bit-for-bit; --self-test checks that.

The original file is never modified: the result is written to --out.

Examples:
    venv/bin/python scripts/add_case_axis.py sources/Crispy.glyphs \
        --out sources/Crispy-xolc.glyphs --tag XOLC --name "X-Opacity lowercase" \
        --corner "XTRA=1715,XOPQ=1462,YOPQ=1" --target "XOPQ=1100"

    # several corners in one run: repeat --corner/--target in pairs
    ... --corner "XTRA=1715,XOPQ=1462,YOPQ=1"   --target "XOPQ=1100" \
        --corner "XTRA=47,XOPQ=1462,YOPQ=275"   --target "XOPQ=1150,YOPQ=275"

    # who would be covered, and does the model round-trip? no file written
    venv/bin/python scripts/add_case_axis.py sources/Crispy.glyphs --self-test --dry-run
"""
import argparse
import copy
import sys
import uuid

import glyphsLib
from fontTools.varLib.models import VariationModel, normalizeValue
from glyphsLib.classes import GSAnchor, GSAxis, GSFontMaster, GSLayer, GSNode, GSPath
from glyphsLib.types import Transform


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def parse_loc(text):
    """'XTRA=1715,XOPQ=1462' -> {'XTRA': 1715.0, 'XOPQ': 1462.0}"""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        tag, _, val = part.partition("=")
        out[tag.strip()] = float(val)
    return out


def default_covered_glyphs(font):
    """Lowercase Latin: glyphs mapped to a-z, plus their dotted variants
    (a.alts, c.ss01, m.002 ...) — the base name before the first dot."""
    bases = set()
    for g in font.glyphs:
        if g.unicode and 0x61 <= int(g.unicode, 16) <= 0x7A:
            bases.add(g.name)
    covered = []
    for g in font.glyphs:
        base = g.name.split(".")[0]
        if g.name in bases or (base in bases and "." in g.name):
            covered.append(g.name)
    return covered


def expand_glyph_list(font, text):
    """'a-z,a.alts,/idotless' or plain comma list -> glyph names present in the font."""
    names = {g.name for g in font.glyphs}
    out = []
    for token in text.split(","):
        token = token.strip().lstrip("/")
        if not token:
            continue
        if len(token) == 3 and token[1] == "-":
            for cp in range(ord(token[0]), ord(token[2]) + 1):
                ch = chr(cp)
                for g in font.glyphs:
                    if g.unicode and int(g.unicode, 16) == cp:
                        out.append(g.name)
        elif token in names:
            out.append(token)
        else:
            print(f"warning: glyph '{token}' not in font — skipped", file=sys.stderr)
    seen, uniq = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


class Interpolator:
    """VariationModel over the masters' parametric coordinates."""

    def __init__(self, font, tags):
        self.font = font
        self.tags = tags
        origin = font.masters[0]
        self.ranges = {}
        for i, tag in enumerate(tags):
            vals = [m.axes[i] for m in font.masters]
            self.ranges[tag] = (min(vals), origin.axes[i], max(vals))
        self.master_ids = [m.id for m in font.masters]
        locs = [self.normalize({t: m.axes[i] for i, t in enumerate(tags)}) for m in font.masters]
        self.model = VariationModel(locs, axisOrder=list(tags))

    def normalize(self, loc):
        return {t: normalizeValue(loc[t], self.ranges[t]) for t in self.tags if t in loc}

    def layer_vector(self, layer):
        """Flatten a layer to numbers + a structural signature for compatibility."""
        vec, sig = [], []
        for p in layer.paths:
            sig.append(("path", p.closed, tuple(n.type for n in p.nodes)))
            for n in p.nodes:
                vec.extend([n.position.x, n.position.y])
        for c in layer.components:
            sig.append(("comp", c.name))
            vec.extend(list(c.transform.value))
        for a in layer.anchors:
            sig.append(("anchor", a.name))
            vec.extend([a.position.x, a.position.y])
        vec.append(layer.width)
        return vec, tuple(sig)

    def interpolate(self, glyph, loc):
        """Return (vector, signature) of ``glyph`` at parametric ``loc``,
        or (None, reason) when the masters are not compatible."""
        vectors, sigs = [], set()
        for mid in self.master_ids:
            layer = next((l for l in glyph.layers if l.layerId == mid), None)
            if layer is None:
                return None, f"no layer for master {mid}"
            vec, sig = self.layer_vector(layer)
            vectors.append(vec)
            sigs.add(sig)
        if len(sigs) != 1:
            return None, "masters are not point-compatible"
        sig = next(iter(sigs))
        n = len(vectors[0])
        nloc = self.normalize(loc)
        out = [self.model.interpolateFromMasters(nloc, [v[i] for v in vectors]) for i in range(n)]
        return out, sig

    @staticmethod
    def apply_vector(template_layer, vec):
        """New GSLayer shaped like ``template_layer`` with coordinates from ``vec``."""
        new = GSLayer()
        i = 0
        for p in template_layer.paths:
            np_ = GSPath()
            np_.closed = p.closed
            for n in p.nodes:
                nn = GSNode((vec[i], vec[i + 1]), n.type)
                nn.smooth = n.smooth
                np_.nodes.append(nn)
                i += 2
            new.paths.append(np_)
        for c in template_layer.components:
            nc = copy.deepcopy(c)
            nc.transform = Transform(*vec[i:i + 6])
            i += 6
            new.components.append(nc)
        for a in template_layer.anchors:
            new.anchors.append(GSAnchor(a.name, (vec[i], vec[i + 1])))
            i += 2
        new.width = vec[i]
        return new


def clone_layer(layer):
    new = GSLayer()
    for p in layer.paths:
        new.paths.append(copy.deepcopy(p))
    for c in layer.components:
        new.components.append(copy.deepcopy(c))
    for a in layer.anchors:
        new.anchors.append(GSAnchor(a.name, (a.position.x, a.position.y)))
    new.width = layer.width
    return new


def find_master(font, tags, corner):
    for m in font.masters:
        if all(abs(m.axes[tags.index(t)] - v) < 1e-6 for t, v in corner.items()):
            return m
    return None


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--out", help="output .glyphs path (required unless --dry-run)")
    ap.add_argument("--tag", default="XOLC")
    ap.add_argument("--name", default=None, help="axis display name (default: tag)")
    ap.add_argument("--max", type=float, default=100.0, help="axis max; default/min are 0")
    ap.add_argument("--corner", action="append", default=[], help="master location to add the sparse master at (repeatable)")
    ap.add_argument("--target", action="append", default=[], help="parametric overrides defining L for the matching --corner (repeatable)")
    ap.add_argument("--glyphs", default=None, help="covered glyphs, e.g. 'a-z,a.alts,c.ss01' (default: lowercase a-z + dotted variants)")
    ap.add_argument("--master-name", default=None, help="name for the new master (single-corner runs)")
    ap.add_argument("--self-test", action="store_true", help="verify the model reproduces every master at its own location")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    if len(args.corner) != len(args.target):
        ap.error("--corner and --target must be given in matching pairs")
    if not args.dry_run and not args.out:
        ap.error("--out is required (or use --dry-run)")

    font = glyphsLib.GSFont(args.source)
    tags = [a.axisTag for a in font.axes]
    if args.tag in tags:
        ap.error(f"axis '{args.tag}' already exists in the source")
    interp = Interpolator(font, tags)

    covered = expand_glyph_list(font, args.glyphs) if args.glyphs else default_covered_glyphs(font)
    print(f"masters: {len(font.masters)}  axes: {tags}  origin: {font.masters[0].name}")
    print(f"covered glyphs ({len(covered)}): {' '.join(covered)}")

    # -- self-test: the model must reproduce each master exactly ------------
    if args.self_test:
        worst = 0.0
        bad = []
        for m in font.masters:
            loc = {t: m.axes[i] for i, t in enumerate(tags)}
            for name in covered:
                g = font.glyphs[name]
                vec, sig = interp.interpolate(g, loc)
                if vec is None:
                    bad.append((name, sig))
                    continue
                ref, _ = interp.layer_vector(next(l for l in g.layers if l.layerId == m.id))
                worst = max(worst, max(abs(a - b) for a, b in zip(vec, ref)))
        print(f"self-test: max deviation reproducing masters = {worst:.6f} units"
              + ("  OK" if worst < 1e-6 else "  ** MODEL DOES NOT ROUND-TRIP **"))
        if bad:
            names = sorted({n for n, _ in bad})
            print(f"self-test: {len(names)} covered glyph(s) not point-compatible across masters: {' '.join(names)}")

    if not args.corner:
        print("no --corner given; nothing to add.")
        return 0

    # -- the new axis -------------------------------------------------------
    axis = GSAxis(name=args.name or args.tag, tag=args.tag)
    font.axes.append(axis)
    for m in font.masters:
        m.axes = list(m.axes) + [0.0]
    for inst in font.instances:
        if inst.axes:
            inst.axes = list(inst.axes) + [0.0]
    for g in font.glyphs:
        for l in g.layers:
            coords = l.attributes.get("coordinates") if l.attributes else None
            if coords:
                l.attributes["coordinates"] = list(coords) + [0.0]

    # -- one sparse master per corner --------------------------------------
    report = []
    for corner_text, target_text in zip(args.corner, args.target):
        corner = parse_loc(corner_text)
        target = parse_loc(target_text)
        src = find_master(font, tags, corner)
        if src is None:
            print(f"error: no master at {corner_text}", file=sys.stderr)
            return 2
        L = {t: src.axes[i] for i, t in enumerate(tags)}
        L.update(target)

        new = GSFontMaster()
        new.id = str(uuid.uuid4()).upper()
        new.name = args.master_name or f"{src.name} {args.tag}{int(args.max)}"
        new.axes = list(src.axes[:len(tags)]) + [args.max]
        for attr in ("ascender", "capHeight", "xHeight", "descender", "italicAngle"):
            try:
                setattr(new, attr, getattr(src, attr))
            except Exception:
                pass
        for p in src.customParameters:
            new.customParameters[p.name] = copy.deepcopy(p.value)
        font.masters.append(new)
        if src.id in font.kerning:
            font.kerning[new.id] = copy.deepcopy(font.kerning[src.id])

        moved, copied, skipped = [], [], []
        for g in font.glyphs:
            src_layer = next((l for l in g.layers if l.layerId == src.id), None)
            if src_layer is None:
                continue
            if g.name in covered:
                vec, sig = interp.interpolate(g, L)
                if vec is None:
                    skipped.append((g.name, sig))
                    layer = clone_layer(src_layer)
                else:
                    layer = Interpolator.apply_vector(src_layer, vec)
                    moved.append(g.name)
            else:
                layer = clone_layer(src_layer)
                copied.append(g.name)
            layer.layerId = new.id
            layer.associatedMasterId = new.id
            g.layers.append(layer)
        report.append((new, src, L, moved, copied, skipped))

    for new, src, L, moved, copied, skipped in report:
        print(f"\nnew master '{new.name}' at {dict(zip(tags + [args.tag], new.axes))}")
        print(f"  covered glyphs rendered at L = {L}: {len(moved)}")
        print(f"  other glyphs copied from '{src.name}': {len(copied)}")
        if skipped:
            print(f"  ** {len(skipped)} covered glyph(s) copied unchanged (not interpolable): "
                  + ", ".join(f"{n} ({why})" for n, why in skipped))

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return 0
    font.save(args.out)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

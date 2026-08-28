#!/usr/bin/env python3
"""
export_studio_bundle.py — write an avar2-studio config bundle (the JSON the
studio's Config → Export produces, and Config → Import consumes) from a source
plus its control sidecar and a wght/wdth mapping.

The bundle carries everything that isn't in the .glyphs file itself:

  source.axes          the parametric axes, plus any secondary axis, with the
                       ranges the studio should show
  control_axes         the secondary axes and their brace layers, INCLUDING the
                       correction ``target`` on each layer and the zero-delta
                       anchor layers that stop the correction leaking
  avar2_csv            the mapping table: user axes (WGHT/WDTH) in, parametric
                       axes plus the secondary axis out

Reads the sidecar written by setup_lowercase_axis.py, so the layers in the
bundle are exactly the ones that were built and verified.

Usage:
    python scripts/export_studio_bundle.py sources/Crispy-adhesion.glyphs \\
        --sidecar /tmp/ws/Crispy-adhesion-control.json \\
        --out proof/Crispy-adhesion-avar2studio.json
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import glyphsLib

# The mapping recipe: (WGHT, WDTH) -> parametric coords + the secondary axis.
# Narrow tops out at the Black Narrow Max master; wide runs the ultra ramp from
# Black Wide Max to the min-XTRA/max-XOPQ corner, and the lowercase correction
# engages only on the wide rows past wght 900.
MAPPING = [
    # name,                 WGHT, WDTH, XTRA, XOPQ, YOPQ, secondary
    ("Narrow Thin",          100,  100,   47,    1,    1, 0),
    ("Narrow Regular",       400,  100,   47,  117,   86, 0),
    ("Narrow Black",         900,  100,   47,  311,  227, 0),
    ("Narrow Ultra",        1000,  100,   47,  350,  255, 0),
    ("Wide Thin",            100,  200, 1715,    1,    1, 0),
    ("Wide Regular",         400,  200, 1715,  263,  104, 0),
    ("Wide Black",           900,  200, 1571,  700,  275, 0),
    ("Wide Ultra Entry",     920,  200, 1266,  852,  275, 100),
    ("Wide Ultra",          1000,  200,   47, 1462,  275, 100),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--sidecar", required=True, help="the <basename>-control.json written by the setup script")
    ap.add_argument("--out", required=True)
    ap.add_argument("--family", default=None, help="family name (default: from the source)")
    ap.add_argument("--secondary-manual", action="store_true",
                    help="leave the secondary axis OUT of the mapping, so the font renders as "
                         "baseline by default and the axis is dialled by hand. Without this the "
                         "mapping drives it and the correction is always applied.")
    args = ap.parse_args()

    font = glyphsLib.GSFont(args.source)
    sidecar = json.loads(Path(args.sidecar).read_text())
    control_axes = sidecar.get("axes", [])
    secondary = [a["tag"] for a in control_axes]

    # Parametric axis ranges come from the masters — the studio shows these as
    # the sliders' bounds, so they must match the real designspace.
    param = []
    for i, ax in enumerate(font.axes):
        vals = [m.axes[i] for m in font.masters]
        param.append({
            "tag": ax.axisTag,
            "min": min(vals),
            "default": font.masters[0].axes[i],
            "max": max(vals),
            "has_master_coverage": True,
        })
    axes = list(param)
    for a in control_axes:
        axes.append({
            "tag": a["tag"],
            "min": a["min"],
            "default": a["default"],
            "max": a["max"],
            # A secondary axis is driven by brace layers on a subset of glyphs,
            # not by masters spanning it.
            "has_master_coverage": False,
        })

    mapped_secondary = [] if args.secondary_manual else secondary
    out_cols = [a["tag"] for a in param] + mapped_secondary
    header = "Instance Name," + ",".join(out_cols) + ",WGHT,WDTH"
    rows = [header]
    for name, wg, wd, xtra, xopq, yopq, sec in MAPPING:
        vals = [str(xtra), str(xopq), str(yopq)] + [str(sec)] * len(mapped_secondary)
        rows.append(f"{name}," + ",".join(vals) + f",{wg},{wd}")
    csv = "\n".join(rows) + "\n"

    bundle = {
        "format": "avar2-studio-config",
        "format_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "studio_version": "crispy-scripts",
        "source": {
            "family_name": args.family or Path(args.source).stem,
            "axes": axes,
            "avar2_out_columns": out_cols,
        },
        "control_axes": {"version": 1, "axes": control_axes},
        "avar2_csv": csv,
        "transforms": {"version": 1, "transforms": []},
        "grade": {"version": 1, "enabled": False, "default_pct": 0.25, "instances": []},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(bundle, indent=2) + "\n")

    n_layers = sum(len(a.get("layers") or []) for a in control_axes)
    n_corr = sum(1 for a in control_axes for l in (a.get("layers") or []) if l.get("target"))
    print(f"wrote {args.out}")
    print(f"  parametric axes : {', '.join(a['tag'] for a in param)}")
    print(f"  secondary axes  : {', '.join(secondary) or '(none)'}")
    print(f"  layers          : {n_layers} ({n_corr} correction, {n_layers - n_corr} anchor)")
    print(f"  mapping rows    : {len(MAPPING)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Give the built font Google Fonts' named instances and name table, in place.

    python scripts/fix_instances.py fonts/variable/*.ttf

gftools' ``fix_fvar_instances`` builds the grid from the GF axis registry: one
instance per registry weight stop inside the font's range, upright and, since
the font has a ``slnt`` axis, Italic at its minimum; the other axes sit at
their fvar defaults, so the font must already rest at Regular (CI builds it
with ``--default wght=400,wdth=100,opsz=144``). PostScript names are set.
``fix_nametable`` then names the font after that default: "Crispy" /
"Regular" / "Crispy-Regular" instead of the origin master's "47-1-1".
Runs after gen-stat so the names match the STAT stops (issue #52).
"""
import sys

from fontTools.ttLib import TTFont
from gftools.fix import fix_fvar_instances, fix_nametable

for path in sys.argv[1:]:
    font = TTFont(path)
    fix_fvar_instances(font)
    fix_nametable(font)
    font.save(path)
    name = font["name"]
    print(f"{path}: {len(font['fvar'].instances)} named instances")
    for inst in font["fvar"].instances:
        ps = name.getDebugName(inst.postscriptNameID) if inst.postscriptNameID != 0xFFFF else "-"
        print(f"  {name.getDebugName(inst.subfamilyNameID):18} {ps:22} "
              + " ".join(f"{t}={v:g}" for t, v in inst.coordinates.items() if t in ("wght", "slnt")))

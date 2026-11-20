"""Finish the variable font that avar2-studio builds.

The studio compiles the font with fontc and leaves three things the Google
Fonts checks reject:

- the name table is named after the default master ("Crispy 47-1-1");
- the one fvar instance sits at the axis defaults, because the config the
  studio writes spells the axis tags in lowercase and gftools'
  gen_fvar_instances matches tags case-sensitively, so every coordinate falls
  back to the default;
- the STAT table has records for wght, wdth and opsz only, named after the
  raw stops of the mapping CSV ("1", "1000", "5", "Ultra Extended"), which
  the Google Fonts axis registry does not know.

This script runs after ``avar2-studio build`` and:

- names the font after its default location. The default is a corner of the
  parametric space, not a selectable weight or width, so the style is the
  STAT name composed at the default ("Hairline SuperCondensed"): name ID 1
  is "<Family> <style>" with ID 2 "Regular" for legacy pickers, and IDs 16
  and 17 carry the family and the style. Were the default the Regular, the
  plain RIBBI names would be written instead;
- adds a named instance at the default location, named from ID 17;
- writes the named instances: the nine registered weights at wdth 100 and
  the default optical size, upright and at the slant minimum ("Italic"),
  each with a PostScript name;
- sets OS/2 usWeightClass to the wght default, the origin master;
- names the wght, wdth and opsz axes, which the studio names after their tags;
- rebuilds STAT with an axis record for every fvar axis, the registry's
  fallback values for wght, wdth and opsz, and Hairline (1) and ExtraBlack
  (1000) for the two wght stops outside the registry.

It does not move the default location and does not touch any glyph.

Usage:
    python scripts/post_build.py fonts/variable/*.ttf
"""

import sys
from pathlib import Path

from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._f_v_a_r import NamedInstance

FAMILY = "Crispy"
STYLE = "Regular"

# Google Fonts axis registry fallback names.
WEIGHTS = [
    (100, "Thin"), (200, "ExtraLight"), (300, "Light"), (400, "Regular"),
    (500, "Medium"), (600, "SemiBold"), (700, "Bold"), (800, "ExtraBold"),
    (900, "Black"),
]
WIDTHS = [
    (25, "SuperCondensed"), (50, "UltraCondensed"), (62.5, "ExtraCondensed"),
    (75, "Condensed"), (87.5, "SemiCondensed"), (100, "Normal"),
    (112.5, "SemiExpanded"), (125, "Expanded"), (150, "ExtraExpanded"),
    (200, "UltraExpanded"),
]
# Names for the stops beyond the registry's range; STAT values only, no instance.
EXTRA_WEIGHTS = [(1, "Hairline"), (1000, "ExtraBlack")]
ELIDABLE = 0x2

# The studio names the axes it creates after their tags.
AXIS_NAMES = {"wght": "Weight", "wdth": "Width", "opsz": "Optical Size"}

# Where the named instances sit on the axes that are not wght. A font with a
# slnt axis also gets the Italic set, at the axis minimum.
INSTANCE_LOCATION = {"wdth": 100}
ITALIC_AXIS = "slnt"


def _win(name, text, name_id):
    name.setName(text, name_id, 3, 1, 0x409)


def fix_weight_class(font):
    """OS/2 usWeightClass follows the wght default, the origin master."""
    wght = next((a for a in font["fvar"].axes if a.axisTag == "wght"), None)
    if wght is not None:
        font["OS/2"].usWeightClass = max(1, min(1000, int(round(wght.defaultValue))))


def default_style(font):
    """The STAT style name at the fvar defaults, from the wght and wdth values
    this script writes (opsz is never elided, so it is left out of names)."""
    defaults = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
    words = []
    for tag, table, elided in (("wght", WEIGHTS + EXTRA_WEIGHTS, 400),
                               ("wdth", WIDTHS, 100)):
        value = defaults.get(tag)
        if value is None or value == elided:
            continue
        label = next((l for v, l in table if v == value), None)
        if label is None:
            raise SystemExit(f"no STAT name for {tag}={value:g}; add it to the "
                             f"table in {__file__}")
        words.append(label)
    return " ".join(words) or STYLE


def fix_names(font):
    name = font["name"]
    style = default_style(font)
    ps_style = style.replace(" ", "")
    for axis in font["fvar"].axes:
        label = AXIS_NAMES.get(axis.axisTag)
        if label and name.getDebugName(axis.axisNameID) != label:
            axis.axisNameID = name.addMultilingualName(
                {"en": label}, windows=True, mac=False, minNameID=256)
    version_record = name.getDebugName(3) or ""
    parts = version_record.split(";")
    unique = ";".join(parts[:-1] + [f"{FAMILY}-{ps_style}"]) if len(parts) > 1 \
        else f"{FAMILY}-{ps_style}"
    _win(name, unique, 3)
    _win(name, f"{FAMILY}-{ps_style}", 6)
    name.removeNames(nameID=16)
    name.removeNames(nameID=17)
    if style == STYLE:
        _win(name, FAMILY, 1)
        _win(name, STYLE, 2)
        _win(name, f"{FAMILY} {STYLE}", 4)
    else:
        _win(name, f"{FAMILY} {style}", 1)
        _win(name, STYLE, 2)
        _win(name, f"{FAMILY} {style}", 4)
        _win(name, FAMILY, 16)
        _win(name, style, 17)


def _referenced_name_ids(font):
    """Name IDs the fvar axes and instances and STAT own, so a rebuild can drop them."""
    ids = set()
    for axis in font["fvar"].axes:
        ids.add(axis.axisNameID)
    for inst in font["fvar"].instances:
        ids.add(inst.subfamilyNameID)
        if inst.postscriptNameID != 0xFFFF:
            ids.add(inst.postscriptNameID)
    if "STAT" in font:
        stat = font["STAT"].table
        if stat.AxisValueArray:
            for value in stat.AxisValueArray.AxisValue:
                if value.Format == 4:
                    ids.add(value.ValueNameID)
                else:
                    ids.add(value.ValueNameID)
    return {i for i in ids if i >= 256}


def fix_instances(font):
    fvar = font["fvar"]
    name = font["name"]
    defaults = {a.axisTag: a.defaultValue for a in fvar.axes}
    ranges = {a.axisTag: (a.minValue, a.maxValue) for a in fvar.axes}
    fvar.instances = []
    # The default location first, named from ID 17 (or 2 when the default is
    # the Regular), as opentype/varfont/valid_default_instance_nameids asks.
    default_inst = NamedInstance()
    default_inst.coordinates = dict(defaults)
    default_inst.subfamilyNameID = 17 if name.getName(17, 3, 1, 0x409) else 2
    ps_style = default_style(font).replace(" ", "")
    default_inst.postscriptNameID = name.addMultilingualName(
        {"en": f"{FAMILY}-{ps_style}"}, windows=True, mac=False, minNameID=256)
    fvar.instances.append(default_inst)
    slants = [{}]
    if ITALIC_AXIS in ranges and ranges[ITALIC_AXIS][0] < 0:
        slants.append({ITALIC_AXIS: ranges[ITALIC_AXIS][0]})
    for slant in slants:
        for value, style in WEIGHTS:
            coords = dict(defaults)
            coords.update(INSTANCE_LOCATION)
            coords.update(slant)
            coords["wght"] = value
            if any(not ranges[t][0] <= v <= ranges[t][1] for t, v in coords.items()):
                continue
            if slant:
                style = "Italic" if style == "Regular" else f"{style} Italic"
            inst = NamedInstance()
            inst.coordinates = coords
            inst.subfamilyNameID = name.addMultilingualName(
                {"en": style}, windows=True, mac=False, minNameID=256)
            ps_name = f"{FAMILY}-{style.replace(' ', '')}"
            inst.postscriptNameID = name.addMultilingualName(
                {"en": ps_name}, windows=True, mac=False, minNameID=256)
            fvar.instances.append(inst)


def fix_stat(font):
    fvar = font["fvar"]
    name = font["name"]
    axes = []
    for ordering, axis in enumerate(fvar.axes):
        tag = axis.axisTag
        lo, hi = axis.minValue, axis.maxValue
        entry = {
            "tag": tag,
            "name": name.getDebugName(axis.axisNameID) or tag,
            "ordering": ordering,
        }
        values = []
        if tag == "wght":
            for value, label in sorted(WEIGHTS + EXTRA_WEIGHTS):
                if lo <= value <= hi:
                    item = {"value": value, "name": label}
                    if value == 400:
                        item["flags"] = ELIDABLE
                        if hi >= 700:
                            item["linkedValue"] = 700
                    values.append(item)
        elif tag == "wdth":
            for value, label in WIDTHS:
                if lo <= value <= hi:
                    item = {"value": value, "name": label}
                    if value == 100:
                        item["flags"] = ELIDABLE
                    values.append(item)
        elif tag == "opsz":
            # Optical size values are never elidable (googlefonts/STAT/opsz_not_elided).
            for value in sorted({lo, axis.defaultValue, hi}):
                values.append({"value": value, "name": f"{value:g}pt"})
        if values:
            entry["values"] = values
        axes.append(entry)
    buildStatTable(font, axes, elidedFallbackName=STYLE)


def finish(path):
    font = TTFont(path)
    stale = _referenced_name_ids(font)
    fix_weight_class(font)
    fix_names(font)
    fix_instances(font)
    fix_stat(font)
    still_used = _referenced_name_ids(font)
    for name_id in stale - still_used:
        font["name"].removeNames(nameID=name_id)
    font.save(path)
    print(f"finished {path}: {len(font['fvar'].instances)} instances, "
          f"STAT records for {len(font['fvar'].axes)} axes")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for arg in argv:
        finish(Path(arg))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

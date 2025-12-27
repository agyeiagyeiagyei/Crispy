#!/usr/bin/env python3
"""
ensure_regular_instance.py

Ensures a "Regular" named instance exists at fvar default coordinates.

CONTEXT:
    Variable fonts have no single canonical "default style name" field. Apps infer
    "Regular" by checking fvar.axes[].defaultValue against fvar.instances coordinates
    and STAT table entries. This script ensures a named instance exists at the exact
    default coordinates and is named "Regular" for maximum app compatibility.

WHY NOT STAT:
    STAT table patches are riskier (affects OS-level naming, more validation required).
    This script focuses on the minimal safe guarantee: a Regular instance at defaults.

WHAT IS SAFE:
    - Adding/modifying fvar instances does not affect outlines or interpolation
    - Reordering instances is cosmetic (first instance often shown first in UIs)
    - Name table patches (if enabled) are legacy and mostly cosmetic for variable fonts

WHAT IS NOT MODIFIED:
    - glyf/CFF2, gvar, HVAR/VVAR (outline data)
    - avar/avar2 tables (interpolation mappings)
    - STAT table (unless explicitly enabled, but not implemented here)
    - Axis defaults themselves (handled by set_axis_defaults.py)

References:
    - OpenType spec fvar table
    - fontTools fvar table documentation
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e


def find_instance_at_defaults(
    fvar,  # fontTools.ttLib.tables._f_v_a_r.table__f_v_a_r
    defaults: Dict[str, float],
    tolerance: float = 0.001,
) -> Optional[int]:
    """
    Find existing instance with coordinates matching defaults.
    
    Returns instance index or None if no match.
    Uses float tolerance for comparison to handle minor rounding.
    """
    for idx, instance in enumerate(fvar.instances):
        if len(instance.coordinates) != len(defaults):
            continue
        
        # Check all coordinates match
        matches = True
        for tag, default_val in defaults.items():
            inst_val = instance.coordinates.get(tag)
            if inst_val is None:
                matches = False
                break
            # Float-safe comparison
            if abs(float(inst_val) - float(default_val)) > tolerance:
                matches = False
                break
        
        if matches:
            return idx
    
    return None


def get_or_create_regular_name_id(
    font: TTFont,
    regular_name: str = "Regular",
) -> int:
    """
    Get nameID for "Regular" string, creating name record if missing.
    
    Returns nameID for platformID=3 (Windows), platEncID=1 (Unicode BMP), langID=0x409 (en-US).
    """
    if "name" not in font:
        raise ValueError("Font lacks name table")
    
    name_table: table__n_a_m_e = font["name"]
    
    # Check if "Regular" already exists (platformID=3, Windows Unicode)
    existing_id = name_table.getDebugName(2)  # nameID 2 is subfamily
    if existing_id == regular_name:
        # Find the actual nameID
        for record in name_table.names:
            if record.nameID == 2 and record.string == regular_name.encode('utf-16-be'):
                return record.nameID
    
    # Create new name record
    nameID = None
    for record in name_table.names:
        if record.nameID == 2:
            nameID = record.nameID
            break
    
    if nameID is None:
        # Find next available nameID (should be 2 for subfamily)
        nameID = 2
    
    # Add Windows Unicode name record
    name_table.setName(
        regular_name,
        nameID,
        3,  # platformID: Windows
        1,  # platEncID: Unicode BMP
        0x409,  # langID: en-US
    )
    
    return nameID


def ensure_regular_instance(
    font: TTFont,
    regular_name: str = "Regular",
    patch_name_table: bool = False,
) -> bool:
    """
    Ensure a Regular instance exists at fvar default coordinates.
    
    Returns True if changes were made, False otherwise.
    """
    if "fvar" not in font:
        raise ValueError("Font lacks fvar table")
    
    fvar = font["fvar"]
    
    # Build defaults dict from axes
    defaults: Dict[str, float] = {}
    axis_tags = []
    for axis in fvar.axes:
        tag = axis.axisTag
        if tag in defaults:
            raise ValueError(f"Duplicate axis tag in fvar: {tag}")
        defaults[tag] = float(axis.defaultValue)
        axis_tags.append(tag)
    
    if not defaults:
        raise ValueError("fvar table has no axes")
    
    # Find existing instance at defaults
    instance_idx = find_instance_at_defaults(fvar, defaults)
    
    # Get or create Regular nameID
    regular_nameID = get_or_create_regular_name_id(font, regular_name)
    
    changes_made = False
    
    if instance_idx is not None:
        # Instance exists at defaults - ensure it's named Regular
        instance = fvar.instances[instance_idx]
        
        if instance.subfamilyNameID != regular_nameID:
            instance.subfamilyNameID = regular_nameID
            changes_made = True
            print(f"  Renamed instance at defaults to '{regular_name}'")
    else:
        # No instance at defaults - try to find and update existing Regular
        # Look for an instance named "Regular" and update its coordinates
        regular_instance_idx = None
        for idx, inst in enumerate(fvar.instances):
            if inst.subfamilyNameID:
                try:
                    inst_name = font["name"].getDebugName(inst.subfamilyNameID)
                    if inst_name and regular_name.lower() in inst_name.lower():
                        regular_instance_idx = idx
                        break
                except:
                    pass
        
        if regular_instance_idx is not None:
            # Update existing Regular instance to match defaults
            instance = fvar.instances[regular_instance_idx]
            instance.coordinates = {tag: defaults[tag] for tag in axis_tags}
            instance.subfamilyNameID = regular_nameID
            instance_idx = regular_instance_idx
            changes_made = True
            print(f"  Updated existing '{regular_name}' instance coordinates to match defaults")
        else:
            # No Regular found - create new instance at defaults
            new_instance = type(fvar.instances[0])()  # Create instance of same type
            new_instance.subfamilyNameID = regular_nameID
            new_instance.flags = 0
            new_instance.coordinates = {tag: defaults[tag] for tag in axis_tags}
            new_instance.postscriptNameID = 0xFFFF  # Not set (will be auto-generated if needed)
            
            fvar.instances.append(new_instance)
            instance_idx = len(fvar.instances) - 1
            changes_made = True
            print(f"  Created new '{regular_name}' instance at default coordinates")
    
    # Move Regular instance to first position
    if instance_idx != 0:
        regular_instance = fvar.instances.pop(instance_idx)
        fvar.instances.insert(0, regular_instance)
        changes_made = True
        print(f"  Moved '{regular_name}' instance to first position")
    
    # Optional: Patch name table (legacy behavior)
    if patch_name_table:
        if "name" not in font:
            raise ValueError("Font lacks name table (required for --patch-name-regular)")
        
        name_table = font["name"]
        
        # Set nameID 2 (Subfamily) to "Regular"
        name_table.setName(
            regular_name,
            2,  # nameID: Subfamily
            3,  # platformID: Windows
            1,  # platEncID: Unicode BMP
            0x409,  # langID: en-US
        )
        
        # Update nameID 4 (Full name) if safe
        # Format: "Family Regular" (only if family name is known)
        family_name = name_table.getDebugName(1)  # nameID 1: Family
        if family_name:
            full_name = f"{family_name} {regular_name}"
            name_table.setName(
                full_name,
                4,  # nameID: Full name
                3,
                1,
                0x409,
            )
            changes_made = True
            print(f"  Updated name table: Subfamily='{regular_name}', Full='{full_name}'")
    
    return changes_made


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--in-font",
        type=Path,
        required=True,
        help="Input variable font TTF path",
    )
    parser.add_argument(
        "--out-font",
        type=Path,
        required=True,
        help="Output font path",
    )
    parser.add_argument(
        "--regular-name",
        type=str,
        default="Regular",
        help="Name for the default instance (default: 'Regular')",
    )
    parser.add_argument(
        "--patch-name-regular",
        action="store_true",
        help="Also patch name table nameID 2 and 4 (legacy behavior, may not affect variable UI)",
    )
    
    args = parser.parse_args()
    
    if not args.in_font.exists():
        print(f"Error: Input font not found: {args.in_font}", file=sys.stderr)
        return 1
    
    try:
        font = TTFont(str(args.in_font))
        
        print(f"Ensuring '{args.regular_name}' instance at default coordinates...")
        print()
        
        # Show current defaults
        if "fvar" in font:
            fvar = font["fvar"]
            defaults = {axis.axisTag: float(axis.defaultValue) for axis in fvar.axes}
            print("Current axis defaults:")
            for tag in sorted(defaults.keys()):
                print(f"  {tag}: {defaults[tag]}")
            print()
        
        changes_made = ensure_regular_instance(
            font,
            regular_name=args.regular_name,
            patch_name_table=args.patch_name_regular,
        )
        
        if changes_made:
            print()
            print(f"✓ Saving patched font to {args.out_font}")
            font.save(str(args.out_font))
        else:
            print()
            print("✓ No changes needed (Regular instance already exists at defaults)")
            if args.in_font != args.out_font:
                # Copy unchanged font to output
                import shutil
                shutil.copy2(args.in_font, args.out_font)
        
        return 0
        
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


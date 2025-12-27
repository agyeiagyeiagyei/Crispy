#!/usr/bin/env python3
"""
set_axis_defaults.py

Post-build patch to set fvar table axis default values in a variable font.

PURPOSE:
    This script modifies fvar.axes[].defaultValue after font compilation.
    This is a deliberate patch step when source-level defaults are not available
    or need to differ from master locations for UI/UX purposes.

WHEN TO USE:
    - When gftools builder (or other toolchain) sets defaults to axis minimums
    - When you need UI slider defaults that differ from actual master coordinates
    - As a post-processing step in automated builds

WHAT IS SAFE:
    - Modifying fvar.axes[].defaultValue does NOT affect interpolation math
    - Does NOT require font regeneration or outline recalculation
    - Does NOT invalidate other tables (STAT, avar, avar2, glyf, etc.)
    - Safe to apply after any build step that generates a valid variable font

WHAT IS UNSAFE / LIMITATIONS:
    - If defaultValue doesn't correspond to a real master, some tooling may warn
    - Font validation tools may flag non-master defaults (acceptable but noted)
    - Defaults outside [minValue, maxValue] are invalid and will be rejected
    - This is a PATCH: source-level defaults in Glyphs/designspace are preferred

References:
    - Glyphs forum discussions on variable font defaults
    - fontTools fvar table documentation
    - OpenType spec fvar table definition
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

import yaml
from fontTools.ttLib import TTFont


# Hardcoded fallback defaults (used if YAML file not found)
DEFAULT_VALUES_FALLBACK: Dict[str, float] = {
    "wght": 400.0,  # Regular weight
    "wdth": 100.0,  # Normal width
    "opsz": 72.0,   # Display optical size
    "cntr": 0.0,    # Normal contrast
}

# Default paths for axis defaults YAML (checked in order: sources/ then scripts/)
def _get_default_yaml_path() -> Path:
    """Return default YAML path, preferring sources/ over scripts/."""
    sources_path = Path(__file__).parent.parent / "sources" / "axis_defaults.yaml"
    scripts_path = Path(__file__).parent / "axis_defaults.yaml"
    return sources_path if sources_path.exists() else scripts_path

DEFAULT_YAML_PATH = _get_default_yaml_path()


def load_defaults_from_yaml(yaml_path: Optional[Path] = None) -> Dict[str, float]:
    """
    Load axis defaults from YAML file.
    
    Args:
        yaml_path: Path to YAML file (defaults to axis_defaults.yaml in script dir)
        
    Returns:
        Dict mapping axis tags to default values
        
    Raises:
        FileNotFoundError: If yaml_path is specified but doesn't exist
    """
    if yaml_path is None:
        yaml_path = DEFAULT_YAML_PATH
    
    yaml_path = Path(yaml_path)
    
    if not yaml_path.exists():
        if yaml_path == DEFAULT_YAML_PATH:
            # Default file doesn't exist - return fallback silently
            return DEFAULT_VALUES_FALLBACK.copy()
        else:
            # User-specified file doesn't exist - raise error
            raise FileNotFoundError(f"Axis defaults YAML not found: {yaml_path}")
    
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not isinstance(data, dict):
        raise ValueError(
            f"YAML file must contain a dictionary mapping axis tags to values: {yaml_path}"
        )
    
    # Convert all values to float
    defaults = {}
    for tag, value in data.items():
        try:
            defaults[str(tag)] = float(value)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid default value for axis '{tag}': {value} (must be numeric)"
            ) from e
    
    return defaults


def set_fvar_defaults(
    font_path: Path,
    output_path: Path,
    defaults: Dict[str, float],
) -> None:
    """
    Patch fvar table axis defaults without regenerating font.
    
    Args:
        font_path: Input variable font path
        output_path: Output font path (may be same as input_path)
        defaults: Dict mapping axis tags to default values
        
    Raises:
        FileNotFoundError: If font_path doesn't exist
        ValueError: If font lacks fvar table or axis tag not found
        RuntimeError: If default value is outside axis range
    """
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")
    
    font = TTFont(str(font_path))
    
    if "fvar" not in font:
        raise ValueError(f"Font does not have fvar table: {font_path}")
    
    fvar = font["fvar"]
    
    # Track which axes we modify
    modified_axes = []
    missing_axes = []
    
    for tag, desired_default in defaults.items():
        # Find axis by tag
        axis = None
        for a in fvar.axes:
            if a.axisTag == tag:
                axis = a
                break
        
        if axis is None:
            missing_axes.append(tag)
            continue
        
        # Validate default is within axis range
        if desired_default < axis.minValue or desired_default > axis.maxValue:
            raise RuntimeError(
                f"Axis '{tag}': default value {desired_default} is outside "
                f"valid range [{axis.minValue}, {axis.maxValue}]"
            )
        
        # Update default (only if different)
        if axis.defaultValue != desired_default:
            old_default = axis.defaultValue
            axis.defaultValue = desired_default
            modified_axes.append((tag, old_default, desired_default))
    
    # Fail fast if any requested axes are missing
    if missing_axes:
        available_tags = [a.axisTag for a in fvar.axes]
        raise ValueError(
            f"Axis tags not found in font: {missing_axes}. "
            f"Available axes: {available_tags}"
        )
    
    # Save patched font
    if modified_axes or font_path != output_path:
        font.save(str(output_path))
        
        if modified_axes:
            print(f"\n✓ Updated {len(modified_axes)} axis defaults in {output_path.name}:")
            for tag, old_val, new_val in modified_axes:
                print(f"    {tag}: {old_val} → {new_val}")
        else:
            print(f"\n✓ All defaults already correct, saved to {output_path.name}")
    else:
        if modified_axes:
            raise RuntimeError(
                "Font was modified but output_path == input_path. "
                "Refusing to overwrite without explicit output path."
            )
        print("\n✓ No changes needed (all defaults already match desired values)")
    
    # Print final report of all axis defaults
    print(f"\n{'='*70}")
    print(f"Final fvar axis defaults in {output_path.name}:")
    print(f"{'='*70}")
    for axis in sorted(fvar.axes, key=lambda a: a.axisTag):
        marker = "✓" if axis.axisTag in defaults else " "
        range_str = f"[{axis.minValue:.1f}, {axis.maxValue:.1f}]"
        print(f"  {marker} {axis.axisTag:6s}: {axis.defaultValue:8.1f}  {range_str}")
    print(f"{'='*70}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1],  # Use first paragraph as description
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_font",
        type=Path,
        help="Input variable font TTF path",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output font path (default: overwrite input)",
    )
    parser.add_argument(
        "--wght",
        type=float,
        help="Weight axis default (overrides hardcoded default)",
    )
    parser.add_argument(
        "--wdth",
        type=float,
        help="Width axis default (overrides hardcoded default)",
    )
    parser.add_argument(
        "--opsz",
        type=float,
        help="Optical size axis default (overrides hardcoded default)",
    )
    parser.add_argument(
        "--cntr",
        type=float,
        help="Contrast axis default (overrides YAML/hardcoded default)",
    )
    parser.add_argument(
        "--defaults-yaml",
        type=Path,
        help="Path to YAML file with axis defaults (default: scripts/axis_defaults.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying font",
    )
    
    args = parser.parse_args()
    
    # Load defaults from YAML (or use fallback)
    try:
        defaults = load_defaults_from_yaml(args.defaults_yaml)
        if args.defaults_yaml is None and not DEFAULT_YAML_PATH.exists():
            # Only print this if using default path and it doesn't exist
            print(
                f"Note: Using hardcoded defaults (YAML not found: {DEFAULT_YAML_PATH})",
                file=sys.stderr,
            )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading defaults: {e}", file=sys.stderr)
        return 1
    
    # Command-line args override YAML/hardcoded defaults
    if args.wght is not None:
        defaults["wght"] = args.wght
    if args.wdth is not None:
        defaults["wdth"] = args.wdth
    if args.opsz is not None:
        defaults["opsz"] = args.opsz
    if args.cntr is not None:
        defaults["cntr"] = args.cntr
    
    output_path = args.output if args.output else args.input_font
    
    try:
        if args.dry_run:
            # Load font to validate, but don't save
            font = TTFont(str(args.input_font))
            if "fvar" not in font:
                raise ValueError(f"Font does not have fvar table: {args.input_font}")
            
            fvar = font["fvar"]
            changes = []
            
            for tag, desired_default in defaults.items():
                axis = None
                for a in fvar.axes:
                    if a.axisTag == tag:
                        axis = a
                        break
                
                if axis is None:
                    print(f"⚠️  Axis '{tag}' not found in font")
                    continue
                
                if axis.defaultValue != desired_default:
                    changes.append((tag, axis.defaultValue, desired_default))
            
            if changes:
                print("DRY RUN - Would update axis defaults:")
                for tag, old_val, new_val in changes:
                    print(f"  {tag}: {old_val} → {new_val}")
            else:
                print("DRY RUN - No changes needed")
            
            return 0
        else:
            set_fvar_defaults(args.input_font, output_path, defaults)
            return 0
            
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
measure_widths.py

Measure glyph widths using fontquant to recalibrate wdth axis.
Measures "H" glyph width at Regular weight (wght=400) for each wdth value.
Calculates width as percentage of default (wdth=100) and recalibrates axis.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional
import json

try:
    from fontquant import quantify
except ImportError:
    print("Error: fontquant not installed. Install with:", file=sys.stderr)
    print("  pip install git+https://github.com/googlefonts/fontquant", file=sys.stderr)
    sys.exit(1)

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("Error: fontTools not installed. Install with:", file=sys.stderr)
    print("  pip install fonttools", file=sys.stderr)
    sys.exit(1)


def get_glyph_width(font_path: Path, glyph_name: str = "H") -> Optional[float]:
    """
    Get the advance width of a specific glyph from a font file.
    
    Args:
        font_path: Path to the font file
        glyph_name: Name of the glyph to measure (default: "H")
    
    Returns:
        Advance width in font units, or None if glyph not found
    """
    try:
        font = TTFont(str(font_path))
        
        # Get glyph ID from glyph name
        if 'cmap' not in font:
            print(f"Warning: No cmap table in {font_path}", file=sys.stderr)
            return None
        
        # Find glyph ID for the character
        cmap = font.getBestCmap()
        if not cmap:
            print(f"Warning: No cmap found in {font_path}", file=sys.stderr)
            return None
        
        # Get Unicode code point for the glyph
        unicode_char = ord(glyph_name)
        if unicode_char not in cmap:
            print(f"Warning: Glyph '{glyph_name}' (U+{unicode_char:04X}) not found in font", file=sys.stderr)
            return None
        
        glyph_id_or_name = cmap[unicode_char]
        
        # Get advance width from hmtx table
        if 'hmtx' not in font:
            print(f"Warning: No hmtx table in {font_path}", file=sys.stderr)
            return None
        
        hmtx = font['hmtx']
        
        # hmtx.metrics can be either a dict (keyed by glyph name) or a list (indexed by glyph ID)
        # Handle both cases
        if isinstance(glyph_id_or_name, str):
            # It's a glyph name - use it directly if hmtx.metrics is a dict
            if isinstance(hmtx.metrics, dict):
                if glyph_id_or_name not in hmtx.metrics:
                    print(f"Warning: Glyph name '{glyph_id_or_name}' not in hmtx.metrics", file=sys.stderr)
                    return None
                metric = hmtx.metrics[glyph_id_or_name]
            else:
                # It's a list, need to get glyph ID
                glyph_order = font.getGlyphOrder()
                try:
                    glyph_id = glyph_order.index(glyph_id_or_name)
                except ValueError:
                    print(f"Warning: Glyph name '{glyph_id_or_name}' not in glyph order", file=sys.stderr)
                    return None
                if glyph_id >= len(hmtx.metrics):
                    print(f"Warning: Glyph ID {glyph_id} out of range", file=sys.stderr)
                    return None
                metric = hmtx.metrics[glyph_id]
        else:
            # It's a glyph ID
            glyph_id = int(glyph_id_or_name)
            if isinstance(hmtx.metrics, dict):
                # Need glyph name to look up
                glyph_order = font.getGlyphOrder()
                if glyph_id >= len(glyph_order):
                    print(f"Warning: Glyph ID {glyph_id} out of range", file=sys.stderr)
                    return None
                glyph_name = glyph_order[glyph_id]
                if glyph_name not in hmtx.metrics:
                    print(f"Warning: Glyph name '{glyph_name}' not in hmtx.metrics", file=sys.stderr)
                    return None
                metric = hmtx.metrics[glyph_name]
            else:
                # It's a list, use glyph_id directly
                if glyph_id >= len(hmtx.metrics):
                    print(f"Warning: Glyph ID {glyph_id} out of range", file=sys.stderr)
                    return None
                metric = hmtx.metrics[glyph_id]
        
        # Handle both tuple and single value cases
        if isinstance(metric, tuple):
            advance_width, lsb = metric
        else:
            advance_width = metric
            lsb = 0
        
        return float(advance_width)
    
    except Exception as e:
        print(f"Error reading font {font_path}: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def measure_instance_width(font_path: Path, wdth_value: float, wght_value: float = 400.0) -> Optional[float]:
    """
    Measure "H" glyph width at a specific wdth and wght coordinate.
    
    Uses fontTools to instantiate the font at specific variation coordinates,
    then measures the "H" glyph advance width.
    
    Args:
        font_path: Path to variable font file
        wdth_value: Width axis value to measure
        wght_value: Weight axis value (default: 400 for Regular)
    
    Returns:
        Advance width of "H" glyph in font units, or None if error
    """
    try:
        from fontTools.varLib import instancer
        import tempfile
        import os
        
        font = TTFont(str(font_path))
        
        # Check if font has fvar table (variable font)
        if 'fvar' not in font:
            print(f"Warning: {font_path} is not a variable font", file=sys.stderr)
            return get_glyph_width(font_path, "H")
        
        # Get axis tags from fvar table
        fvar = font['fvar']
        axis_tags = [axis.axisTag for axis in fvar.axes]
        
        # Build location dictionary for instancer
        # We need to include all axes, setting others to their defaults
        location = {}
        
        # Set wght and wdth to specified values
        location['wght'] = wght_value
        location['wdth'] = wdth_value
        
        # Set other axes to their defaults from fvar table
        for axis in fvar.axes:
            tag = axis.axisTag
            if tag not in location:
                location[tag] = axis.defaultValue
        
        # Create a temporary instance font
        with tempfile.NamedTemporaryFile(suffix='.ttf', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Instantiate the font at the specified location
            # Note: instantiateVariableFont returns a new font, doesn't modify in place
            instance_font = instancer.instantiateVariableFont(font, location)
            
            # Save the instantiated font temporarily
            instance_font.save(tmp_path)
            
            # Measure the "H" glyph width from the instantiated font
            width = get_glyph_width(Path(tmp_path), "H")
            
            return width
        
        except Exception as e:
            print(f"Error during instantiation: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
    
    except Exception as e:
        print(f"Error measuring instance width: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def measure_widths_from_variable_font(font_path: Path, wdth_values: list[float], wght_value: float = 400.0) -> Dict[float, float]:
    """
    Measure "H" glyph width at multiple wdth values.
    
    Args:
        font_path: Path to variable font file
        wdth_values: List of wdth axis values to measure
        wght_value: Weight axis value (default: 400 for Regular)
    
    Returns:
        Dictionary mapping wdth_value -> measured_width
    """
    results = {}
    
    for wdth in wdth_values:
        print(f"Measuring wdth={wdth} (wght={wght_value})...", file=sys.stderr)
        width = measure_instance_width(font_path, wdth, wght_value)
        if width is not None:
            results[wdth] = width
            print(f"  Width: {width} font units", file=sys.stderr)
        else:
            print(f"  Failed to measure", file=sys.stderr)
    
    return results


def calculate_percentages(measurements: Dict[float, float], reference_wdth: float = 100.0) -> Dict[float, float]:
    """
    Calculate width percentages relative to reference wdth value.
    
    Args:
        measurements: Dictionary mapping wdth_value -> measured_width
        reference_wdth: wdth value to use as 100% reference (default: 100.0)
    
    Returns:
        Dictionary mapping wdth_value -> percentage_of_reference
    """
    if reference_wdth not in measurements:
        print(f"Error: Reference wdth {reference_wdth} not found in measurements", file=sys.stderr)
        return {}
    
    reference_width = measurements[reference_wdth]
    percentages = {}
    
    for wdth, width in measurements.items():
        if reference_width > 0:
            percentage = (width / reference_width) * 100.0
            percentages[wdth] = percentage
        else:
            print(f"Warning: Reference width is 0, cannot calculate percentage", file=sys.stderr)
    
    return percentages


def recalibrate_wdth_axis(percentages: Dict[float, float], reference_wdth: float = 100.0) -> Dict[str, float]:
    """
    Recalibrate wdth axis values based on measured percentages.
    
    If a wdth value maps to a percentage, we want to adjust the axis
    so that the wdth value equals the percentage.
    
    Example:
        If wdth=40 measures 60% of reference, we want wdth=40 to represent 60%
        This means the axis mapping should be adjusted.
    
    Args:
        percentages: Dictionary mapping wdth_value -> percentage_of_reference
        reference_wdth: Reference wdth value (stays at 100%)
    
    Returns:
        Dictionary with recalibrated axis information:
        - min_wdth: Minimum wdth value (based on lowest percentage)
        - max_wdth: Maximum wdth value (based on highest percentage)
        - current_values: Mapping of current wdth -> measured percentage
    """
    if not percentages:
        return {}
    
    # Find min and max percentages
    min_percentage = min(percentages.values())
    max_percentage = max(percentages.values())
    
    # The axis extremes should match the measured percentages
    # If Condensed (wdth=40) measures 60%, then min_wdth should be 60
    # If Ultra Extended (wdth=220) measures 200%, then max_wdth should be 200
    
    recalibrated = {
        "min_wdth": min_percentage,
        "max_wdth": max_percentage,
        "reference_wdth": reference_wdth,
        "current_mappings": percentages,
        "recommendations": {}
    }
    
    # Generate recommendations for each measured wdth
    for wdth, percentage in percentages.items():
        if wdth != reference_wdth:
            recalibrated["recommendations"][wdth] = {
                "current_wdth": wdth,
                "measured_percentage": percentage,
                "suggested_wdth": percentage,  # wdth should equal percentage
                "difference": percentage - wdth
            }
    
    return recalibrated


def main():
    parser = argparse.ArgumentParser(
        description="Measure glyph widths to recalibrate wdth axis"
    )
    parser.add_argument(
        "--font",
        type=Path,
        required=True,
        help="Path to variable font file"
    )
    parser.add_argument(
        "--wdth-values",
        type=float,
        nargs="+",
        default=[40.0, 100.0, 160.0, 220.0],
        help="wdth axis values to measure (default: 40 100 160 220)"
    )
    parser.add_argument(
        "--wght",
        type=float,
        default=400.0,
        help="Weight axis value (default: 400 for Regular)"
    )
    parser.add_argument(
        "--glyph",
        type=str,
        default="H",
        help="Glyph to measure (default: H)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file for results (default: print to stdout)"
    )
    
    args = parser.parse_args()
    
    if not args.font.exists():
        print(f"Error: Font file not found: {args.font}", file=sys.stderr)
        return 1
    
    print(f"Measuring '{args.glyph}' glyph width at wght={args.wght}", file=sys.stderr)
    print(f"wdth values to measure: {args.wdth_values}", file=sys.stderr)
    print("", file=sys.stderr)
    
    # Measure widths
    measurements = measure_widths_from_variable_font(args.font, args.wdth_values, args.wght)
    
    if not measurements:
        print("Error: No measurements obtained", file=sys.stderr)
        return 1
    
    # Calculate percentages
    percentages = calculate_percentages(measurements, reference_wdth=100.0)
    
    # Recalibrate axis
    recalibrated = recalibrate_wdth_axis(percentages, reference_wdth=100.0)
    
    # Prepare output
    output = {
        "font_path": str(args.font),
        "glyph": args.glyph,
        "wght": args.wght,
        "measurements": {str(k): v for k, v in measurements.items()},
        "percentages": {str(k): v for k, v in percentages.items()},
        "recalibration": {
            "min_wdth": recalibrated.get("min_wdth"),
            "max_wdth": recalibrated.get("max_wdth"),
            "reference_wdth": recalibrated.get("reference_wdth"),
            "recommendations": {
                str(k): v for k, v in recalibrated.get("recommendations", {}).items()
            }
        }
    }
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\nResults saved to: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

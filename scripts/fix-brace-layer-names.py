#!/usr/bin/env python3
"""
fix-brace-layer-names.py

Non-destructively fixes brace layer names by removing date tags.
Creates a copy of the Glyphs file with cleaned names for testing.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from glyphsLib import load
except ImportError:
    print("Error: glyphsLib not found. Install with: pip install glyphsLib", file=sys.stderr)
    sys.exit(1)


def clean_brace_layer_name(layer_name: str, coordinates: list) -> str:
    """
    Clean brace layer name by removing date tags and standardizing format.
    
    Returns a standardized name based on coordinates: {X, Y, Z}
    """
    # Extract coordinates and format consistently
    if coordinates and len(coordinates) >= 3:
        # Round to reasonable precision
        x = round(coordinates[0], 2)
        y = round(coordinates[1], 2)
        z = round(coordinates[2], 2)
        return f"{{{x}, {y}, {z}}}"
    
    # Fallback: try to extract coordinates from existing name
    # Look for pattern like {290, 147, 130}
    match = re.search(r'\{([^}]+)\}', layer_name)
    if match:
        return f"{{{match.group(1)}}}"
    
    # If no coordinates found, return a generic name
    return "{brace layer}"


def fix_brace_layer_names(glyphs_path: Path, output_path: Path) -> dict:
    """
    Fix brace layer names in a copy of the Glyphs file.
    
    Returns a dict with statistics about the fixes.
    """
    print(f"Loading Glyphs file: {glyphs_path}", file=sys.stderr)
    font = load(str(glyphs_path))
    
    stats = {
        'total_brace_layers': 0,
        'renamed_layers': 0,
        'coordinate_groups': {}
    }
    
    # First pass: collect all brace layers and their coordinates
    brace_layers_by_coords = {}
    
    for glyph in font.glyphs:
        for layer in glyph.layers:
            if hasattr(layer, 'attributes') and layer.attributes:
                coords = layer.attributes.get('coordinates')
                if coords:
                    stats['total_brace_layers'] += 1
                    coords_tuple = tuple(coords)
                    
                    if coords_tuple not in brace_layers_by_coords:
                        brace_layers_by_coords[coords_tuple] = []
                    
                    brace_layers_by_coords[coords_tuple].append({
                        'glyph': glyph,
                        'layer': layer,
                        'original_name': getattr(layer, 'name', ''),
                        'coordinates': coords
                    })
    
    # Second pass: assign consistent names based on coordinates
    print(f"Found {stats['total_brace_layers']} brace layers in {len(brace_layers_by_coords)} unique locations", file=sys.stderr)
    
    for coords_tuple, layers in brace_layers_by_coords.items():
        # Generate standard name for this coordinate set
        standard_name = clean_brace_layer_name("", list(coords_tuple))
        
        # Track this coordinate group
        stats['coordinate_groups'][standard_name] = len(layers)
        
        # Rename all layers with these coordinates to the same name
        for layer_info in layers:
            layer = layer_info['layer']
            original_name = layer_info['original_name']
            
            if original_name != standard_name:
                layer.name = standard_name
                stats['renamed_layers'] += 1
                print(f"  Renamed: '{original_name}' -> '{standard_name}' (glyph: {layer_info['glyph'].name})", file=sys.stderr)
            else:
                print(f"  Already correct: '{original_name}' (glyph: {layer_info['glyph'].name})", file=sys.stderr)
    
    # Save to output file
    print(f"\nSaving fixed file to: {output_path}", file=sys.stderr)
    font.save(str(output_path))
    
    return stats


def test_for_duplicates(glyphs_path: Path) -> bool:
    """
    Test if the Glyphs file has duplicate location issues.
    
    Returns True if duplicates found, False otherwise.
    """
    from glyphsLib import to_designspace
    
    try:
        font = load(str(glyphs_path))
        designspace = to_designspace(font)
        
        # Check for duplicate locations
        locations = {}
        duplicates = []
        
        for source in designspace.sources:
            loc_key = tuple(sorted(source.location.items()))
            if loc_key in locations:
                duplicates.append((locations[loc_key], source.name, source.location))
            else:
                locations[loc_key] = source.name
        
        if duplicates:
            print(f"\n⚠️  Found {len(duplicates)} duplicate locations:", file=sys.stderr)
            for orig_name, dup_name, loc in duplicates[:5]:
                print(f"  {orig_name} and {dup_name}: {loc}", file=sys.stderr)
            return True
        else:
            print("\n✓ No duplicate locations found", file=sys.stderr)
            return False
    
    except Exception as e:
        print(f"\n⚠️  Error testing for duplicates: {e}", file=sys.stderr)
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Fix brace layer names by removing date tags (non-destructive)"
    )
    parser.add_argument(
        "--glyphs",
        type=Path,
        default=Path("sources/Crispy.glyphs"),
        help="Path to source Glyphs file (default: sources/Crispy.glyphs)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sources/Crispy-fixed-brace-names.glyphs"),
        help="Path to output fixed Glyphs file (default: sources/Crispy-fixed-brace-names.glyphs)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test the output file for duplicate locations"
    )
    
    args = parser.parse_args()
    
    if not args.glyphs.exists():
        print(f"Error: Source file not found: {args.glyphs}", file=sys.stderr)
        sys.exit(1)
    
    # Test original file first
    print("=== TESTING ORIGINAL FILE ===", file=sys.stderr)
    original_has_duplicates = test_for_duplicates(args.glyphs)
    
    # Fix brace layer names
    print("\n=== FIXING BRACE LAYER NAMES ===", file=sys.stderr)
    stats = fix_brace_layer_names(args.glyphs, args.output)
    
    print(f"\n=== STATISTICS ===", file=sys.stderr)
    print(f"Total brace layers: {stats['total_brace_layers']}", file=sys.stderr)
    print(f"Layers renamed: {stats['renamed_layers']}", file=sys.stderr)
    print(f"Unique coordinate groups: {len(stats['coordinate_groups'])}", file=sys.stderr)
    
    # Test fixed file
    if args.test:
        print("\n=== TESTING FIXED FILE ===", file=sys.stderr)
        fixed_has_duplicates = test_for_duplicates(args.output)
        
        if original_has_duplicates and not fixed_has_duplicates:
            print("\n✓ SUCCESS: Duplicate location issue resolved!", file=sys.stderr)
        elif original_has_duplicates and fixed_has_duplicates:
            print("\n⚠️  WARNING: Duplicate locations still present after fix", file=sys.stderr)
        elif not original_has_duplicates:
            print("\n✓ Original file had no duplicates", file=sys.stderr)
    
    print(f"\n✓ Fixed file saved to: {args.output}", file=sys.stderr)
    print(f"  Original file unchanged: {args.glyphs}", file=sys.stderr)


if __name__ == "__main__":
    main()

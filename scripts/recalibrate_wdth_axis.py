#!/usr/bin/env python3
"""
recalibrate_wdth_axis.py

Recalibrate wdth axis based on measured glyph widths.
Updates:
1. Font fvar table: min/max wdth axis values (52-300)
2. CSV file: wdth values for measured points (40→52, 160→182, 220→300)
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("Error: fontTools not installed", file=sys.stderr)
    sys.exit(1)


def update_font_wdth_axis(font_path: Path, min_wdth: int = 52, max_wdth: int = 300) -> bool:
    """
    Update wdth axis min/max values in the font's fvar table.
    
    Args:
        font_path: Path to variable font file
        min_wdth: New minimum wdth value
        max_wdth: New maximum wdth value
    
    Returns:
        True if successful, False otherwise
    """
    try:
        font = TTFont(str(font_path))
        
        if 'fvar' not in font:
            print(f"Error: {font_path} is not a variable font", file=sys.stderr)
            return False
        
        fvar = font['fvar']
        updated = False
        
        # Find and update wdth axis
        for axis in fvar.axes:
            if axis.axisTag == 'wdth':
                old_min = axis.minValue
                old_max = axis.maxValue
                old_default = axis.defaultValue
                axis.minValue = float(min_wdth)
                axis.maxValue = float(max_wdth)
                # Update default to 100.0 (Regular) if it's outside the new range or not 100
                if old_default < min_wdth or old_default > max_wdth or old_default != 100.0:
                    axis.defaultValue = 100.0
                    print(f"Updated wdth axis: {old_min}-{old_max} (default: {old_default}) → {min_wdth}-{max_wdth} (default: 100.0)", file=sys.stderr)
                else:
                    print(f"Updated wdth axis: {old_min}-{old_max} → {min_wdth}-{max_wdth}", file=sys.stderr)
                updated = True
                break
        
        if not updated:
            print(f"Warning: wdth axis not found in font", file=sys.stderr)
            return False
        
        # Save the updated font
        font.save(str(font_path))
        print(f"Font updated: {font_path}", file=sys.stderr)
        return True
    
    except Exception as e:
        print(f"Error updating font: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def update_csv_wdth_values(csv_path: Path, wdth_mapping: Dict[int, int]) -> bool:
    """
    Update wdth values in CSV file based on mapping.
    
    Args:
        csv_path: Path to CSV file
        wdth_mapping: Dictionary mapping old_wdth -> new_wdth
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read CSV
        rows = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                # Update WDTH value if it's in the mapping
                if 'WDTH' in row:
                    old_wdth_str = row['WDTH'].strip()
                    if old_wdth_str:
                        try:
                            old_wdth = int(float(old_wdth_str))
                            if old_wdth in wdth_mapping:
                                new_wdth = wdth_mapping[old_wdth]
                                row['WDTH'] = str(new_wdth)
                                print(f"Updated {row.get('Instance Name', 'unknown')}: wdth {old_wdth} → {new_wdth}", file=sys.stderr)
                        except (ValueError, TypeError):
                            # Keep original value if can't parse
                            pass
                rows.append(row)
        
        # Write updated CSV
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"CSV updated: {csv_path}", file=sys.stderr)
        return True
    
    except Exception as e:
        print(f"Error updating CSV: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Recalibrate wdth axis based on measured widths"
    )
    parser.add_argument(
        "--font",
        type=Path,
        required=True,
        help="Path to variable font file"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to avar2 CSV file"
    )
    parser.add_argument(
        "--min-wdth",
        type=int,
        default=52,
        help="New minimum wdth value (default: 52)"
    )
    parser.add_argument(
        "--max-wdth",
        type=int,
        default=300,
        help="New maximum wdth value (default: 300)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    
    args = parser.parse_args()
    
    # Mapping based on measurements:
    # wdth=40 (52.92%) → 52
    # wdth=160 (182.09%) → 182
    # wdth=220 (300.70%) → 300
    # wdth=100 stays as 100 (reference)
    wdth_mapping = {
        40: 52,
        160: 182,
        220: 300
    }
    
    print("=" * 70, file=sys.stderr)
    print("WDTH AXIS RECALIBRATION", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("", file=sys.stderr)
    print("Axis range update:", file=sys.stderr)
    print(f"  Min: 40 → {args.min_wdth}", file=sys.stderr)
    print(f"  Max: 220 → {args.max_wdth}", file=sys.stderr)
    print("", file=sys.stderr)
    print("CSV value updates:", file=sys.stderr)
    for old, new in wdth_mapping.items():
        print(f"  wdth={old} → wdth={new}", file=sys.stderr)
    print("", file=sys.stderr)
    
    if args.dry_run:
        print("DRY RUN - No changes made", file=sys.stderr)
        return 0
    
    # Update font
    if not args.font.exists():
        print(f"Error: Font file not found: {args.font}", file=sys.stderr)
        return 1
    
    font_success = update_font_wdth_axis(args.font, args.min_wdth, args.max_wdth)
    
    # Update CSV
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        return 1
    
    csv_success = update_csv_wdth_values(args.csv, wdth_mapping)
    
    if font_success and csv_success:
        print("", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("✅ RECALIBRATION COMPLETE", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 0
    else:
        print("", file=sys.stderr)
        print("❌ Recalibration failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

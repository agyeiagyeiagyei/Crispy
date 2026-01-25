#!/usr/bin/env python3
"""
match-instances-to-avar2.py

Match instances from Glyphs file to avar2-mappings.csv and display relationships.

This script:
1. Reads instances from Glyphs file (source of truth)
2. Reads CSV mappings from avar2-mappings.csv
3. Matches instances by exact name (case-sensitive)
4. Compares coordinates (CSV should match Glyphs for axes in Glyphs)
5. Returns structured data showing relationships between traditional and parametric axes

Output format:
{
  "instance_name": "Regular",
  "glyphs_coordinates": {"XTRA": 627.0, "XOPQ": 187.672, ...},
  "avar2_mapping": {
    "in": {"wght": 400, "wdth": 100, "opsz": 48},
    "out": {"XTRA": 627.0, "XOPQ": 187.672, ...}
  },
  "match_status": "matched" | "missing_in_csv" | "missing_in_glyphs",
  "coordinate_mismatches": [...]
}
"""

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

try:
    from glyphsLib import load
except ImportError:
    print("Error: glyphsLib not available. Install with: pip install glyphsLib", file=sys.stderr)
    sys.exit(1)


def get_glyphs_instances(glyphs_path: Path) -> Dict[str, Dict[str, float]]:
    """
    Read instances from Glyphs file.
    
    Returns dict mapping instance name -> {axis_tag: value}
    Includes all axes found in the Glyphs file instances.
    Preserves instance order from Glyphs file.
    """
    try:
        font = load(str(glyphs_path))
        instances = {}
        
        for instance in font.instances:
            name = instance.name or "Unnamed"
            if not name:
                continue
            
            # Get coordinates from instance.axes
            coordinates = {}
            if hasattr(instance, 'axes') and instance.axes:
                for i, axis in enumerate(font.axes):
                    if i < len(instance.axes):
                        tag = axis.axisTag
                        value = float(instance.axes[i])
                        coordinates[tag] = value
            
            instances[name] = coordinates
        
        return instances
    
    except Exception as e:
        print(f"Error reading Glyphs file {glyphs_path}: {e}", file=sys.stderr)
        raise


def _normalize_in_axis_name(col_name: str) -> str:
    """Normalize traditional axis column name (WGHT/WGHT-e -> wght)."""
    col_upper = col_name.upper()
    if col_upper.endswith("-E"):
        col_upper = col_upper[:-2]
    
    # Map to lowercase axis tags
    axis_map = {
        "WGHT": "wght",
        "WDTH": "wdth",
        "OPSZ": "opsz",
        "CONTRAST": "cntr",
        "CNTR": "cntr",
    }
    return axis_map.get(col_upper, col_upper.lower())


def read_csv_mappings(csv_path: Path, glyphs_path: Optional[Path] = None) -> Tuple[List[Dict[str, str]], List[str], List[str], List[str]]:
    """
    Read CSV file and return mappings.
    
    Uses Glyphs file as source of truth to determine parametric vs traditional axes.
    - Parametric axes: axes that exist in the Glyphs file
    - Traditional axes: axes in CSV that are NOT in the Glyphs file
    
    Returns:
        (rows, fieldnames, in_cols, out_cols)
        - rows: List of row dicts
        - fieldnames: List of column names
        - in_cols: List of traditional axis columns (not in Glyphs file)
        - out_cols: List of parametric axis columns (axes from Glyphs file)
    """
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        
        if not fieldnames:
            raise ValueError("CSV has no header row")
        
        # Strip whitespace and normalize column names (uppercase for consistency)
        # Preserve original case mapping for writing back, but use normalized for processing
        normalized_fieldnames = []
        fieldname_mapping = {}  # normalized -> original
        for h in fieldnames:
            original = h.strip()
            normalized = original.upper() if original != "Instance Name" else original
            normalized_fieldnames.append(normalized)
            fieldname_mapping[normalized] = original
        
        name_col = "Instance Name"
        if name_col not in normalized_fieldnames:
            raise ValueError(f"CSV must include '{name_col}' column. Found: {normalized_fieldnames}")
        
        # Use normalized fieldnames for processing
        fieldnames = normalized_fieldnames
        
        # Get parametric axes from Glyphs file (source of truth)
        # Check font.axes (the actual axes defined in the font), not instance coordinates
        parametric_axis_tags = set()
        if glyphs_path and glyphs_path.exists():
            try:
                font = load(str(glyphs_path))
                # Get axis tags directly from font.axes
                for axis in font.axes:
                    if hasattr(axis, 'axisTag'):
                        parametric_axis_tags.add(axis.axisTag.upper())
            except Exception as e:
                print(f"Warning: Could not read Glyphs file to determine parametric axes: {e}", file=sys.stderr)
        
        # Separate columns into traditional (in:) and parametric (out:)
        # Parametric axes are those that exist in the Glyphs file
        out_cols = []  # Parametric axes (from Glyphs file)
        in_cols = []   # Traditional axes (not in Glyphs file)
        
        for c in fieldnames:
            if c == name_col:
                continue
            
            col_upper = c.upper()
            # Check if this column matches a parametric axis from Glyphs file
            # Match by exact tag (parametric_axis_tags are already uppercase)
            is_parametric = col_upper in parametric_axis_tags
            
            if is_parametric:
                out_cols.append(c)
            else:
                # Traditional axis (not in Glyphs file)
                in_cols.append(c)
        
        for row in reader:
            # Normalize row keys to match normalized fieldnames, strip whitespace from values
            cleaned_row = {}
            for k, v in row.items():
                original_key = k.strip()
                # Map to normalized key
                normalized_key = original_key.upper() if original_key != "Instance Name" else original_key
                cleaned_row[normalized_key] = (v.strip() if v else "")
            rows.append(cleaned_row)
    
    return rows, fieldnames, in_cols, out_cols, fieldname_mapping


def _parse_decimal(value: str) -> Optional[Decimal]:
    """Parse string to Decimal, return None if blank."""
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except (ValueError, InvalidOperation):
        return None


def compare_coordinates(
    glyphs_coords: Dict[str, float],
    csv_out_coords: Dict[str, Decimal],
    tolerance: float = 0.01
) -> List[Dict]:
    """
    Compare Glyphs coordinates with CSV parametric coordinates.
    
    Only compares axes that exist in the Glyphs file (excludes SPAC, which is programmatic).
    
    Returns list of mismatches:
    [
      {
        "axis": "XTRA",
        "glyphs_value": 627.0,
        "csv_value": 630.0,
        "differs": True,
        "difference": 3.0
      },
      ...
    ]
    """
    mismatches = []
    
    # Check all axes that exist in Glyphs file
    for axis_tag, glyphs_value in glyphs_coords.items():
            
        csv_value = csv_out_coords.get(axis_tag)
        
        if csv_value is None:
            # Axis exists in Glyphs but not in CSV
            mismatches.append({
                "axis": axis_tag,
                "glyphs_value": glyphs_value,
                "csv_value": None,
                "differs": True,
                "difference": None,
                "reason": "missing_in_csv"
            })
        else:
            # Compare values with tolerance
            csv_float = float(csv_value)
            difference = abs(glyphs_value - csv_float)
            differs = difference > tolerance
            
            if differs:
                mismatches.append({
                    "axis": axis_tag,
                    "glyphs_value": glyphs_value,
                    "csv_value": csv_float,
                    "differs": True,
                    "difference": difference,
                    "reason": "mismatch"
                })
    
    return mismatches


def match_instances(
    glyphs_path: Path,
    csv_path: Path,
    tolerance: float = 0.01
) -> List[Dict]:
    """
    Match instances from Glyphs file to CSV mappings.
    
    Returns list of matched instances with relationships:
    [
      {
        "instance_name": "Regular",
        "glyphs_coordinates": {"XTRA": 627.0, ...},
        "avar2_mapping": {
          "in": {"wght": 400, "wdth": 100, "opsz": 48},
          "out": {"XTRA": 627.0, ...}
        },
        "match_status": "matched" | "missing_in_csv" | "missing_in_glyphs",
        "coordinate_mismatches": [...]
      },
      ...
    ]
    
    Instances are returned in the same order as the Glyphs file.
    """
    # Read Glyphs instances (source of truth, preserves order)
    glyphs_instances = get_glyphs_instances(glyphs_path)
    
    # Read CSV mappings (pass glyphs_path to determine parametric vs traditional)
    csv_rows, fieldnames, in_cols, out_cols, _ = read_csv_mappings(csv_path, glyphs_path)
    
    name_col = "Instance Name"
    
    # Build mapping of instance name -> CSV row
    csv_by_name = {}
    for row in csv_rows:
        instance_name = row.get(name_col, "").strip()
        if instance_name:
            csv_by_name[instance_name] = row
    
    # Build result list (in Glyphs file order)
    results = []
    
    # Process instances from Glyphs file (source of truth)
    for instance_name, glyphs_coords in glyphs_instances.items():
        csv_row = csv_by_name.get(instance_name)
        
        if csv_row is None:
            # Instance exists in Glyphs but not in CSV
            results.append({
                "instance_name": instance_name,
                "glyphs_coordinates": glyphs_coords,
                "avar2_mapping": None,
                "match_status": "missing_in_csv",
                "coordinate_mismatches": []
            })
        else:
            # Match found - extract avar2 mapping
            # Build in_axes (traditional axes)
            in_axes = {}
            for col in in_cols:
                value_str = csv_row.get(col, "").strip()
                if value_str:
                    normalized = _normalize_in_axis_name(col)
                    decimal_val = _parse_decimal(value_str)
                    if decimal_val is not None:
                        in_axes[normalized] = float(decimal_val)
            
            # Build out_axes (parametric axes from CSV)
            # Note: SPAC may or may not be present - treat it like any other axis
            out_axes = {}
            for col in out_cols:
                value_str = csv_row.get(col, "").strip()
                if value_str:
                    decimal_val = _parse_decimal(value_str)
                    if decimal_val is not None:
                        out_axes[col] = decimal_val
            
            # Compare coordinates (only axes that exist in Glyphs file)
            # If SPAC is in CSV but not in Glyphs, it won't be compared (which is fine)
            mismatches = compare_coordinates(glyphs_coords, out_axes, tolerance)
            
            results.append({
                "instance_name": instance_name,
                "glyphs_coordinates": glyphs_coords,
                "avar2_mapping": {
                    "in": in_axes,
                    "out": {k: float(v) for k, v in out_axes.items()}
                },
                "match_status": "matched" if not mismatches else "mismatch",
                "coordinate_mismatches": mismatches
            })
    
    # Add instances that exist in CSV but not in Glyphs (for future import)
    for instance_name, csv_row in csv_by_name.items():
        if instance_name not in glyphs_instances:
            # Build out_axes (parametric axes from CSV)
            # Note: SPAC may or may not be present - treat it like any other axis
            out_axes = {}
            for col in out_cols:
                value_str = csv_row.get(col, "").strip()
                if value_str:
                    decimal_val = _parse_decimal(value_str)
                    if decimal_val is not None:
                        out_axes[col] = float(decimal_val)
            
            # Build in_axes
            in_axes = {}
            for col in in_cols:
                value_str = csv_row.get(col, "").strip()
                if value_str:
                    normalized = _normalize_in_axis_name(col)
                    decimal_val = _parse_decimal(value_str)
                    if decimal_val is not None:
                        in_axes[normalized] = float(decimal_val)
            
            results.append({
                "instance_name": instance_name,
                "glyphs_coordinates": None,
                "avar2_mapping": {
                    "in": in_axes,
                    "out": out_axes
                },
                "match_status": "missing_in_glyphs",
                "coordinate_mismatches": []
            })
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Match instances from Glyphs file to avar2-mappings.csv"
    )
    parser.add_argument(
        "--glyphs",
        type=Path,
        required=True,
        help="Path to Glyphs file"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to avar2-mappings.csv"
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Tolerance for coordinate comparison (default: 0.01)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    if not args.glyphs.exists():
        print(f"Error: Glyphs file not found: {args.glyphs}", file=sys.stderr)
        sys.exit(1)
    
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)
    
    try:
        matches = match_instances(args.glyphs, args.csv, args.tolerance)
        
        if args.json:
            print(json.dumps(matches, indent=2))
        else:
            # Human-readable output
            print(f"Matched {len(matches)} instances\n")
            
            for match in matches:
                status = match["match_status"]
                name = match["instance_name"]
                
                if status == "matched":
                    print(f"✅ {name}")
                elif status == "mismatch":
                    print(f"⚠️  {name} (coordinate mismatches)")
                elif status == "missing_in_csv":
                    print(f"❌ {name} (not in CSV)")
                elif status == "missing_in_glyphs":
                    print(f"📥 {name} (not in Glyphs - can be imported)")
                
                if match["avar2_mapping"]:
                    in_axes = match["avar2_mapping"]["in"]
                    out_axes = match["avar2_mapping"]["out"]
                    
                    print(f"   Traditional: {in_axes}")
                    print(f"   Parametric: {out_axes}")
                
                if match["coordinate_mismatches"]:
                    print(f"   Mismatches:")
                    for mismatch in match["coordinate_mismatches"]:
                        print(f"     - {mismatch['axis']}: Glyphs={mismatch['glyphs_value']}, CSV={mismatch['csv_value']}, diff={mismatch.get('difference', 'N/A')}")
                
                print()
        
        # Exit code: 0 if all matched, 1 if mismatches or missing
        has_issues = any(
            m["match_status"] in ("mismatch", "missing_in_csv", "missing_in_glyphs")
            for m in matches
        )
        sys.exit(0 if not has_issues else 1)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

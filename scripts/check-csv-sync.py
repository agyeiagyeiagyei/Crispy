#!/usr/bin/env python3
"""
Check if CSV is synced with Glyphs file.
Exits with code 0 if synced, 1 if not synced.
"""

import argparse
import sys
from pathlib import Path

# Import sync script functions
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util

sync_script_path = Path(__file__).parent / "sync-glyphs-to-avar2.py"
spec = importlib.util.spec_from_file_location("sync_glyphs_to_avar2", sync_script_path)
sync_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_module)


def check_sync(glyphs_path: Path, csv_path: Path) -> bool:
    """Check if CSV is synced with Glyphs file."""
    if not glyphs_path.exists():
        print(f"ERROR: Glyphs file not found: {glyphs_path}", file=sys.stderr)
        return False
    
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}", file=sys.stderr)
        return False
    
    # Get instances from Glyphs file
    glyphs_instances_dict = sync_module.get_glyphs_instances(glyphs_path)
    glyphs_instances = set(glyphs_instances_dict.keys())
    
    # Get instances from CSV
    csv_rows, fieldnames = sync_module.read_csv_mappings(csv_path)
    instance_name_col = "Instance Name"
    if instance_name_col not in fieldnames:
        print(f"ERROR: CSV missing 'Instance Name' column", file=sys.stderr)
        return False
    
    csv_instances = {row[instance_name_col].strip() for row in csv_rows if row.get(instance_name_col)}
    
    # Check if they match
    missing_in_csv = glyphs_instances - csv_instances
    missing_in_glyphs = csv_instances - glyphs_instances
    
    if missing_in_csv or missing_in_glyphs:
        if missing_in_csv:
            print(f"ERROR: Instances in Glyphs but not in CSV: {sorted(missing_in_csv)}", file=sys.stderr)
        if missing_in_glyphs:
            print(f"ERROR: Instances in CSV but not in Glyphs: {sorted(missing_in_glyphs)}", file=sys.stderr)
        return False
    
    print("✓ CSV is synced with Glyphs file", file=sys.stderr)
    return True


def main():
    parser = argparse.ArgumentParser(description="Check if CSV is synced with Glyphs file")
    parser.add_argument("--glyphs", required=True, type=Path, help="Path to Glyphs file")
    parser.add_argument("--csv", required=True, type=Path, help="Path to CSV file")
    args = parser.parse_args()
    
    if check_sync(args.glyphs, args.csv):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

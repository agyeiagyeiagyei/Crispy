#!/usr/bin/env python3
"""
Remove duplicate instances from CSV file.
Keeps the first occurrence and removes subsequent duplicates.
"""

import csv
import sys
from pathlib import Path

def remove_duplicates_from_csv(csv_path: Path, dry_run: bool = False) -> int:
    """Remove duplicate instances from CSV, keeping first occurrence."""
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        return 0
    
    # Read CSV
    rows = []
    fieldnames = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        rows = list(reader)
    
    # Track seen instance names and remove duplicates
    seen_instances = set()
    unique_rows = []
    removed_count = 0
    
    for i, row in enumerate(rows, 1):
        instance_name = row.get("Instance Name", "").strip()
        if not instance_name:
            # Keep empty rows (shouldn't happen, but be safe)
            unique_rows.append(row)
            continue
        
        if instance_name in seen_instances:
            # Duplicate - skip it
            removed_count += 1
            if dry_run:
                print(f"Would remove duplicate: Row {i} - '{instance_name}'", file=sys.stderr)
            else:
                print(f"Removing duplicate: Row {i} - '{instance_name}'", file=sys.stderr)
        else:
            # First occurrence - keep it
            seen_instances.add(instance_name)
            unique_rows.append(row)
    
    if removed_count == 0:
        print("No duplicates found in CSV", file=sys.stderr)
        return 0
    
    if dry_run:
        print(f"\nDRY RUN: Would remove {removed_count} duplicate row(s)", file=sys.stderr)
        return removed_count
    
    # Write cleaned CSV
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique_rows)
    
    print(f"\nRemoved {removed_count} duplicate row(s) from CSV", file=sys.stderr)
    print(f"CSV now has {len(unique_rows)} unique instance(s)", file=sys.stderr)
    return removed_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Remove duplicate instances from CSV")
    parser.add_argument("--csv", type=Path, default=Path("preview-app/Crispy-avar.csv"),
                        help="Path to CSV file (default: preview-app/Crispy-avar.csv)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be removed without actually removing")
    args = parser.parse_args()
    
    removed = remove_duplicates_from_csv(args.csv, dry_run=args.dry_run)
    sys.exit(0 if removed >= 0 else 1)

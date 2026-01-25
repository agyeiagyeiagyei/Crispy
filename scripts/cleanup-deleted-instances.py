#!/usr/bin/env python3
"""
Clean up CSV by removing instances that don't exist in Glyphs file.

Usage:
    python3 scripts/cleanup-deleted-instances.py [--csv CSV_PATH] [--glyphs GLYPHS_PATH] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

# Import sync function from sync-glyphs-to-avar2.py
try:
    import importlib.util
    sync_script = Path(__file__).parent / "sync-glyphs-to-avar2.py"
    spec = importlib.util.spec_from_file_location("sync_glyphs_to_avar2", sync_script)
    sync_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync_module)
except Exception as e:
    print(f"Error importing sync script: {e}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Remove instances from CSV that don't exist in Glyphs file"
    )
    parser.add_argument(
        "--glyphs",
        type=Path,
        default=Path("sources/Crispy.glyphs"),
        help="Path to Glyphs file (default: sources/Crispy.glyphs)"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Path to CSV file (default: auto-detect preview CSV or sources/avar2-mappings.csv)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without making changes"
    )
    
    args = parser.parse_args()
    
    # Auto-detect CSV if not provided
    if not args.csv:
        # Try preview CSV first
        preview_csv = Path("preview-app/Crispy-avar.csv")
        if preview_csv.exists():
            args.csv = preview_csv
            print(f"Using preview CSV: {args.csv}", file=sys.stderr)
        else:
            # Fallback to production CSV
            args.csv = Path("sources/avar2-mappings.csv")
            if args.csv.exists():
                print(f"Using production CSV: {args.csv}", file=sys.stderr)
            else:
                print(f"Error: CSV file not found. Please specify with --csv", file=sys.stderr)
                sys.exit(1)
    
    # Validate paths
    if not args.glyphs.exists():
        print(f"Error: Glyphs file not found: {args.glyphs}", file=sys.stderr)
        sys.exit(1)
    
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)
    
    # Use sync function to update CSV
    print(f"Syncing CSV with Glyphs file...", file=sys.stderr)
    print(f"  Glyphs: {args.glyphs}", file=sys.stderr)
    print(f"  CSV: {args.csv}", file=sys.stderr)
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'UPDATE'}", file=sys.stderr)
    print("", file=sys.stderr)
    
    success = sync_module.update_csv_from_glyphs(
        args.glyphs,
        args.csv,
        dry_run=args.dry_run
    )
    
    if success:
        if args.dry_run:
            print("\nDry run complete. Run without --dry-run to apply changes.", file=sys.stderr)
        else:
            print("\nCSV updated successfully. Deleted instances have been removed.", file=sys.stderr)
        sys.exit(0)
    else:
        print("\nError: Failed to update CSV", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

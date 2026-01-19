#!/usr/bin/env python3
"""
sync-glyphs-to-avar2.py

Watch Glyphs file for changes and sync instance coordinates to avar2-mappings.csv.

When the Glyphs file is updated:
1. Read instances from Glyphs file
2. Match instances by exact name (case-sensitive) with CSV rows
3. Update XTRA, XOPQ, YOPQ columns from Glyphs coordinates
4. Keep SPAC, WGHT, WDTH, OPSZ unchanged
5. Remove CSV rows that don't match any Glyphs instance
6. Write updated CSV

Only updates axes that exist in the Glyphs file (XTRA, XOPQ, YOPQ).
"""

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    print("Warning: watchdog not available. Install with: pip install watchdog", file=sys.stderr)

try:
    from glyphsLib import load
    HAS_GLYPHSLIB = True
except ImportError:
    HAS_GLYPHSLIB = False
    print("Error: glyphsLib not available. Install with: pip install glyphsLib", file=sys.stderr)
    sys.exit(1)


def get_glyphs_instances(glyphs_path: Path) -> Dict[str, Dict[str, float]]:
    """
    Read instances from Glyphs file.
    
    Returns dict mapping instance name -> {axis_tag: value}
    Includes all axes found in the Glyphs file instances.
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


def read_csv_mappings(csv_path: Path) -> List[Dict[str, str]]:
    """Read CSV file and return list of row dicts."""
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError("CSV has no header row")
        
        for row in reader:
            # Strip whitespace from keys and values
            cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
            rows.append(cleaned_row)
    
    return rows, fieldnames


def update_csv_from_glyphs(
    glyphs_path: Path,
    csv_path: Path,
    dry_run: bool = False
) -> bool:
    """
    Update CSV file with coordinates from Glyphs file.
    
    Returns True if CSV was updated, False otherwise.
    """
    try:
        # Read Glyphs instances
        glyphs_instances = get_glyphs_instances(glyphs_path)
        if not glyphs_instances:
            print(f"No instances found in Glyphs file", file=sys.stderr)
            return False
        
        # Read CSV
        csv_rows, fieldnames = read_csv_mappings(csv_path)
        if not fieldnames:
            print(f"CSV has no header row", file=sys.stderr)
            return False
        
        instance_name_col = "Instance Name"
        if instance_name_col not in fieldnames:
            print(f"CSV missing '{instance_name_col}' column", file=sys.stderr)
            return False
        
        # Dynamically determine which axes to sync:
        # - All axes found in Glyphs file instances
        all_glyphs_axes = set()
        for coords in glyphs_instances.values():
            all_glyphs_axes.update(coords.keys())
        
        # Find axes in Glyphs that aren't in CSV (new axes to add)
        csv_axes = set(fieldnames) - {instance_name_col}
        new_axes = all_glyphs_axes - csv_axes
        
        # Axes to sync (both existing and new)
        glyphs_axes = all_glyphs_axes
        
        if new_axes:
            print(f"New axes found in Glyphs file (will add to CSV): {sorted(new_axes)}", file=sys.stderr)
            # Add new axis columns to fieldnames
            fieldnames = list(fieldnames) + sorted(new_axes)
            # Initialize new axis columns for all existing rows
            for row in csv_rows:
                for axis in new_axes:
                    row[axis] = ""
        
        existing_axes = all_glyphs_axes.intersection(csv_axes)
        if existing_axes:
            print(f"Syncing existing axes from Glyphs file: {sorted(existing_axes)}", file=sys.stderr)
        
        # Build mapping of instance name -> Glyphs coordinates
        glyphs_coords = {}
        for name, coords in glyphs_instances.items():
            glyphs_coords[name] = {axis: coords.get(axis) for axis in glyphs_axes if axis in coords}
        
        # Build set of instance names from Glyphs file
        glyphs_instance_names = set(glyphs_coords.keys())
        
        # Update CSV rows
        updated_rows = []
        updated_count = 0
        removed_count = 0
        added_count = 0
        
        # Process existing CSV rows
        for row in csv_rows:
            instance_name = row.get(instance_name_col, "").strip()
            
            # Check if this instance exists in Glyphs file (exact match, case-sensitive)
            if instance_name in glyphs_coords:
                # Update row with Glyphs coordinates
                coords = glyphs_coords[instance_name]
                for axis in glyphs_axes:
                    if axis in fieldnames and axis in coords:
                        old_value = row.get(axis, "")
                        new_value = str(coords[axis])
                        if old_value != new_value:
                            row[axis] = new_value
                            updated_count += 1
                
                updated_rows.append(row)
                # Remove from set so we know which instances are already in CSV
                glyphs_instance_names.discard(instance_name)
            else:
                # Remove row - instance not in Glyphs file
                removed_count += 1
                if not dry_run:
                    print(f"Removing row: {instance_name} (not in Glyphs file)", file=sys.stderr)
        
        # Add new instances from Glyphs file that aren't in CSV
        for instance_name in glyphs_instance_names:
            coords = glyphs_coords[instance_name]
            new_row = {instance_name_col: instance_name}
            # Initialize all columns
            for col in fieldnames:
                if col != instance_name_col:
                    if col in coords:
                        new_row[col] = str(coords[col])
                    else:
                        new_row[col] = ""
            updated_rows.append(new_row)
            added_count += 1
            if not dry_run:
                print(f"Adding new instance: {instance_name}", file=sys.stderr)
        
        if dry_run:
            changes = []
            if updated_count > 0:
                changes.append(f"update {updated_count} values")
            if removed_count > 0:
                changes.append(f"remove {removed_count} rows")
            if added_count > 0:
                changes.append(f"add {added_count} instances")
            if new_axes:
                changes.append(f"add {len(new_axes)} new axis columns")
            if changes:
                print(f"Dry run: Would {', '.join(changes)}", file=sys.stderr)
            return updated_count > 0 or removed_count > 0 or added_count > 0 or bool(new_axes)
        
        # Write updated CSV
        if updated_count > 0 or removed_count > 0 or added_count > 0 or new_axes:
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(updated_rows)
            
            changes = []
            if updated_count > 0:
                changes.append(f"{updated_count} values updated")
            if removed_count > 0:
                changes.append(f"{removed_count} rows removed")
            if added_count > 0:
                changes.append(f"{added_count} instances added")
            if new_axes:
                changes.append(f"{len(new_axes)} new axis columns added")
            print(f"Updated CSV: {', '.join(changes)}", file=sys.stderr)
            return True
        else:
            print("No changes needed", file=sys.stderr)
            return True  # Success even if no changes (for build process)
    
    except Exception as e:
        print(f"Error updating CSV: {e}", file=sys.stderr)
        return False


class GlyphsFileHandler(FileSystemEventHandler):
    """Watchdog handler for Glyphs file changes."""
    
    def __init__(self, glyphs_path: Path, csv_path: Path):
        self.glyphs_path = glyphs_path
        self.csv_path = csv_path
        self.last_modified = 0
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        # Only process our Glyphs file
        if Path(event.src_path).resolve() != self.glyphs_path.resolve():
            return
        
        # Debounce rapid saves (within 0.5 seconds)
        current_time = time.time()
        if current_time - self.last_modified < 0.5:
            return
        self.last_modified = current_time
        
        print(f"\nGlyphs file modified: {self.glyphs_path}", file=sys.stderr)
        update_csv_from_glyphs(self.glyphs_path, self.csv_path)


def main():
    parser = argparse.ArgumentParser(
        description="Sync Glyphs file instances to avar2-mappings.csv"
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
        default=Path("sources/avar2-mappings.csv"),
        help="Path to avar2-mappings CSV file (default: sources/avar2-mappings.csv)"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch Glyphs file for changes and update CSV automatically"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Update CSV once and exit (don't watch)"
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.glyphs.exists():
        print(f"Error: Glyphs file not found: {args.glyphs}", file=sys.stderr)
        sys.exit(1)
    
    # Create CSV if it doesn't exist
    if not args.csv.exists():
        print(f"CSV file not found: {args.csv}", file=sys.stderr)
        print(f"Creating new CSV from Glyphs file...", file=sys.stderr)
        
        # Read Glyphs instances to create CSV structure
        glyphs_instances = get_glyphs_instances(args.glyphs)
        if not glyphs_instances:
            print(f"Error: No instances found in Glyphs file", file=sys.stderr)
            sys.exit(1)
        
        # Determine all axes from Glyphs file
        all_axes = set()
        for coords in glyphs_instances.values():
            all_axes.update(coords.keys())
        
        # Create CSV with Instance Name and all axes
        fieldnames = ["Instance Name"] + sorted(all_axes)
        rows = []
        for name, coords in sorted(glyphs_instances.items()):
            row = {"Instance Name": name}
            for axis in sorted(all_axes):
                row[axis] = str(coords.get(axis, ""))
            rows.append(row)
        
        # Write new CSV
        with args.csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"Created new CSV with {len(rows)} instances and {len(all_axes)} axes: {sorted(all_axes)}", file=sys.stderr)
        
        # If --once or not watching, exit after creating CSV
        if args.once or not args.watch:
            sys.exit(0)
    
    # Update once
    if args.once or not args.watch:
        success = update_csv_from_glyphs(args.glyphs, args.csv, dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    
    # Watch mode
    if not HAS_WATCHDOG:
        print("Error: watchdog not available. Install with: pip install watchdog", file=sys.stderr)
        sys.exit(1)
    
    print(f"Watching {args.glyphs} for changes...", file=sys.stderr)
    print(f"CSV will be updated to: {args.csv}", file=sys.stderr)
    print("Press Ctrl+C to stop", file=sys.stderr)
    
    # Set up file watcher
    event_handler = GlyphsFileHandler(args.glyphs, args.csv)
    observer = Observer()
    observer.schedule(event_handler, path=str(args.glyphs.parent), recursive=False)
    observer.start()
    
    try:
        # Initial update
        update_csv_from_glyphs(args.glyphs, args.csv)
        
        # Keep watching
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...", file=sys.stderr)
        observer.stop()
    
    observer.join()


if __name__ == "__main__":
    main()

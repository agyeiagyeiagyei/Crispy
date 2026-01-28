#!/usr/bin/env python3
"""
glyphs-preview-server.py

Backend server for Glyphs file preview tool.
Provides API endpoints to:
- Read instances from Glyphs file
- Build variable font
- Extract axes from built font
- Update instance coordinates in Glyphs file
- Serve font files
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Warning: PyYAML not found. Install with: pip install pyyaml", file=sys.stderr)
    yaml = None

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from fontTools.ttLib import TTFont

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Create dummy types for type hints when watchdog is not available
    Observer = None
    FileSystemEventHandler = None
    print("Warning: watchdog not available. Auto-rebuild on file save disabled.", file=sys.stderr)
    print("Install with: pip install watchdog", file=sys.stderr)

try:
    from glyphsLib import GSFont, load
except ImportError:
    print("Error: glyphsLib not found. Install with: pip install glyphsLib", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Global state
GLYPHS_PATH: Optional[Path] = None
BUILD_DIR: Optional[Path] = None
VARIABLE_FONT_PATH: Optional[Path] = None
LAST_BUILD_TIME: Optional[float] = None
BUILDING: bool = False
OBSERVER: Optional[Observer] = None
CSV_PATH: Optional[Path] = None  # Path to avar2-mappings.csv
USE_FONTC: bool = True  # Use fontc by default, fallback to fontmake
PREVIEW_DIR: Optional[Path] = None  # Directory for preview tool files (preview-app/)
PREVIEW_CSV_PATH: Optional[Path] = None  # Path to preview CSV (e.g., preview-app/Crispy-avar.csv)
PREVIEW_CONFIG_PATH: Optional[Path] = None  # Path to preview config (e.g., preview-app/config-preview.yaml)
EDITING_INSTANCES: set = set()  # Track instances currently being edited (protected from sync)


def _check_glyphs_file_unsaved_changes(glyphs_path: Path) -> bool:
    """
    Check if Glyphs file is open in Glyphs.app and has unsaved changes.
    
    Returns True if file has unsaved changes, False otherwise.
    """
    if sys.platform != 'darwin':
        # Only works on macOS with Glyphs.app
        return False
    
    try:
        abs_path = glyphs_path.resolve()
        
        applescript = f'''
        tell application "Glyphs"
            try
                set docPath to POSIX file "{abs_path}" as alias
                set openDocs to documents whose path is (docPath as string)
                set docCount to count of openDocs
                
                if docCount > 0 then
                    repeat with aDoc in openDocs
                        tell aDoc
                            if modified then
                                return true
                            end if
                        end tell
                    end repeat
                end if
                return false
            on error
                return false
            end try
        end tell
        '''
        
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if result.returncode == 0:
            return result.stdout.strip().lower() == 'true'
        return False
    except Exception as e:
        print(f"Warning: Could not check Glyphs file unsaved changes: {e}", file=sys.stderr)
        return False


def _force_reload_glyphs_document(glyphs_path: Path, font_object=None) -> None:
    """
    Force Glyphs.app to reload the document by saving unsaved changes, 
    then closing and reopening all windows of the document.
    
    This ensures the document reflects external changes without save conflicts.
    
    Flow:
    1. Save any unsaved changes in Glyphs.app (preserves user work)
    2. Re-save our changes (since Glyphs.app may have overwritten them)
    3. Close all windows of the document
    4. Wait briefly for close to complete
    5. Reopen the document
    
    Args:
        glyphs_path: Path to the Glyphs file
        font_object: Optional font object to re-save after Glyphs.app saves
                    (if None, will reload and save from disk)
    """
    try:
        # Touch the file to update its modification time
        current_time = time.time()
        os.utime(glyphs_path, (current_time, current_time))
        
        # On macOS, use AppleScript to handle save/close/reopen
        if sys.platform == 'darwin':
            try:
                abs_path = glyphs_path.resolve()
                
                # Step 1: Save any unsaved changes in Glyphs.app
                # Step 2: Re-save our changes (reload from disk and save)
                # Step 3: Close all windows of the document
                # Step 4: Wait briefly
                # Step 5: Reopen the document
                applescript = f'''
                tell application "Glyphs"
                    try
                        set docPath to POSIX file "{abs_path}" as alias
                        set openDocs to documents whose path is (docPath as string)
                        set docCount to count of openDocs
                        
                        if docCount > 0 then
                            -- Step 1: Save any unsaved changes in all open windows
                            -- Reference documents from the openDocs list
                            repeat with aDoc in openDocs
                                tell aDoc
                                    if modified then
                                        save
                                    end if
                                end tell
                            end repeat
                            
                            -- Step 2: Close all windows of this document
                            -- Close all documents from the openDocs list
                            repeat with aDoc in openDocs
                                tell aDoc
                                    close saving no
                                end tell
                            end repeat
                            
                            -- Step 3: Wait for close to complete
                            delay 0.5
                            
                            -- Step 4: Reopen the document
                            open docPath
                        end if
                    end try
                end tell
                '''
                
                # Run AppleScript with longer timeout for save/close/reopen operations
                result = subprocess.run(
                    ['osascript', '-e', applescript],
                    capture_output=True,
                    timeout=10,
                    check=False
                )
                
                # After Glyphs.app saves, we need to re-save our changes
                # (since Glyphs.app may have overwritten them with its in-memory state)
                if result.returncode == 0 and font_object is not None:
                    # Small delay to ensure Glyphs.app has finished saving
                    time.sleep(0.3)
                    # Re-save our changes
                    font_object.save(str(glyphs_path))
                    print(f"Re-saved changes after Glyphs.app save", file=sys.stderr)
                elif result.returncode == 0:
                    # If no font object provided, reload from disk and save
                    # This ensures our changes are preserved
                    time.sleep(0.3)
                    from glyphsLib import load
                    font = load(str(glyphs_path))
                    font.save(str(glyphs_path))
                    print(f"Re-saved changes after Glyphs.app save", file=sys.stderr)
                    
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
                # AppleScript failed - log but don't fail
                print(f"Warning: Could not force reload Glyphs document: {e}", file=sys.stderr)
    except Exception as e:
        # Silently fail - file save already succeeded, this is just a notification
        print(f"Warning: Could not force reload Glyphs document: {e}", file=sys.stderr)


def get_instances_from_glyphs(glyphs_path: Path) -> List[Dict]:
    """
    Read instances from Glyphs file with their axis coordinates.
    
    Returns list of instance dicts with:
    - name: instance name
    - coordinates: dict of axis tag -> value (from instance.axes)
    """
    try:
        font = load(str(glyphs_path))
        instances = []
        axes = font.axes
        
        for instance in font.instances:
            name = instance.name or "Unnamed"
            
            # Get coordinates from instance.axes (direct axis values)
            coordinates = {}
            if hasattr(instance, 'axes') and instance.axes:
                for i, axis in enumerate(axes):
                    if i < len(instance.axes):
                        tag = axis.axisTag
                        value = float(instance.axes[i])
                        coordinates[tag] = value
            
            instances.append({
                "name": name,
                "coordinates": coordinates
            })
        
        return instances
    
    except Exception as e:
        print(f"Error reading Glyphs file: {e}", file=sys.stderr)
        raise


def get_axes_from_glyphs(glyphs_path: Path) -> List[Dict]:
    """
    Extract axes from Glyphs file.
    Calculates min/max from master axes values.
    
    Returns list of axis dicts with:
    - tag: axis tag
    - name: axis name
    - min: minimum value (from masters)
    - max: maximum value (from masters)
    - default: default value (typically min or calculated)
    """
    try:
        font = load(str(glyphs_path))
        axes = font.axes
        
        if not axes:
            return []
        
        # Calculate min/max from masters
        axis_ranges = {ax.axisTag: {'min': float('inf'), 'max': float('-inf')} for ax in axes}
        
        for master in font.masters:
            if hasattr(master, 'axes') and master.axes:
                for i, axis in enumerate(axes):
                    if i < len(master.axes):
                        tag = axis.axisTag
                        value = float(master.axes[i])
                        axis_ranges[tag]['min'] = min(axis_ranges[tag]['min'], value)
                        axis_ranges[tag]['max'] = max(axis_ranges[tag]['max'], value)
        
        # Build axis list
        result = []
        for axis in axes:
            tag = axis.axisTag
            ranges = axis_ranges[tag]
            
            result.append({
                "tag": tag,
                "name": axis.name,
                "min": ranges['min'] if ranges['min'] != float('inf') else 0.0,
                "max": ranges['max'] if ranges['max'] != float('-inf') else 1000.0,
                "default": ranges['min'] if ranges['min'] != float('inf') else 0.0
            })
        
        return result
    
    except Exception as e:
        print(f"Error reading axes from Glyphs file: {e}", file=sys.stderr)
        raise


def build_variable_font(glyphs_path: Path, output_dir: Path, use_fontc: bool = True) -> Path:
    """
    Build variable font from Glyphs file using fontc (with fontmake fallback).
    
    Args:
        glyphs_path: Path to Glyphs file
        output_dir: Directory to output the font
        use_fontc: If True, try fontc first, fallback to fontmake on failure
    
    Returns path to the built variable font TTF.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Try fontc first if enabled
    if use_fontc:
        # Use fontc from PATH (pip-installed)
        fontc_cmd = shutil.which("fontc")
        if fontc_cmd:
            output_file = output_dir / "Crispy-VF.ttf"
            cmd = [
                fontc_cmd,
                "--output-file", str(output_file),
                str(glyphs_path)
            ]
            
            print(f"Building variable font with fontc: {' '.join(cmd)}", file=sys.stderr)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=glyphs_path.parent
            )
            
            if result.returncode == 0 and output_file.exists():
                print("✅ fontc compilation successful", file=sys.stderr)
                return output_file
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                print(f"fontc failed, falling back to fontmake: {error_msg}", file=sys.stderr)
        else:
            print(f"fontc not found in PATH, using fontmake", file=sys.stderr)
    
    # Fallback to fontmake
    cmd = [
        "fontmake",
        "-o", "variable",
        "-g", str(glyphs_path),
        "--output-dir", str(output_dir)
    ]
    
    print(f"Building variable font with fontmake: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=glyphs_path.parent
    )
    
    if result.returncode != 0:
        error_msg = result.stderr or result.stdout or "Unknown error"
        print(f"fontmake failed with exit code {result.returncode}", file=sys.stderr)
        print(f"fontmake stderr: {error_msg}", file=sys.stderr)
        if result.stdout:
            print(f"fontmake stdout: {result.stdout}", file=sys.stderr)
        raise RuntimeError(f"fontmake failed: {error_msg}")
    
    # Find the generated variable font
    # fontmake may create files directly in output_dir or in a subdirectory
    variable_fonts = list(output_dir.rglob("*.ttf"))
    if not variable_fonts:
        raise RuntimeError(f"No variable font found in {output_dir}")
    
    # Return the first variable font found
    # (In practice, there should be only one)
    return variable_fonts[0]


def get_axes_from_built_font(font_path: Path) -> List[Dict]:
    """
    Extract axes from built variable font (for verification).
    This is used after building to confirm the axes match the Glyphs file.
    
    Returns list of axis dicts with:
    - tag: axis tag
    - name: axis name
    - min: minimum value
    - max: maximum value
    - default: default value
    """
    font = TTFont(str(font_path))
    
    if "fvar" not in font:
        return []
    
    fvar = font["fvar"]
    axes = []
    
    for axis in fvar.axes:
        tag = axis.axisTag
        
        # Get axis name from STAT table if available
        name = tag  # Default to tag
        if "STAT" in font:
            stat = font["STAT"]
            # Try to find axis name in STAT table
            # This is simplified - STAT table parsing is complex
            # For now, use common axis names
            axis_names = {
                "wght": "Weight",
                "wdth": "Width",
                "opsz": "Optical Size",
                "cntr": "Contrast",
                "XOPQ": "X-Opacity",
                "YOPQ": "Y-Opacity",
                "XTRA": "X-Transparency",
            }
            name = axis_names.get(tag, tag)
        
        axes.append({
            "tag": tag,
            "name": name,
            "min": float(axis.minValue),
            "max": float(axis.maxValue),
            "default": float(axis.defaultValue)
        })
    
    return axes


def create_instance_in_glyphs(glyphs_path: Path, instance_name: str, coordinates: Dict[str, float], insert_after_instance_name: Optional[str] = None) -> bool:
    """
    Create a new instance in Glyphs file with specified name and coordinates.
    
    Args:
        glyphs_path: Path to the Glyphs file
        instance_name: Name for the new instance
        coordinates: Dictionary of axis tag -> value coordinates
        insert_after_instance_name: Optional name of instance to insert after.
                                    If None, appends to end of list.
    
    Returns True if creation was successful, False otherwise.
    Raises ValueError if instance name already exists.
    """
    try:
        font = load(str(glyphs_path))
        axes = font.axes
        
        # Check if instance name already exists
        for inst in font.instances:
            if inst.name == instance_name:
                raise ValueError(f"Instance '{instance_name}' already exists")
        
        # Create new instance
        from glyphsLib.classes import GSInstance
        new_instance = GSInstance()
        new_instance.name = instance_name
        
        # Set instance.axes to match font.axes order
        new_axes = []
        for i, axis in enumerate(axes):
            tag = axis.axisTag
            if tag in coordinates:
                new_axes.append(coordinates[tag])
            else:
                # Default to 0 if coordinate not provided
                new_axes.append(0.0)
        
        new_instance.axes = new_axes
        
        # Insert instance at the correct position
        if insert_after_instance_name:
            # Find the index of the instance to insert after
            insert_index = None
            for i, inst in enumerate(font.instances):
                if inst.name == insert_after_instance_name:
                    insert_index = i + 1
                    break
            
            if insert_index is not None:
                # Insert after the found instance
                font.instances.insert(insert_index, new_instance)
            else:
                # Instance not found, append to end
                font.instances.append(new_instance)
        else:
            # No insert position specified, append to end
            font.instances.append(new_instance)
        
        # Save the font
        font.save(str(glyphs_path))
        
        # Force Glyphs.app to reload the document (save unsaved changes, close, reopen)
        # Pass font object so we can re-save after Glyphs.app saves
        _force_reload_glyphs_document(glyphs_path, font_object=font)
        
        return True
    
    except ValueError:
        # Re-raise ValueError (duplicate name)
        raise
    except Exception as e:
        print(f"Error creating instance in Glyphs file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def rename_instance_in_glyphs(glyphs_path: Path, old_name: str, new_name: str) -> bool:
    """
    Rename an instance in Glyphs file.
    
    Returns True if rename was successful, False otherwise.
    Raises ValueError if new name already exists.
    """
    try:
        font = load(str(glyphs_path))
        
        # Check if new name already exists
        for inst in font.instances:
            if inst.name == new_name:
                raise ValueError(f"Instance '{new_name}' already exists")
        
        # Find the instance by old name
        instance = None
        for inst in font.instances:
            if inst.name == old_name:
                instance = inst
                break
        
        if not instance:
            return False
        
        # Rename the instance
        instance.name = new_name
        
        # Save the font
        font.save(str(glyphs_path))
        
        # Force Glyphs.app to reload the document (save unsaved changes, close, reopen)
        # Pass font object so we can re-save after Glyphs.app saves
        _force_reload_glyphs_document(glyphs_path, font_object=font)
        
        return True
    
    except ValueError:
        # Re-raise ValueError (duplicate name)
        raise
    except Exception as e:
        print(f"Error renaming instance in Glyphs file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def update_instance_in_glyphs(glyphs_path: Path, instance_name: str, coordinates: Dict[str, float]) -> bool:
    """
    Update instance coordinates in Glyphs file.
    Modifies instance.axes values directly.
    
    Returns True if update was successful, False otherwise.
    """
    try:
        font = load(str(glyphs_path))
        axes = font.axes
        
        # Find the instance by name
        instance = None
        for inst in font.instances:
            if inst.name == instance_name:
                instance = inst
                break
        
        if not instance:
            return False
        
        # Update instance.axes with new coordinates
        # instance.axes is a list matching the order of font.axes
        new_axes = []
        for i, axis in enumerate(axes):
            tag = axis.axisTag
            if tag in coordinates:
                new_axes.append(coordinates[tag])
            elif hasattr(instance, 'axes') and instance.axes and i < len(instance.axes):
                # Keep existing value if not specified
                new_axes.append(instance.axes[i])
            else:
                # Default to 0 if no existing value
                new_axes.append(0.0)
        
        instance.axes = new_axes
        
        # Save the font
        font.save(str(glyphs_path))
        
        # Force Glyphs.app to reload the document (save unsaved changes, close, reopen)
        # Pass font object so we can re-save after Glyphs.app saves
        _force_reload_glyphs_document(glyphs_path, font_object=font)
        
        return True
    
    except Exception as e:
        print(f"Error updating Glyphs file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


@app.route('/api/instances', methods=['GET'])
def get_instances():
    """Get all instances from the Glyphs file with their coordinates."""
    try:
        instances = get_instances_from_glyphs(GLYPHS_PATH)
        return jsonify({"instances": instances})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/axes', methods=['GET'])
def get_axes():
    """Get axes from the Glyphs file (or built font if available)."""
    try:
        # Try to get from built font first (more accurate), fallback to Glyphs file
        if VARIABLE_FONT_PATH and VARIABLE_FONT_PATH.exists():
            axes = get_axes_from_built_font(VARIABLE_FONT_PATH)
        else:
            axes = get_axes_from_glyphs(GLYPHS_PATH)
        
        return jsonify({"axes": axes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def trigger_build():
    """Trigger font build (used by both manual and auto-rebuild)."""
    global VARIABLE_FONT_PATH, LAST_BUILD_TIME, BUILDING, USE_FONTC
    
    if BUILDING:
        print("Build already in progress, skipping...", file=sys.stderr)
        return False
    
    BUILDING = True
    try:
        print(f"Building font from {GLYPHS_PATH}...", file=sys.stderr)
        VARIABLE_FONT_PATH = build_variable_font(GLYPHS_PATH, BUILD_DIR, use_fontc=USE_FONTC)
        LAST_BUILD_TIME = time.time()
        print(f"Font built successfully: {VARIABLE_FONT_PATH}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return False
    finally:
        BUILDING = False


@app.route('/api/build', methods=['POST'])
def build_font():
    """Build the variable font from Glyphs file using fontmake."""
    try:
        success = trigger_build()
        
        if not success:
            return jsonify({"error": "Build failed or already in progress"}), 500
        
        # Get axes after building (for verification)
        axes = get_axes_from_built_font(VARIABLE_FONT_PATH)
        
        return jsonify({
            "success": True,
            "font_path": str(VARIABLE_FONT_PATH),
            "axes": axes,
            "build_time": LAST_BUILD_TIME
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/font', methods=['GET'])
def get_font():
    """Serve the variable font file (designspace-generated with SPAC axis)."""
    # Always serve designspace-generated font if available
    spac_font_path = _ensure_spac_font_exists()
    
    if spac_font_path and spac_font_path.exists():
        font_path = spac_font_path
    elif VARIABLE_FONT_PATH and VARIABLE_FONT_PATH.exists():
        # Fallback to regular variable font if SPAC font not available
        font_path = VARIABLE_FONT_PATH
    else:
        return jsonify({"error": "Variable font not built yet."}), 404
    
    response = send_file(
        str(font_path),
        mimetype='font/ttf',
        as_attachment=False
    )
    # Add cache control headers to prevent browser caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # Add ETag based on file modification time for cache validation
    mtime = font_path.stat().st_mtime
    response.headers['ETag'] = f'"{int(mtime)}"'
    return response


@app.route('/api/preview-font', methods=['GET'])
def get_preview_font():
    """Serve the preview font file (with SPAC axis if available)."""
    preview_font_dir = _get_preview_font_dir()
    if not preview_font_dir or not preview_font_dir.exists():
        return jsonify({"error": "Preview font directory not found"}), 404
    
    # Look for font with SPAC in name first, then any .ttf file
    family_name = GLYPHS_PATH.stem if GLYPHS_PATH else "Crispy"
    spac_font = preview_font_dir / f"{family_name}[SPAC].ttf"
    
    if spac_font.exists():
        font_path = spac_font
    else:
        # Fallback to any .ttf file in preview directory
        ttf_files = list(preview_font_dir.glob("*.ttf"))
        if not ttf_files:
            return jsonify({"error": "Preview font not built yet"}), 404
        font_path = ttf_files[0]  # Use first TTF file found
    
    response = send_file(
        str(font_path),
        mimetype='font/ttf',
        as_attachment=False
    )
    # Add cache control headers to prevent browser caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # Add ETag based on file modification time for cache validation
    mtime = font_path.stat().st_mtime
    response.headers['ETag'] = f'"{int(mtime)}"'
    return response


@app.route('/api/instance', methods=['POST'])
def create_instance():
    """Create a new instance in the Glyphs file."""
    data = request.get_json()
    if not data or 'name' not in data or 'coordinates' not in data:
        return jsonify({"error": "Missing 'name' or 'coordinates' in request body"}), 400
    
    instance_name = data['name'].strip()
    if not instance_name:
        return jsonify({"error": "Instance name cannot be empty"}), 400
    
    coordinates = data['coordinates']
    
    # Validate coordinates are numeric
    try:
        coordinates = {k: float(v) for k, v in coordinates.items()}
    except (ValueError, TypeError):
        return jsonify({"error": "Coordinates must be numeric"}), 400
    
    # Explicitly exclude SPAC from coordinates (SPAC is only stored in preview CSV, not Glyphs file)
    coordinates = {k: v for k, v in coordinates.items() if k.upper() != 'SPAC'}
    
    # Optional: insert after a specific instance
    insert_after = data.get('insert_after', None)
    if insert_after:
        insert_after = insert_after.strip()
    
    try:
        success = create_instance_in_glyphs(GLYPHS_PATH, instance_name, coordinates, insert_after_instance_name=insert_after)
        
        if success:
            # Add new instance to preview CSV if it exists
            csv_path = _get_preview_csv_path()
            if csv_path and csv_path.exists():
                try:
                    # Read existing CSV
                    rows = []
                    fieldnames = []
                    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                        reader = csv.DictReader(f)
                        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
                        for row in reader:
                            rows.append(row)
                    
                    # Ensure SPAC column exists
                    if "SPAC" not in fieldnames:
                        fieldnames.append("SPAC")
                        for row in rows:
                            if "SPAC" not in row:
                                row["SPAC"] = "0"
                    
                    # Get parametric axis values from coordinates
                    new_row = {"Instance Name": instance_name}
                    # Get parametric axes from Glyphs file to know which columns to populate
                    if GLYPHS_PATH and GLYPHS_PATH.exists():
                        try:
                            font = load(str(GLYPHS_PATH))
                            for axis in font.axes:
                                if hasattr(axis, 'axisTag'):
                                    tag = axis.axisTag.upper()
                                    # Use coordinate if provided, otherwise 0
                                    new_row[tag] = str(coordinates.get(axis.axisTag, coordinates.get(tag, 0)))
                        except Exception as e:
                            print(f"Warning: Could not read axes from Glyphs file: {e}", file=sys.stderr)
                    
                    # Initialize SPAC to 0
                    new_row["SPAC"] = "0"
                    
                    # Ensure all fieldnames are present in new_row
                    for field in fieldnames:
                        if field not in new_row:
                            new_row[field] = "0"
                    
                    # Add new instance row
                    rows.append(new_row)
                    
                    # Write updated CSV
                    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    
                    # Update modification time cache to prevent false "external edit" detection
                    _update_csv_modification_time(csv_path)
                    
                    print(f"Added instance '{instance_name}' to preview CSV", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Could not add instance to preview CSV: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()
            
            # Trigger immediate rebuild after creating instance
            # This ensures font is rebuilt right away, not waiting for periodic check
            print(f"Instance created, triggering immediate rebuild...", file=sys.stderr)
            trigger_build()
            
            return jsonify({"success": True, "message": f"Created instance '{instance_name}' in Glyphs file"})
        else:
            return jsonify({"error": f"Failed to create instance '{instance_name}'"}), 500
    except ValueError as e:
        # Duplicate name error
        return jsonify({"error": str(e)}), 400


@app.route('/api/instance/<instance_name>', methods=['PUT'])
def update_instance(instance_name: str):
    """Update instance coordinates in the Glyphs file and CSV.
    
    Writes parametric coordinates (XTRA, XOPQ, YOPQ) to Glyphs file.
    Saves SPAC value to CSV (SPAC is CSV-only, not in Glyphs file).
    """
    data = request.get_json()
    if not data or 'coordinates' not in data:
        return jsonify({"error": "Missing 'coordinates' in request body"}), 400
    
    coordinates = data['coordinates']
    
    # Validate coordinates are numeric
    try:
        coordinates = {k: float(v) for k, v in coordinates.items()}
    except (ValueError, TypeError):
        return jsonify({"error": "Coordinates must be numeric"}), 400
    
    # Extract SPAC value (CSV-only)
    spac_value = coordinates.get('SPAC')
    
    # Filter to only parametric axes that exist in Glyphs file (XTRA, XOPQ, YOPQ)
    # SPAC is CSV-only, traditional axes (WGHT, WDTH, OPSZ) are not in Glyphs file
    font = load(str(GLYPHS_PATH))
    glyphs_axis_tags = {axis.axisTag for axis in font.axes}
    
    # Only include coordinates for axes that exist in Glyphs file (exclude SPAC)
    glyphs_coordinates = {
        tag: value for tag, value in coordinates.items()
        if tag in glyphs_axis_tags and tag != 'SPAC'
    }
    
    # Remove from editing set since we're saving
    global EDITING_INSTANCES
    EDITING_INSTANCES.discard(instance_name)
    
    # Update Glyphs file only if there are parametric coordinates to update
    glyphs_updated = False
    if glyphs_coordinates:
        glyphs_updated = update_instance_in_glyphs(GLYPHS_PATH, instance_name, glyphs_coordinates)
        if not glyphs_updated:
            return jsonify({"error": f"Failed to update instance '{instance_name}' in Glyphs file"}), 500
    
    # Save SPAC value to CSV if provided
    if spac_value is not None:
        csv_path = _get_preview_csv_path()
        if csv_path and csv_path.exists():
            try:
                import csv
                # Read CSV
                rows = []
                with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    fieldnames = list(reader.fieldnames) if reader.fieldnames else []
                    rows = list(reader)
                
                # Ensure SPAC column exists
                if "SPAC" not in fieldnames:
                    fieldnames.append("SPAC")
                
                # Update SPAC value for this instance
                instance_updated = False
                for row in rows:
                    if row.get("Instance Name", "").strip() == instance_name:
                        row["SPAC"] = str(spac_value)
                        instance_updated = True
                        break
                
                if instance_updated:
                    # Write updated CSV
                    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    _update_csv_modification_time(csv_path)
                    print(f"Updated SPAC value for '{instance_name}' in CSV: {spac_value}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not update SPAC value in CSV: {e}", file=sys.stderr)
    
    # Sync CSV to update with new Glyphs coordinates (but skip this instance if still editing)
    csv_path = _get_avar2_csv_path()
    if csv_path and csv_path.exists():
        try:
            import subprocess
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent / "sync-glyphs-to-avar2.py"),
                    "--glyphs", str(GLYPHS_PATH),
                    "--csv", str(csv_path),
                    "--once"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"CSV synced after instance update", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not sync CSV after update: {e}", file=sys.stderr)
    
    # Trigger immediate rebuild after updating instance
    # If SPAC font exists, regenerate it (designspace-based), otherwise rebuild regular font
    # Run rebuild in background thread to avoid blocking the response and file locking issues
    def rebuild_in_background():
        global BUILDING
        if BUILDING:
            print("Build already in progress, skipping rebuild after instance update...", file=sys.stderr)
            return
        
        spac_font_dir = _get_spac_font_dir()
        if spac_font_dir:
            spac_font_path = spac_font_dir / "Crispy-SPAC-VF.ttf"
            if spac_font_path.exists():
                # SPAC font exists - regenerate it using add-spac-axis-ufo.py
                print(f"Instance updated, regenerating SPAC font...", file=sys.stderr)
                BUILDING = True
                try:
                    if not _regenerate_spac_font():
                        # Fallback to regular build if regeneration fails
                        print(f"SPAC regeneration failed, falling back to regular build...", file=sys.stderr)
                        BUILDING = False  # Reset before trigger_build (which sets it)
                        trigger_build()
                except Exception as e:
                    print(f"Error during SPAC font regeneration: {e}", file=sys.stderr)
                    BUILDING = False
            else:
                # No SPAC font - rebuild regular font
                print(f"Instance updated, triggering immediate rebuild...", file=sys.stderr)
                trigger_build()
        else:
            # No SPAC font directory - rebuild regular font
            print(f"Instance updated, triggering immediate rebuild...", file=sys.stderr)
            trigger_build()
    
    # Start rebuild in background thread (small delay to ensure file save completes)
    rebuild_thread = threading.Thread(target=rebuild_in_background, daemon=True)
    rebuild_thread.start()
    
    message_parts = []
    if glyphs_updated:
        message_parts.append(f"Updated instance '{instance_name}' in Glyphs file")
    if spac_value is not None:
        message_parts.append(f"Updated SPAC value to {spac_value} in CSV")
    
    return jsonify({
        "success": True,
        "message": "; ".join(message_parts) if message_parts else f"Updated instance '{instance_name}'"
    })


@app.route('/api/instance/<instance_name>/rename', methods=['PUT'])
def rename_instance(instance_name: str):
    """Rename an instance in the Glyphs file."""
    data = request.get_json()
    if not data or 'new_name' not in data:
        return jsonify({"error": "Missing 'new_name' in request body"}), 400
    
    new_name = data['new_name'].strip()
    if not new_name:
        return jsonify({"error": "New instance name cannot be empty"}), 400
    
    if new_name == instance_name:
        return jsonify({"error": "New name is the same as current name"}), 400
    
    try:
        success = rename_instance_in_glyphs(GLYPHS_PATH, instance_name, new_name)
        
        if success:
            # Update preview CSV if it exists
            csv_path = _get_preview_csv_path()
            if csv_path and csv_path.exists():
                try:
                    rows = []
                    fieldnames = []
                    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                        reader = csv.DictReader(f)
                        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
                        for row in reader:
                            if row.get("Instance Name", "").strip() == instance_name:
                                row["Instance Name"] = new_name
                            rows.append(row)
                    
                    # Write updated CSV
                    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    
                    # Update modification time cache
                    _update_csv_modification_time(csv_path)
                    
                    print(f"Renamed instance '{instance_name}' to '{new_name}' in preview CSV", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Could not update instance name in preview CSV: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()
            
            # Trigger immediate rebuild after renaming instance
            print(f"Instance renamed, triggering immediate rebuild...", file=sys.stderr)
            trigger_build()
            
            return jsonify({"success": True, "message": f"Renamed instance '{instance_name}' to '{new_name}'"})
        else:
            return jsonify({"error": f"Failed to rename instance '{instance_name}'"}), 500
    except ValueError as e:
        # Duplicate name error
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def get_font_family_name(glyphs_path: Path) -> Optional[str]:
    """Get font family name from Glyphs file."""
    try:
        if not glyphs_path or not glyphs_path.exists():
            return None
        font = load(str(glyphs_path))
        return font.familyName
    except Exception as e:
        print(f"Error getting font family name: {e}", file=sys.stderr)
        return None


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        family_name = None
        if GLYPHS_PATH:
            family_name = get_font_family_name(GLYPHS_PATH)
        
        return jsonify({
            "status": "ok",
            "glyphs_path": str(GLYPHS_PATH) if GLYPHS_PATH else None,
            "font_built": VARIABLE_FONT_PATH.exists() if VARIABLE_FONT_PATH else False,
            "family_name": family_name,
            "last_build_time": LAST_BUILD_TIME,
            "building": BUILDING
        })
    except Exception as e:
        print(f"Error in health endpoint: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/glyphs-file-status', methods=['GET'])
def glyphs_file_status():
    """Check if Glyphs file has unsaved changes."""
    try:
        has_unsaved = _check_glyphs_file_unsaved_changes(GLYPHS_PATH)
        return jsonify({
            "has_unsaved_changes": has_unsaved,
            "file_path": str(GLYPHS_PATH)
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "has_unsaved_changes": False
        }), 500


# ============================================================================
# Avar2 API Endpoints
# ============================================================================

# Track CSV modification times for external edit detection
_CSV_MODIFICATION_TIMES: Dict[str, float] = {}

def _get_avar2_csv_path() -> Optional[Path]:
    """Get path to avar2-mappings.csv (relative to Glyphs file or explicit)."""
    # For preview tool: use preview CSV if it exists (fresh start workflow)
    preview_csv = _get_preview_csv_path()
    if preview_csv and preview_csv.exists():
        return preview_csv
    
    # Fallback to explicit CSV path if set
    global CSV_PATH
    if CSV_PATH:
        return CSV_PATH
    
    # Default: look for avar2-mappings.csv in same directory as Glyphs file
    if GLYPHS_PATH:
        default_csv = GLYPHS_PATH.parent / "avar2-mappings.csv"
        if default_csv.exists():
            return default_csv
    
    return None


def _get_avar2_metadata_path() -> Optional[Path]:
    """Get path to avar2-axis-metadata.json (same directory as CSV)."""
    csv_path = _get_avar2_csv_path()
    if not csv_path:
        return None
    # For preview CSV, use preview directory for metadata
    preview_csv = _get_preview_csv_path()
    if preview_csv and csv_path == preview_csv:
        preview_dir = _get_preview_dir()
        if preview_dir:
            return preview_dir / "avar2-axis-metadata.json"
    return csv_path.parent / "avar2-axis-metadata.json"


def _get_preview_dir() -> Optional[Path]:
    """Get preview tool directory (preview-app/)."""
    global PREVIEW_DIR
    if PREVIEW_DIR:
        return PREVIEW_DIR
    
    # Default: preview-app/ directory relative to script location
    script_dir = Path(__file__).parent.parent
    preview_dir = script_dir / "preview-app"
    if preview_dir.exists():
        PREVIEW_DIR = preview_dir
        return preview_dir
    return None


def _get_preview_csv_path() -> Optional[Path]:
    """Get path to preview CSV (e.g., preview-app/Crispy-avar.csv)."""
    global PREVIEW_CSV_PATH
    if PREVIEW_CSV_PATH:
        return PREVIEW_CSV_PATH
    
    preview_dir = _get_preview_dir()
    if not preview_dir or not GLYPHS_PATH:
        return None
    
    # Extract family name from Glyphs file
    try:
        font = load(str(GLYPHS_PATH))
        family_name = font.familyName or "Font"
    except Exception:
        # Fallback: use Glyphs filename without extension
        family_name = GLYPHS_PATH.stem
    
    csv_path = preview_dir / f"{family_name}-avar.csv"
    PREVIEW_CSV_PATH = csv_path
    return csv_path


def _get_preview_config_path() -> Optional[Path]:
    """Get path to preview config.yaml (e.g., preview-app/config-preview.yaml)."""
    global PREVIEW_CONFIG_PATH
    if PREVIEW_CONFIG_PATH:
        return PREVIEW_CONFIG_PATH
    
    preview_dir = _get_preview_dir()
    if not preview_dir:
        return None
    
    config_path = preview_dir / "config-preview.yaml"
    PREVIEW_CONFIG_PATH = config_path
    return config_path


def _get_preview_font_dir() -> Optional[Path]:
    """Get preview font directory (preview-app/preview-fonts/)."""
    preview_dir = _get_preview_dir()
    if not preview_dir:
        return None
    font_dir = preview_dir / "preview-fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    return font_dir


def _regenerate_spac_font() -> bool:
    """
    Regenerate SPAC font using add-spac-axis-ufo.py.
    This is called after Glyphs file updates to refresh the SPAC font.
    
    Returns True if successful, False otherwise.
    """
    if not GLYPHS_PATH or not GLYPHS_PATH.exists():
        return False
    
    spac_font_dir = _get_spac_font_dir()
    if not spac_font_dir:
        return False
    
    family_name = GLYPHS_PATH.stem
    spac_font_path = spac_font_dir / "Crispy-SPAC-VF.ttf"
    
    add_spac_script = Path(__file__).parent / "add-spac-axis-ufo.py"
    if not add_spac_script.exists():
        print(f"Warning: add-spac-axis-ufo.py not found at {add_spac_script}", file=sys.stderr)
        return False
    
    # Run add-spac-axis-ufo.py to regenerate SPAC font
    cmd = [
        sys.executable,
        str(add_spac_script),
        str(GLYPHS_PATH),
        "--output-dir", str(spac_font_dir),
        "--compile",
        "--fontc-output", str(spac_font_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    if result.returncode == 0 and spac_font_path.exists():
        print(f"✓ Regenerated SPAC font: {spac_font_path}", file=sys.stderr)
        return True
    else:
        print(f"Warning: SPAC font regeneration failed:", file=sys.stderr)
        print(f"  stdout: {result.stdout}", file=sys.stderr)
        print(f"  stderr: {result.stderr}", file=sys.stderr)
        return False


def _get_spac_font_dir() -> Optional[Path]:
    """Get SPAC font directory (preview-app/preview-fonts/spac/)."""
    preview_font_dir = _get_preview_font_dir()
    if not preview_font_dir:
        return None
    spac_dir = preview_font_dir / "spac"
    spac_dir.mkdir(parents=True, exist_ok=True)
    return spac_dir


def _ensure_spac_font_exists() -> Optional[Path]:
    """
    Ensure designspace-generated SPAC font exists.
    If not, run add-spac-axis-ufo.py to generate it.
    
    Returns path to SPAC font if successful, None otherwise.
    """
    if not GLYPHS_PATH or not GLYPHS_PATH.exists():
        return None
    
    spac_font_dir = _get_spac_font_dir()
    if not spac_font_dir:
        return None
    
    family_name = GLYPHS_PATH.stem
    spac_font_path = spac_font_dir / "Crispy-SPAC-VF.ttf"
    
    # Check if font already exists
    if spac_font_path.exists():
        return spac_font_path
    
    # Check if designspace exists (indicates partial generation)
    designspace_files = list(spac_font_dir.glob("*.designspace"))
    designspace_path = designspace_files[0] if designspace_files else None
    
    # If designspace exists but font doesn't, just compile it
    if designspace_path and designspace_path.exists():
        print(f"Designspace found but font missing, compiling with fontc...", file=sys.stderr)
        # Compile designspace with fontc
        fontc_cmd = shutil.which("fontc")
        if fontc_cmd:
            cmd = [
                fontc_cmd,
                "--output-file", str(spac_font_path),
                str(designspace_path.resolve())
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and spac_font_path.exists():
                print(f"✓ Compiled SPAC font: {spac_font_path}", file=sys.stderr)
                return spac_font_path
            else:
                print(f"Warning: fontc compilation failed: {result.stderr}", file=sys.stderr)
    
    # Generate SPAC font using add-spac-axis-ufo.py
    print(f"Generating SPAC font...", file=sys.stderr)
    add_spac_script = Path(__file__).parent / "add-spac-axis-ufo.py"
    
    if not add_spac_script.exists():
        print(f"Warning: add-spac-axis-ufo.py not found at {add_spac_script}", file=sys.stderr)
        return None
    
    # Run add-spac-axis-ufo.py
    cmd = [
        sys.executable,
        str(add_spac_script),
        str(GLYPHS_PATH),
        "--output-dir", str(spac_font_dir),
        "--compile",
        "--fontc-output", str(spac_font_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    if result.returncode == 0 and spac_font_path.exists():
        print(f"✓ Generated SPAC font: {spac_font_path}", file=sys.stderr)
        return spac_font_path
    else:
        print(f"Warning: SPAC font generation failed:", file=sys.stderr)
        print(f"  stdout: {result.stdout}", file=sys.stderr)
        print(f"  stderr: {result.stderr}", file=sys.stderr)
        return None


def _get_avar2_font_dir() -> Optional[Path]:
    """Get avar2 font directory (preview-app/fonts-avar2/variable/)."""
    preview_dir = _get_preview_dir()
    if not preview_dir:
        return None
    font_dir = preview_dir / "fonts-avar2" / "variable"
    font_dir.mkdir(parents=True, exist_ok=True)
    return font_dir


def _check_preview_csv_sync_status() -> Dict[str, any]:
    """
    Check if preview CSV is synced with Glyphs file.
    
    Returns dict with:
    - synced: bool
    - message: str
    - glyphs_instances: list of instance names in Glyphs
    - csv_instances: list of instance names in CSV
    """
    try:
        csv_path = _get_preview_csv_path()
        if not csv_path or not csv_path.exists():
            return {
                "synced": False,
                "message": "Preview CSV not found",
                "glyphs_instances": [],
                "csv_instances": []
            }
        
        if not GLYPHS_PATH or not GLYPHS_PATH.exists():
            return {
                "synced": False,
                "message": "Glyphs file not found",
                "glyphs_instances": [],
                "csv_instances": []
            }
        
        # Read instances from Glyphs file
        # Import sync script functions using importlib (handles hyphenated module names)
        import importlib.util
        sync_script_path = Path(__file__).parent / "sync-glyphs-to-avar2.py"
        spec = importlib.util.spec_from_file_location("sync_glyphs_to_avar2", sync_script_path)
        sync_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync_module)
        
        glyphs_instances_dict = sync_module.get_glyphs_instances(GLYPHS_PATH)
        glyphs_instances = set(glyphs_instances_dict.keys())
        
        # Read instances from CSV
        csv_rows, fieldnames = sync_module.read_csv_mappings(csv_path)
        instance_name_col = "Instance Name"
        if instance_name_col not in fieldnames:
            return {
                "synced": False,
                "message": "CSV missing 'Instance Name' column",
                "glyphs_instances": sorted(glyphs_instances),
                "csv_instances": []
            }
        
        csv_instances = {row[instance_name_col].strip() for row in csv_rows if row.get(instance_name_col)}
        
        # Check if they match
        missing_in_csv = glyphs_instances - csv_instances
        missing_in_glyphs = csv_instances - glyphs_instances
        
        synced = len(missing_in_csv) == 0 and len(missing_in_glyphs) == 0
        
        if synced:
            message = "CSV is synced with Glyphs file"
        else:
            parts = []
            if missing_in_csv:
                parts.append(f"{len(missing_in_csv)} instance(s) in Glyphs but not in CSV: {', '.join(sorted(missing_in_csv))}")
            if missing_in_glyphs:
                parts.append(f"{len(missing_in_glyphs)} instance(s) in CSV but not in Glyphs: {', '.join(sorted(missing_in_glyphs))}")
            message = "; ".join(parts)
        
        return {
            "synced": synced,
            "message": message,
            "glyphs_instances": sorted(glyphs_instances),
            "csv_instances": sorted(csv_instances),
            "missing_in_csv": sorted(missing_in_csv),
            "missing_in_glyphs": sorted(missing_in_glyphs)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "synced": False,
            "message": f"Error checking sync status: {str(e)}",
            "glyphs_instances": [],
            "csv_instances": []
        }


def _ensure_spac_column_in_csv(csv_path: Path) -> bool:
    """
    Ensure SPAC column exists in CSV, adding it if missing (initialize to 0).
    Returns True if column was added or already exists, False on error.
    """
    if not csv_path.exists():
        return False
    
    try:
        import csv
        # Read CSV
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        
        # Check if SPAC column exists
        if "SPAC" in fieldnames:
            return True  # Already exists
        
        # Add SPAC column
        fieldnames.append("SPAC")
        for row in rows:
            row["SPAC"] = "0"
        
        # Write updated CSV
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        _update_csv_modification_time(csv_path)
        print(f"Added SPAC column to preview CSV: {csv_path}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Warning: Could not add SPAC column to CSV: {e}", file=sys.stderr)
        return False


def _initialize_preview_csv_from_glyphs() -> Optional[Path]:
    """
    Initialize preview CSV from Glyphs file.
    Creates CSV with Instance Name and parametric axes (XTRA, XOPQ, YOPQ) from Glyphs instances.
    Only creates if CSV doesn't exist.
    Also ensures SPAC column exists (initialized to 0).
    """
    csv_path = _get_preview_csv_path()
    if not csv_path:
        return None
    
    # If CSV exists, ensure SPAC column is present
    if csv_path.exists():
        _ensure_spac_column_in_csv(csv_path)
        return csv_path
    
    if not GLYPHS_PATH or not GLYPHS_PATH.exists():
        return None
    
    try:
        import csv
        font = load(str(GLYPHS_PATH))
        
        # Get parametric axes from Glyphs file
        parametric_axes = []
        for axis in font.axes:
            if hasattr(axis, 'axisTag'):
                parametric_axes.append(axis.axisTag.upper())
        
        # Get instances from Glyphs file
        instances = []
        for instance in font.instances:
            if not instance.name:
                continue
            
            row = {"Instance Name": instance.name}
            
            # Get parametric axis values from instance
            if hasattr(instance, 'axes') and instance.axes:
                for i, axis in enumerate(font.axes):
                    if i < len(instance.axes):
                        tag = axis.axisTag.upper()
                        value = float(instance.axes[i])
                        row[tag] = value
            
            instances.append(row)
        
        # Write CSV (include SPAC column)
        if instances:
            fieldnames = ["Instance Name"] + parametric_axes + ["SPAC"]
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in instances:
                    # Ensure all parametric axes are present (fill missing with 0)
                    for axis in parametric_axes:
                        if axis not in row:
                            row[axis] = 0
                    # Initialize SPAC to 0
                    row["SPAC"] = 0
                    writer.writerow(row)
            
            print(f"Initialized preview CSV: {csv_path}", file=sys.stderr)
            return csv_path
    except Exception as e:
        print(f"Error initializing preview CSV: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    
    return None


def _initialize_preview_config_from_glyphs() -> Optional[Path]:
    """
    Initialize preview config.yaml from Glyphs file.
    Creates minimal config with sources, familyName, and fvarInstances from Glyphs.
    Only creates if config doesn't exist.
    """
    config_path = _get_preview_config_path()
    if not config_path:
        return None
    
    # Don't overwrite existing config
    if config_path.exists():
        return config_path
    
    if not GLYPHS_PATH or not GLYPHS_PATH.exists():
        return None
    
    try:
        import yaml
        font = load(str(GLYPHS_PATH))
        
        # Get family name
        family_name = font.familyName or GLYPHS_PATH.stem
        
        # Get fvarInstances from Glyphs file
        fvar_instances = []
        for instance in font.instances:
            if not instance.name:
                continue
            
            coords = {}
            if hasattr(instance, 'axes') and instance.axes:
                for i, axis in enumerate(font.axes):
                    if i < len(instance.axes):
                        tag = axis.axisTag.lower()
                        value = float(instance.axes[i])
                        coords[tag] = value
            
            if coords:
                fvar_instances.append({
                    "name": instance.name,
                    "coordinates": coords
                })
        
        # Build config structure
        # Get font filename - use format with axis tags (gftools builder expects this)
        # Get parametric axes from Glyphs file to include in filename
        parametric_tags = []
        for axis in font.axes:
            if hasattr(axis, 'axisTag'):
                parametric_tags.append(axis.axisTag.upper())
        # SPAC will be added later, but include it in filename format
        if parametric_tags:
            tags_str = ",".join(parametric_tags)
            font_filename = f"{family_name}[SPAC,{tags_str}].ttf"
        else:
            font_filename = f"{family_name}[SPAC].ttf"
        
        # Use absolute path for sources to avoid path issues
        sources_path = str(GLYPHS_PATH.resolve())
        
        config = {
            "sources": [sources_path],
            "familyName": family_name,
            "fvarInstances": {
                font_filename: fvar_instances
            }
        }
        
        # Write config
        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        print(f"Initialized preview config: {config_path}", file=sys.stderr)
        return config_path
    except Exception as e:
        print(f"Error initializing preview config: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    
    return None


def _check_spac_axis_in_font(font_path: Path) -> bool:
    """Check if SPAC axis exists in font's fvar table."""
    try:
        font = TTFont(str(font_path))
        if "fvar" not in font:
            return False
        
        fvar = font["fvar"]
        for axis in fvar.axes:
            if axis.axisTag == "SPAC":
                return True
        return False
    except Exception as e:
        print(f"Error checking SPAC axis in font: {e}", file=sys.stderr)
        return False


def _get_spac_axis_range_from_font(font_path: Path) -> Optional[Dict[str, float]]:
    """Get SPAC axis min/max/default values from font's fvar table.
    
    Returns dict with 'min', 'max', 'default' if SPAC axis exists, None otherwise.
    """
    try:
        font = TTFont(str(font_path))
        if "fvar" not in font:
            return None
        
        fvar = font["fvar"]
        for axis in fvar.axes:
            if axis.axisTag == "SPAC":
                return {
                    "min": float(axis.minValue),
                    "max": float(axis.maxValue),
                    "default": float(axis.defaultValue)
                }
        return None
    except Exception as e:
        print(f"Error getting SPAC axis range from font: {e}", file=sys.stderr)
        return None


def _load_axis_metadata() -> Dict[str, Dict[str, any]]:
    """Load axis metadata from JSON file. Auto-populates with Glyphs file axes if missing."""
    metadata_path = _get_avar2_metadata_path()
    if not metadata_path:
        return {}
    
    # Create file with empty dict if it doesn't exist
    if not metadata_path.exists():
        try:
            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)
        except Exception as e:
            print(f"Error creating axis metadata file: {e}", file=sys.stderr)
            return {}
    
    # Load existing metadata
    try:
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"Error loading axis metadata: {e}", file=sys.stderr)
        metadata = {}
    
    # Get parametric axes from Glyphs file and add to metadata if missing
    if GLYPHS_PATH and GLYPHS_PATH.exists():
        try:
            font = load(str(GLYPHS_PATH))
            metadata_updated = False
            
            for axis in font.axes:
                if hasattr(axis, 'axisTag'):
                    axis_tag_upper = axis.axisTag.upper()
                    axis_name = getattr(axis, 'name', axis_tag_upper) if hasattr(axis, 'name') else axis_tag_upper
                    
                    # If this parametric axis is not in metadata, add it
                    if axis_tag_upper not in metadata:
                        metadata[axis_tag_upper] = {
                            "display_name": axis_name,
                            "registered_tag": axis.axisTag.lower(),
                            "min": -1000,
                            "max": 1000,
                            "is_parametric": True  # Mark as parametric (from Glyphs file)
                        }
                        metadata_updated = True
                    else:
                        # Ensure existing entries are marked correctly
                        if "is_parametric" not in metadata[axis_tag_upper]:
                            metadata[axis_tag_upper]["is_parametric"] = True
                            metadata_updated = True
                        # Update display name from Glyphs if not user-modified
                        # (preserve user edits, but initialize from Glyphs)
                        if metadata[axis_tag_upper].get("display_name") == axis_tag_upper:
                            metadata[axis_tag_upper]["display_name"] = axis_name
                            metadata_updated = True
            
            # Save updated metadata if we added any parametric axes
            if metadata_updated:
                _save_axis_metadata(metadata)
        except Exception as e:
            print(f"Error reading axes from Glyphs file for metadata: {e}", file=sys.stderr)
    
    return metadata


def _save_axis_metadata(metadata: Dict[str, Dict[str, any]]) -> bool:
    """Save axis metadata to JSON file."""
    metadata_path = _get_avar2_metadata_path()
    if not metadata_path:
        return False
    
    try:
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving axis metadata: {e}", file=sys.stderr)
        return False


def _check_csv_external_edit(csv_path: Path) -> bool:
    """Check if CSV was modified externally. Returns True if modified externally."""
    csv_str = str(csv_path)
    current_mtime = csv_path.stat().st_mtime if csv_path.exists() else 0
    
    if csv_str in _CSV_MODIFICATION_TIMES:
        if current_mtime > _CSV_MODIFICATION_TIMES[csv_str]:
            return True
    
    _CSV_MODIFICATION_TIMES[csv_str] = current_mtime
    return False


def _update_csv_modification_time(csv_path: Path) -> None:
    """Update tracked modification time after we write to CSV."""
    csv_str = str(csv_path)
    if csv_path.exists():
        _CSV_MODIFICATION_TIMES[csv_str] = csv_path.stat().st_mtime


def _validate_axis_tag(tag: str) -> tuple[bool, Optional[str]]:
    """Validate OpenType axis tag. Returns (is_valid, error_message)."""
    if not tag:
        return False, "Tag cannot be empty"
    if len(tag) != 4:
        return False, "Tag must be exactly 4 characters"
    if not tag.islower():
        return False, "Tag must be lowercase"
    if not tag.isalnum():
        return False, "Tag must contain only alphanumeric characters"
    return True, None


def _get_glyphs_axis_tags() -> set:
    """Get set of axis tags from Glyphs file (source of truth for parametric axes)."""
    if not GLYPHS_PATH or not GLYPHS_PATH.exists():
        return set()
    
    try:
        font = load(str(GLYPHS_PATH))
        axis_tags = set()
        # Get axis tags directly from font.axes
        for axis in font.axes:
            if hasattr(axis, 'axisTag'):
                axis_tags.add(axis.axisTag.lower())
        return axis_tags
    except Exception as e:
        print(f"Error reading axes from Glyphs file: {e}", file=sys.stderr)
        return set()


def _add_missing_instance_to_csv(instance_name: str, glyphs_coords: Dict[str, float], csv_path: Path) -> bool:
    """Add a missing instance to CSV with blank traditional axis values."""
    import csv
    import importlib.util
    try:
        # Use normalized read function
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        rows, fieldnames, in_cols, out_cols, _ = match_module.read_csv_mappings(csv_path, GLYPHS_PATH)
        
        if not fieldnames:
            return False
        
        # Create new row with instance name
        new_row = {"Instance Name": instance_name}
        
        # Initialize all columns (use normalized fieldnames)
        for col in fieldnames:
            if col == "Instance Name":
                continue
            elif col in in_cols:
                # Traditional axes: blank
                new_row[col] = ""
            elif col in out_cols:
                # Parametric axes: use value from Glyphs (match by uppercase)
                # Find matching glyphs coordinate (case-insensitive)
                glyphs_key = None
                for glyphs_tag in glyphs_coords.keys():
                    if glyphs_tag.upper() == col:
                        glyphs_key = glyphs_tag
                        break
                if glyphs_key:
                    new_row[col] = str(glyphs_coords[glyphs_key])
                else:
                    new_row[col] = ""
            else:
                # Other columns: blank
                new_row[col] = ""
        
        # Add new row
        rows.append(new_row)
        
        # Write updated CSV (use normalized fieldnames)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return True
    except Exception as e:
        print(f"Error adding instance to CSV: {e}", file=sys.stderr)
        return False


@app.route('/api/avar2/instances', methods=['GET'])
def get_avar2_instances():
    """Get instances matched to avar2 mappings. Automatically adds missing instances to CSV."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({
                "error": "avar2-mappings.csv not found",
                "suggestion": "Set CSV path or place avar2-mappings.csv in same directory as Glyphs file"
            }), 404
        
        # Import matching function
        import importlib.util
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        # Get Glyphs instances
        glyphs_instances = match_module.get_glyphs_instances(GLYPHS_PATH)
        
        # Get matches
        matches = match_module.match_instances(GLYPHS_PATH, csv_path)
        
        # Add missing instances to CSV
        added_count = 0
        for match in matches:
            if match.get("match_status") == "missing_in_csv":
                instance_name = match["instance_name"]
                glyphs_coords = match.get("glyphs_coordinates", {})
                if _add_missing_instance_to_csv(instance_name, glyphs_coords, csv_path):
                    added_count += 1
        
        # If we added instances, reload matches
        if added_count > 0:
            matches = match_module.match_instances(GLYPHS_PATH, csv_path)
        
        return jsonify({
            "instances": matches,
            "csv_path": str(csv_path),
            "added_instances": added_count
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/avar2/mappings', methods=['GET'])
def get_avar2_mappings():
    """Get all avar2 mappings from CSV."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({
                "error": "avar2-mappings.csv not found"
            }), 404
        
        import importlib.util
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        rows, fieldnames, in_cols, out_cols, _ = match_module.read_csv_mappings(csv_path, GLYPHS_PATH)
        
        return jsonify({
            "mappings": rows,
            "fieldnames": fieldnames,
            "traditional_axes": in_cols,
            "parametric_axes": out_cols
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/avar2/axes', methods=['GET'])
def get_avar2_axes():
    """Get traditional axes (in:) and parametric axes (out:) from CSV, including metadata."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({
                "error": "avar2-mappings.csv not found"
            }), 404
        
        import importlib.util
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        _, _, in_cols, out_cols, _ = match_module.read_csv_mappings(csv_path, GLYPHS_PATH)
        
        # Normalize traditional axis names
        traditional_axes = [match_module._normalize_in_axis_name(col) for col in in_cols]
        
        # Load metadata
        metadata = _load_axis_metadata()
        
        # Get parametric axes from Glyphs file and populate metadata
        glyphs_axes_info = {}
        if GLYPHS_PATH and GLYPHS_PATH.exists():
            try:
                font = load(str(GLYPHS_PATH))
                # Calculate min/max from masters
                axis_ranges = {}
                for axis in font.axes:
                    if hasattr(axis, 'axisTag'):
                        tag = axis.axisTag
                        axis_ranges[tag] = {'min': float('inf'), 'max': float('-inf')}
                
                for master in font.masters:
                    if hasattr(master, 'axes') and master.axes:
                        for i, axis in enumerate(font.axes):
                            if i < len(master.axes):
                                tag = axis.axisTag
                                value = float(master.axes[i])
                                axis_ranges[tag]['min'] = min(axis_ranges[tag]['min'], value)
                                axis_ranges[tag]['max'] = max(axis_ranges[tag]['max'], value)
                
                # Build axes info with min/max from masters
                for axis in font.axes:
                    if hasattr(axis, 'axisTag'):
                        tag = axis.axisTag.upper()
                        ranges = axis_ranges[axis.axisTag]
                        glyphs_axes_info[tag] = {
                            "display_name": axis.name if hasattr(axis, 'name') and axis.name else tag,
                            "registered_tag": axis.axisTag.lower(),
                            "is_parametric": True,
                            "min": ranges['min'] if ranges['min'] != float('inf') else 0.0,
                            "max": ranges['max'] if ranges['max'] != float('-inf') else 1000.0
                        }
            except Exception as e:
                print(f"Warning: Could not read axes from Glyphs file: {e}", file=sys.stderr)
        
        # Build axes with metadata
        # If axis doesn't exist in metadata, create default entry and save it
        axes_with_metadata = {}
        metadata_updated = False
        
        # First, populate parametric axes from Glyphs file (these are in out_cols)
        for col in out_cols:
            col_upper = col.upper()
            if col_upper in glyphs_axes_info:
                # This is a parametric axis from Glyphs file
                glyphs_info = glyphs_axes_info[col_upper]
                if col_upper not in metadata:
                    metadata[col_upper] = {
                        "display_name": glyphs_info["display_name"],
                        "registered_tag": glyphs_info["registered_tag"],
                        "is_parametric": True,
                        "min": glyphs_info.get("min", 0.0),
                        "max": glyphs_info.get("max", 1000.0)
                    }
                    metadata_updated = True
                else:
                    # Update existing entry to mark as parametric and sync from Glyphs
                    if metadata[col_upper].get("is_parametric") != True:
                        metadata[col_upper]["is_parametric"] = True
                        metadata_updated = True
                    # Always update display_name, registered_tag, min, and max from Glyphs (source of truth)
                    if metadata[col_upper].get("display_name") != glyphs_info["display_name"]:
                        metadata[col_upper]["display_name"] = glyphs_info["display_name"]
                        metadata_updated = True
                    if metadata[col_upper].get("registered_tag") != glyphs_info["registered_tag"]:
                        metadata[col_upper]["registered_tag"] = glyphs_info["registered_tag"]
                        metadata_updated = True
                    # Update min/max from Glyphs (parametric axes should always match Glyphs)
                    if metadata[col_upper].get("min") != glyphs_info.get("min", 0.0):
                        metadata[col_upper]["min"] = glyphs_info.get("min", 0.0)
                        metadata_updated = True
                    if metadata[col_upper].get("max") != glyphs_info.get("max", 1000.0):
                        metadata[col_upper]["max"] = glyphs_info.get("max", 1000.0)
                        metadata_updated = True
                axes_with_metadata[col_upper] = metadata[col_upper]
            else:
                # Parametric axis not found in Glyphs (shouldn't happen, but handle gracefully)
                if col_upper not in metadata:
                    normalized_tag = match_module._normalize_in_axis_name(col)
                    metadata[col_upper] = {
                        "display_name": col,
                        "registered_tag": normalized_tag,
                        "is_parametric": True,
                        "min": -1000,
                        "max": 1000
                    }
                    metadata_updated = True
                axes_with_metadata[col_upper] = metadata[col_upper]
        
        # Then, handle traditional axes (not in Glyphs file)
        # Map of normalized tags to default display names
        default_display_names = {
            "wght": "Weight",
            "wdth": "Width",
            "opsz": "Optical Size",
            "cntr": "Contrast",
            "spac": "Spacing",
            "grad": "Grade",
            "slnt": "Slant",
            "ital": "Italic"
        }
        
        for col in in_cols:
            if col not in metadata:
                # Create default entry for traditional axis (not in Glyphs file)
                normalized_tag = match_module._normalize_in_axis_name(col)
                # Use proper display name if available, otherwise use column name
                default_display_name = default_display_names.get(normalized_tag.lower(), col)
                metadata[col] = {
                    "display_name": default_display_name,
                    "registered_tag": normalized_tag,
                    "min": -1000,
                    "max": 1000,
                    "is_parametric": False  # Mark as traditional (not in Glyphs file)
                }
                metadata_updated = True
            else:
                # Ensure is_parametric flag exists for existing entries
                if "is_parametric" not in metadata[col]:
                    # Check if it's actually parametric (exists in Glyphs)
                    normalized_tag = match_module._normalize_in_axis_name(col)
                    glyphs_axis_tags = _get_glyphs_axis_tags()
                    metadata[col]["is_parametric"] = normalized_tag in glyphs_axis_tags
                    metadata_updated = True
                
                # Update display_name if it's still the column name (tag) - migrate to proper display name
                normalized_tag = match_module._normalize_in_axis_name(col)
                if metadata[col].get("display_name") == col and normalized_tag.lower() in default_display_names:
                    metadata[col]["display_name"] = default_display_names[normalized_tag.lower()]
                    metadata_updated = True
            
            axes_with_metadata[col] = metadata[col]
        
        # Save updated metadata if we added any new axes
        if metadata_updated:
            _save_axis_metadata(metadata)
        
        return jsonify({
            "traditional_axes": {
                "columns": in_cols,
                "normalized": traditional_axes
            },
            "parametric_axes": out_cols,  # All parametric axes from Glyphs file
            "metadata": axes_with_metadata  # Includes all axes with is_parametric flag
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/instance/<instance_name>/editing', methods=['POST'])
def register_editing_instance(instance_name: str):
    """Register an instance as being edited (protect from sync)."""
    global EDITING_INSTANCES
    EDITING_INSTANCES.add(instance_name)
    return jsonify({"success": True, "message": f"Instance '{instance_name}' registered as editing"})

@app.route('/api/instance/<instance_name>/editing', methods=['DELETE'])
def unregister_editing_instance(instance_name: str):
    """Unregister an instance from editing (allow sync)."""
    global EDITING_INSTANCES
    EDITING_INSTANCES.discard(instance_name)
    return jsonify({"success": True, "message": f"Instance '{instance_name}' unregistered from editing"})

@app.route('/api/avar2/sync-csv', methods=['POST'])
def sync_csv():
    """Update CSV parametric values to match Glyphs file."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({
                "error": "avar2-mappings.csv not found"
            }), 404
        
        # Use existing sync script via subprocess, skipping editing instances
        import subprocess
        import json as json_module
        
        # Pass editing instances via environment variable (since subprocess doesn't support sets)
        env = os.environ.copy()
        if EDITING_INSTANCES:
            env['SKIP_INSTANCES'] = json_module.dumps(list(EDITING_INSTANCES))
        
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "sync-glyphs-to-avar2.py"),
                "--glyphs", str(GLYPHS_PATH),
                "--csv", str(csv_path),
                "--once"
            ],
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode != 0:
            return jsonify({
                "error": "Failed to sync CSV",
                "details": result.stderr
            }), 500
        
        return jsonify({
            "success": True,
            "csv_path": str(csv_path),
            "output": result.stdout,
            "skipped_instances": list(EDITING_INSTANCES)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/avar2/axis', methods=['POST'])
def add_avar2_axis():
    """Add a new traditional axis to the CSV."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({"error": "avar2-mappings.csv not found"}), 404
        
        # Check for external edits
        if _check_csv_external_edit(csv_path):
            return jsonify({
                "error": "CSV was modified externally. Please reload.",
                "reload_required": True
            }), 409
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        axis_name = data.get("axis_name")  # CSV column header (e.g., "WGHT")
        display_name = data.get("display_name", axis_name)  # Display name (e.g., "Weight")
        registered_tag = data.get("registered_tag", "").lower()  # OpenType tag (e.g., "wght")
        default_value = data.get("default_value", 0)
        min_value = data.get("min", -1000)
        max_value = data.get("max", 1000)
        
        # Validate inputs
        if not axis_name:
            return jsonify({"error": "axis_name is required"}), 400
        
        is_valid, error_msg = _validate_axis_tag(registered_tag)
        if not is_valid:
            return jsonify({"error": f"Invalid registered tag: {error_msg}"}), 400
        
        # Check if tag exists in Glyphs file (parametric axes) - cannot add traditional axis with same tag
        glyphs_axis_tags = _get_glyphs_axis_tags()
        if registered_tag.lower() in glyphs_axis_tags:
            return jsonify({
                "error": f"Registered tag '{registered_tag}' already exists in Glyphs file as a parametric axis. Traditional axes cannot use tags that exist in the Glyphs file."
            }), 400
        
        if min_value < -1000 or min_value > 1000:
            return jsonify({"error": "min must be between -1000 and 1000"}), 400
        if max_value < -1000 or max_value > 1000:
            return jsonify({"error": "max must be between -1000 and 1000"}), 400
        if min_value >= max_value:
            return jsonify({"error": "min must be less than max"}), 400
        
        # Check for duplicate registered tags in existing metadata
        metadata = _load_axis_metadata()
        for existing_axis, existing_meta in metadata.items():
            if existing_meta.get("registered_tag") == registered_tag and existing_axis != axis_name_normalized:
                return jsonify({"error": f"Registered tag '{registered_tag}' already used by axis '{existing_axis}'"}), 400
        
        # Read CSV using normalized function
        import importlib.util
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        rows, fieldnames, _, _, fieldname_mapping = match_module.read_csv_mappings(csv_path, GLYPHS_PATH)
        
        # Normalize axis_name to uppercase for consistency
        axis_name_normalized = axis_name.upper()
        
        # Check if axis already exists (case-insensitive)
        if axis_name_normalized in fieldnames:
            return jsonify({"error": f"Axis '{axis_name}' already exists"}), 400
        
        # Add new column to CSV (use normalized name)
        fieldnames.append(axis_name_normalized)
        for row in rows:
            row[axis_name_normalized] = str(default_value)
        
        # Write updated CSV (use normalized fieldnames)
        import csv
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        _update_csv_modification_time(csv_path)
        
        # Save metadata (use normalized name)
        # Check if this is a parametric axis (shouldn't happen, but be safe)
        is_parametric = False
        glyphs_axis_tags = _get_glyphs_axis_tags()
        if registered_tag.lower() in glyphs_axis_tags:
            is_parametric = True
        
        metadata[axis_name_normalized] = {
            "display_name": display_name,
            "registered_tag": registered_tag,
            "is_parametric": is_parametric,
            "min": min_value,
            "max": max_value
        }
        _save_axis_metadata(metadata)
        
        return jsonify({
            "success": True,
            "axis_name": axis_name_normalized,
            "metadata": metadata[axis_name_normalized]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/avar2/axis/<axis_name>', methods=['PUT'])
def update_avar2_axis(axis_name: str):
    """Update axis metadata. Cannot edit axes that exist in Glyphs file (parametric axes)."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({"error": "avar2-mappings.csv not found"}), 404
        
        # Check for external edits
        if _check_csv_external_edit(csv_path):
            return jsonify({
                "error": "CSV was modified externally. Please reload.",
                "reload_required": True
            }), 409
        
        # Check if this axis exists in Glyphs file (parametric axis) - cannot edit
        import importlib.util
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        _, _, in_cols, out_cols, _ = match_module.read_csv_mappings(csv_path, GLYPHS_PATH)
        
        # Normalize axis_name to uppercase for lookup
        axis_name_normalized = axis_name.upper()
        
        # If axis is in parametric axes (exists in Glyphs file), cannot edit
        if axis_name_normalized in out_cols:
            return jsonify({
                "error": f"Cannot edit axis '{axis_name}' - it exists in the Glyphs file as a parametric axis. Parametric axes are managed in the Glyphs file, not in avar2 mappings."
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        new_display_name = data.get("display_name")
        new_registered_tag = data.get("registered_tag", "").lower()
        new_min = data.get("min")
        new_max = data.get("max")
        
        # Normalize axis_name to uppercase for lookup
        axis_name_normalized = axis_name.upper()
        
        # Load metadata
        metadata = _load_axis_metadata()
        if axis_name_normalized not in metadata:
            return jsonify({"error": f"Axis '{axis_name}' not found in metadata"}), 404
        
        # Validate registered tag if provided
        if new_registered_tag:
            is_valid, error_msg = _validate_axis_tag(new_registered_tag)
            if not is_valid:
                return jsonify({"error": f"Invalid registered tag: {error_msg}"}), 400
            
            # Check if tag exists in Glyphs file (parametric axes) - cannot use same tag
            glyphs_axis_tags = _get_glyphs_axis_tags()
            if new_registered_tag.lower() in glyphs_axis_tags:
                return jsonify({
                    "error": f"Registered tag '{new_registered_tag}' already exists in Glyphs file as a parametric axis. Traditional axes cannot use tags that exist in the Glyphs file."
                }), 400
            
            # Check for duplicate tags in existing metadata
            for existing_axis, existing_meta in metadata.items():
                if existing_axis != axis_name_normalized and existing_meta.get("registered_tag") == new_registered_tag:
                    return jsonify({"error": f"Registered tag '{new_registered_tag}' already used by axis '{existing_axis}'"}), 400
        
        # Validate min/max if provided
        if new_min is not None:
            if new_min < -1000 or new_min > 1000:
                return jsonify({"error": "min must be between -1000 and 1000"}), 400
        if new_max is not None:
            if new_max < -1000 or new_max > 1000:
                return jsonify({"error": "max must be between -1000 and 1000"}), 400
        if new_min is not None and new_max is not None and new_min >= new_max:
            return jsonify({"error": "min must be less than max"}), 400
        
        # Read CSV
        import csv
        rows = []
        fieldnames = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else []
            for row in reader:
                rows.append(row)
        
        if axis_name not in fieldnames:
            return jsonify({"error": f"Axis '{axis_name}' not found in CSV"}), 404
        
        # Update metadata (use normalized name)
        if axis_name_normalized not in metadata:
            # Create metadata entry if it doesn't exist
            metadata[axis_name_normalized] = {
                "display_name": axis_name_normalized,
                "registered_tag": match_module._normalize_in_axis_name(axis_name_normalized),
                "min": -1000,
                "max": 1000
            }
        
        current_meta = metadata[axis_name_normalized]
        if new_display_name:
            current_meta["display_name"] = new_display_name
        if new_registered_tag:
            old_tag = current_meta.get("registered_tag")
            current_meta["registered_tag"] = new_registered_tag
        if new_min is not None:
            current_meta["min"] = new_min
        if new_max is not None:
            current_meta["max"] = new_max
        
        # Ensure is_parametric flag is preserved (don't allow changing it via edit)
        # It should already be set correctly from initialization
        
        # If axis_name was different case, update metadata key
        if axis_name_normalized != axis_name and axis_name in metadata:
            del metadata[axis_name]
        
        metadata[axis_name_normalized] = current_meta
        _save_axis_metadata(metadata)
        
        # Write CSV back (use normalized fieldnames)
        import csv
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        _update_csv_modification_time(csv_path)
        
        return jsonify({
            "success": True,
            "axis_name": axis_name_normalized,
            "metadata": current_meta
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/avar2/mapping/<instance_name>/<axis_name>', methods=['PUT'])
def update_avar2_mapping(instance_name: str, axis_name: str):
    """Update a single cell value in the CSV."""
    try:
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({"error": "avar2-mappings.csv not found"}), 404
        
        # Check for external edits
        if _check_csv_external_edit(csv_path):
            return jsonify({
                "error": "CSV was modified externally. Please reload.",
                "reload_required": True
            }), 409
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        new_value = data.get("value")
        if new_value is None:
            return jsonify({"error": "value is required"}), 400
        
        # Validate value is numeric
        try:
            float_value = float(new_value)
        except (ValueError, TypeError):
            return jsonify({"error": "value must be a number"}), 400
        
        # Normalize axis_name to uppercase for lookup
        axis_name_normalized = axis_name.upper()
        
        # Load metadata to check range
        metadata = _load_axis_metadata()
        if axis_name_normalized in metadata:
            axis_meta = metadata[axis_name_normalized]
            min_val = axis_meta.get("min", -1000)
            max_val = axis_meta.get("max", 1000)
            if float_value < min_val or float_value > max_val:
                return jsonify({
                    "error": f"Value {float_value} is outside allowed range [{min_val}, {max_val}]"
                }), 400
        
        # Read CSV using normalized function
        import importlib.util
        match_script = Path(__file__).parent / "match-instances-to-avar2.py"
        spec = importlib.util.spec_from_file_location("match_instances_to_avar2", match_script)
        match_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(match_module)
        
        rows, fieldnames, _, _, _ = match_module.read_csv_mappings(csv_path, GLYPHS_PATH)
        
        if axis_name_normalized not in fieldnames:
            return jsonify({"error": f"Axis '{axis_name}' not found in CSV"}), 404
        
        # Find and update the instance
        instance_found = False
        for row in rows:
            if row.get("Instance Name", "").strip() == instance_name:
                row[axis_name_normalized] = str(float_value)
                instance_found = True
                break
        
        if not instance_found:
            return jsonify({"error": f"Instance '{instance_name}' not found in CSV"}), 404
        
        # Write updated CSV (use normalized fieldnames)
        import csv
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        _update_csv_modification_time(csv_path)
        
        return jsonify({
            "success": True,
            "instance_name": instance_name,
            "axis_name": axis_name_normalized,
            "value": float_value
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/spacing/init', methods=['POST'])
def init_spac_axis():
    """Initialize SPAC axis: add SPAC column to CSV (all instances = 0) and update config.yaml."""
    try:
        csv_path = _get_preview_csv_path()
        config_path = _get_preview_config_path()
        if not csv_path or not config_path:
            return jsonify({"error": "Preview CSV or config not found"}), 404
        
        # Read CSV
        rows = []
        fieldnames = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else []
            for row in reader:
                rows.append(row)
        
        # Check if SPAC column already exists
        if "SPAC" in fieldnames:
            return jsonify({
                "success": True,
                "message": "SPAC column already exists",
                "initialized": False
            })
        
        # Add SPAC column with 0 for all instances
        fieldnames.append("SPAC")
        for row in rows:
            row["SPAC"] = "0"
        
        # Write updated CSV
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Update modification time cache to prevent false "external edit" detection
        _update_csv_modification_time(csv_path)
        
        # Update config.yaml to add spacingAxis section
        if yaml:
            with config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            
            config["spacingAxis"] = {
                "min": -100,
                "max": 100
            }
            
            with config_path.open("w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        return jsonify({
            "success": True,
            "initialized": True,
            "message": "SPAC axis initialized"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/spacing/check', methods=['GET'])
def check_spac_axis():
    """Check if SPAC axis exists in designspace font and return its range."""
    try:
        # Check designspace-generated font first (correct range 0-100)
        spac_font_dir = _get_spac_font_dir()
        if spac_font_dir:
            spac_font_path = spac_font_dir / "Crispy-SPAC-VF.ttf"
            if spac_font_path.exists():
                has_spac = _check_spac_axis_in_font(spac_font_path)
                spac_range = None
                if has_spac:
                    spac_range = _get_spac_axis_range_from_font(spac_font_path)
                
                result = {
                    "exists": has_spac,
                    "font_path": str(spac_font_path)
                }
                if spac_range:
                    result["range"] = spac_range
                
                return jsonify(result)
        
        # Fallback to preview font directory
        preview_font_dir = _get_preview_font_dir()
        if not preview_font_dir:
            return jsonify({"exists": False, "error": "Preview font directory not found"}), 404
        
        # Look for preview font files, prefer one with SPAC in filename
        font_files = list(preview_font_dir.glob("*.ttf"))
        if not font_files:
            return jsonify({"exists": False})
        
        # Prefer font with SPAC in filename, otherwise use most recent
        spac_font = None
        for font_file in font_files:
            if "SPAC" in font_file.name:
                spac_font = font_file
                break
        
        if not spac_font:
            spac_font = max(font_files, key=lambda p: p.stat().st_mtime)
        
        has_spac = _check_spac_axis_in_font(spac_font)
        spac_range = None
        if has_spac:
            spac_range = _get_spac_axis_range_from_font(spac_font)
        
        result = {
            "exists": has_spac,
            "font_path": str(spac_font)
        }
        if spac_range:
            result["range"] = spac_range
        
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/spacing/values', methods=['GET'])
def get_spac_values():
    """Get SPAC values for all instances from preview CSV."""
    try:
        csv_path = _get_preview_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({"error": "Preview CSV not found"}), 404
        
        rows = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                instance_name = row.get("Instance Name", "").strip()
                spac_value = row.get("SPAC", "0").strip()
                try:
                    spac_float = float(spac_value) if spac_value else 0.0
                except ValueError:
                    spac_float = 0.0
                rows.append({
                    "instance_name": instance_name,
                    "spac": spac_float
                })
        
        return jsonify({"values": rows})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/spacing/instance/<instance_name>', methods=['PUT'])
def update_spac_value(instance_name: str):
    """Update SPAC value for a specific instance."""
    try:
        csv_path = _get_preview_csv_path()
        if not csv_path or not csv_path.exists():
            return jsonify({"error": "Preview CSV not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        new_value = data.get("value")
        if new_value is None:
            return jsonify({"error": "value is required"}), 400
        
        # Validate value
        try:
            float_value = float(new_value)
            if float_value < -100 or float_value > 100:
                return jsonify({"error": "SPAC value must be between -100 and 100"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "value must be a number"}), 400
        
        # Read CSV
        rows = []
        fieldnames = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else []
            for row in reader:
                rows.append(row)
        
        # Ensure SPAC column exists
        if "SPAC" not in fieldnames:
            fieldnames.append("SPAC")
            for row in rows:
                if "SPAC" not in row:
                    row["SPAC"] = "0"
        
        # Find and update instance
        instance_found = False
        for row in rows:
            if row.get("Instance Name", "").strip() == instance_name:
                row["SPAC"] = str(float_value)
                instance_found = True
                break
        
        if not instance_found:
            return jsonify({"error": f"Instance '{instance_name}' not found"}), 404
        
        # Write updated CSV
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Update modification time cache to prevent false "external edit" detection
        _update_csv_modification_time(csv_path)
        
        # Update config.yaml spacingAxis min/max based on all SPAC values
        _update_spacing_axis_range()
        
        return jsonify({
            "success": True,
            "instance_name": instance_name,
            "spac": float_value
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _update_spacing_axis_range():
    """Update config.yaml spacingAxis min/max to always be -100 to 100."""
    if not yaml:
        return
    
    csv_path = _get_preview_csv_path()
    config_path = _get_preview_config_path()
    if not csv_path or not csv_path.exists() or not config_path:
        return
    
    try:
        # Read config
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        # Always set spacingAxis to -100 to 100 (full range)
        config["spacingAxis"] = {
            "min": -100,
            "max": 100
        }
        
        # Write config back
        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        print(f"Error updating spacing axis range: {e}", file=sys.stderr)


@app.route('/api/spacing/rebuild', methods=['POST'])
def rebuild_preview_font_with_spac():
    """Rebuild preview font with SPAC axis using minimal config and fontc."""
    global BUILDING
    
    if BUILDING:
        return jsonify({"error": "Build already in progress"}), 409
    
    try:
        config_path = _get_preview_config_path()
        preview_font_dir = _get_preview_font_dir()
        if not config_path or not preview_font_dir:
            return jsonify({"error": "Preview config or font directory not found"}), 404
        
        if not USE_FONTC:
            return jsonify({"error": "fontc is required for preview font rebuild"}), 400
        
        # Check if fontc is available
        fontc_path = shutil.which("fontc")
        if not fontc_path:
            return jsonify({"error": "fontc not found in PATH"}), 400
        
        BUILDING = True
        
        # Build preview font directly with fontc, then add SPAC axis
        # Skip fix, BuildSTAT, and buildFvarInstances steps
        project_root = GLYPHS_PATH.parent.parent if GLYPHS_PATH else Path.cwd()
        
        # Step 1: Build variable font with fontc (no post-processing)
        temp_font = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
        temp_font_path = Path(temp_font.name)
        temp_font.close()
        
        fontc_cmd = [
            fontc_path,
            "--output-file", str(temp_font_path),
            str(GLYPHS_PATH.resolve()),
            "--flatten-components",
            "--decompose-transformed-components"
        ]
        
        fontc_result = subprocess.run(
            fontc_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if fontc_result.returncode != 0:
            BUILDING = False
            if temp_font_path.exists():
                temp_font_path.unlink()
            return jsonify({
                "error": "fontc build failed",
                "details": fontc_result.stderr
            }), 500
        
        if not temp_font_path.exists():
            BUILDING = False
            return jsonify({"error": "fontc did not produce output file"}), 500
        
        # Step 2: Add SPAC axis using gftools-gen-spac
        # Get spacingAxis min/max from config
        spacing_min = -100
        spacing_max = 100
        if yaml and config_path.exists():
            try:
                with config_path.open("r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                    if "spacingAxis" in config:
                        spacing_min = config["spacingAxis"].get("min", -100)
                        spacing_max = config["spacingAxis"].get("max", 100)
            except Exception as e:
                print(f"Warning: Could not read spacingAxis from config: {e}", file=sys.stderr)
        
        # Step 2: Add SPAC axis using gftools-gen-spac (inplace to temp file, then copy)
        # Use --inplace to modify temp file directly
        spac_cmd = [
            "gftools-gen-spac",
            "--inplace",
            str(temp_font_path),
            str(int(spacing_min)),
            str(int(spacing_max))
        ]
        
        spac_result = subprocess.run(
            spac_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        BUILDING = False
        
        if spac_result.returncode != 0:
            if temp_font_path.exists():
                temp_font_path.unlink()
            return jsonify({
                "error": "SPAC axis addition failed",
                "details": spac_result.stderr
            }), 500
        
        # Generate preview font filename with SPAC
        family_name = GLYPHS_PATH.stem
        preview_font_path = preview_font_dir / f"{family_name}[SPAC].ttf"
        
        # Copy temp font to preview directory
        shutil.copy2(temp_font_path, preview_font_path)
        
        # Clean up temp file
        if temp_font_path.exists():
            temp_font_path.unlink()
        
        final_font = preview_font_path
        
        has_spac = _check_spac_axis_in_font(final_font)
        
        return jsonify({
            "success": True,
            "font_path": str(final_font),
            "has_spac": has_spac,
            "output": f"fontc: {fontc_result.stdout}\ngftools-gen-spac: {spac_result.stdout}"
        })
    except subprocess.TimeoutExpired:
        BUILDING = False
        return jsonify({"error": "Build timeout"}), 500
    except Exception as e:
        BUILDING = False
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/check-sync-status', methods=['GET'])
def check_sync_status():
    """Check if preview CSV is synced with Glyphs file."""
    try:
        status = _check_preview_csv_sync_status()
        return jsonify(status)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/build-avar2', methods=['POST'])
def build_avar2_font():
    """Build avar2 font from preview CSV with selected axes."""
    global BUILDING
    
    if BUILDING:
        return jsonify({"error": "Build already in progress"}), 409
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Get selected axes
        selected_traditional_axes = data.get("traditional_axes", [])  # e.g., ["wght", "wdth", "opsz", "cntr"]
        selected_avar2_axes = data.get("avar2_axes", [])  # e.g., ["XTRA", "XOPQ", "YOPQ"]
        include_spac = data.get("include_spac", True)  # SPAC axis (always available)
        
        if not selected_traditional_axes:
            return jsonify({"error": "At least one traditional axis must be selected"}), 400
        
        # Check sync status - CSV must be synced with Glyphs before building
        sync_status = _check_preview_csv_sync_status()
        if not sync_status.get("synced", False):
            return jsonify({
                "error": "CSV is not synced with Glyphs file",
                "details": sync_status.get("message", "Unknown sync error"),
                "sync_status": sync_status
            }), 400
        
        # Get paths
        preview_csv = _get_preview_csv_path()
        if not preview_csv or not preview_csv.exists():
            return jsonify({"error": "Preview CSV not found"}), 404
        
        avar2_font_dir = _get_avar2_font_dir()
        if not avar2_font_dir:
            return jsonify({"error": "Could not create avar2 font directory"}), 500
        
        BUILDING = True
        
        try:
            # Get preview config path - this is what we'll update and build from
            preview_config_path = _get_preview_config_path()
            if not preview_config_path or not preview_config_path.exists():
                # Fallback to sources/config.yaml if preview config doesn't exist
                base_config_path = Path.cwd() / "sources" / "config.yaml"
                if not base_config_path.exists():
                    return jsonify({"error": "Neither preview-app/config-preview.yaml nor sources/config.yaml found"}), 404
                # If using sources/config.yaml, update it in place
                config_to_update = base_config_path
            else:
                # Use preview-app/config-preview.yaml - update it in place
                config_to_update = preview_config_path
            
            # Update config-preview.yaml with CSV values BEFORE copying
            # This ensures config-preview.yaml stays in sync with CSV
            # CSV is already validated to be synced with Glyphs above
            update_config_script = Path.cwd() / "sources" / "update_config.py"
            update_config_cmd = [
                sys.executable,
                str(update_config_script),
                "--csv", str(preview_csv),
                "--config", str(config_to_update),
                "--no-backup"
            ]
            
            result = subprocess.run(
                update_config_cmd,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd())
            )
            
            if result.returncode != 0:
                BUILDING = False
                return jsonify({
                    "error": "Failed to update config",
                    "details": result.stderr
                }), 500
            
            # Ensure config file has correct Glyphs path
            # gftools builder resolves paths relative to config file location
            # Since config-preview.yaml is in preview-app/, use ../sources/Crispy.glyphs
            import yaml as yaml_module
            with config_to_update.open('r', encoding='utf-8') as f:
                config_content = yaml_module.safe_load(f)
            
            # Determine correct path based on config file location
            sources_list = config_content.get('sources', [])
            needs_update = False
            if sources_list:
                first_source = str(sources_list[0])
                # If config is in preview-app/, use relative path from there
                if 'preview-app' in str(config_to_update) or 'preview_app' in str(config_to_update):
                    if '../sources/Crispy.glyphs' not in first_source and 'sources/Crispy.glyphs' == first_source:
                        # Update to use relative path from preview-app/ directory
                        config_content['sources'] = ['../sources/Crispy.glyphs']
                        needs_update = True
                else:
                    # Config is in sources/, use relative path from there
                    if 'Crispy.glyphs' == first_source or first_source.endswith('Crispy.glyphs'):
                        # Keep as is or update to just Crispy.glyphs
                        if first_source != 'Crispy.glyphs':
                            config_content['sources'] = ['Crispy.glyphs']
                            needs_update = True
            
            if needs_update:
                with config_to_update.open('w', encoding='utf-8') as f:
                    yaml_module.dump(config_content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            # Build font using gftools builder directly from config-preview.yaml
            # gftools builder creates fonts/ directory relative to where it runs (project root)
            fontc_path = shutil.which("fontc")
            if not fontc_path:
                BUILDING = False
                return jsonify({"error": "fontc not found in PATH"}), 500
            
            builder_cmd = [
                "gftools", "builder",
                "--experimental-fontc", fontc_path,
                str(config_to_update.resolve())  # Use absolute path to config-preview.yaml
            ]
            
            result = subprocess.run(
                builder_cmd,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd())  # Run from project root
            )
            
            if result.returncode != 0:
                BUILDING = False
                error_details = result.stderr or result.stdout or "No error details available"
                return jsonify({
                    "error": "Font build failed",
                    "details": error_details,
                    "stdout": result.stdout[:1000] if result.stdout else None,
                    "stderr": result.stderr[:1000] if result.stderr else None,
                    "returncode": result.returncode
                }), 500
            
            # gftools builder outputs to fonts/variable/ in project root
            # Move the font to preview-app/fonts-avar2/variable/
            project_fonts_dir = Path.cwd() / "fonts" / "variable"
            built_font = project_fonts_dir / "Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf"
            
            if not built_font.exists():
                BUILDING = False
                return jsonify({
                    "error": "Built font not found",
                    "details": f"Expected at {built_font}. gftools builder output: {result.stdout[:500]}"
                }), 500
            
            # Ensure avar2 font directory exists
            avar2_font_dir.mkdir(parents=True, exist_ok=True)
            
            # Move font to preview-app/fonts-avar2/variable/
            font_file = avar2_font_dir / "Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf"
            shutil.move(str(built_font), str(font_file))
            
            BUILDING = False
            
            return jsonify({
                "success": True,
                "font_path": str(font_file),
                "sync_status": sync_status,
                "message": "Avar2 font built successfully"
            })
            
        except Exception as e:
            BUILDING = False
            raise
            
    except Exception as e:
        BUILDING = False
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/avar2-font', methods=['GET'])
def get_avar2_font():
    """Serve the avar2 font file."""
    avar2_font_dir = _get_avar2_font_dir()
    if not avar2_font_dir or not avar2_font_dir.exists():
        return jsonify({"error": "Avar2 font directory not found"}), 404
    
    # Look for the avar2 font
    font_file = avar2_font_dir / "Crispy[SPAC,XOPQ,XTRA,YOPQ].ttf"
    
    if not font_file.exists():
        return jsonify({"error": "Avar2 font not built yet"}), 404
    
    return send_file(
        str(font_file),
        mimetype="font/ttf",
        as_attachment=False,
        download_name=font_file.name
    )


def main():
    global GLYPHS_PATH, BUILD_DIR, CSV_PATH
    
    parser = argparse.ArgumentParser(description="Glyphs preview server")
    parser.add_argument(
        "--glyphs",
        type=Path,
        default=Path("sources/Crispy.glyphs"),
        help="Path to Glyphs file (default: sources/Crispy.glyphs)"
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=Path("preview-app/preview-fonts"),
        help="Directory for built fonts (default: preview-app/preview-fonts)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to run server on (default: 5001, avoiding macOS AirPlay on 5000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to avar2-mappings.csv (default: same directory as Glyphs file)"
    )
    parser.add_argument(
        "--no-fontc",
        action="store_true",
        help="Disable fontc and use fontmake only"
    )
    
    args = parser.parse_args()
    
    global USE_FONTC
    GLYPHS_PATH = args.glyphs.resolve()
    BUILD_DIR = args.build_dir.resolve()
    USE_FONTC = not args.no_fontc  # Use fontc unless --no-fontc is specified
    
    if args.csv:
        CSV_PATH = args.csv.resolve()
    else:
        CSV_PATH = None  # Will use default location
    
    if not GLYPHS_PATH.exists():
        print(f"Error: Glyphs file not found: {GLYPHS_PATH}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize preview tool files (CSV and config) if they don't exist
    _initialize_preview_csv_from_glyphs()
    _initialize_preview_config_from_glyphs()
    
    # Ensure SPAC font exists (generate if needed)
    print(f"Checking for SPAC font...", file=sys.stderr)
    spac_font_path = _ensure_spac_font_exists()
    if spac_font_path:
        print(f"SPAC font available: {spac_font_path}", file=sys.stderr)
    else:
        print(f"Warning: SPAC font not available, will use regular font", file=sys.stderr)
    
    # Auto-build font on server startup
    print(f"Auto-building font on startup...", file=sys.stderr)
    try:
        trigger_build()
        if VARIABLE_FONT_PATH and VARIABLE_FONT_PATH.exists():
            print(f"✓ Font built successfully on startup: {VARIABLE_FONT_PATH}", file=sys.stderr)
        else:
            print(f"⚠ Font build completed but file not found", file=sys.stderr)
    except Exception as e:
        print(f"⚠ Auto-build on startup failed: {e}", file=sys.stderr)
        print(f"  Font can be built manually via /api/build endpoint", file=sys.stderr)
    
    print(f"Starting server on {args.host}:{args.port}", file=sys.stderr)
    print(f"Glyphs file: {GLYPHS_PATH}", file=sys.stderr)
    print(f"Build directory: {BUILD_DIR}", file=sys.stderr)
    print(f"Compiler: {'fontc (with fontmake fallback)' if USE_FONTC else 'fontmake only'}", file=sys.stderr)
    if CSV_PATH:
        print(f"CSV file: {CSV_PATH}", file=sys.stderr)
    else:
        csv_path = _get_avar2_csv_path()
        if csv_path:
            print(f"CSV file (auto-detected): {csv_path}", file=sys.stderr)
        else:
            print(f"CSV file: not found (avar2 endpoints will be unavailable)", file=sys.stderr)
    
    preview_csv = _get_preview_csv_path()
    if preview_csv:
        print(f"Preview CSV: {preview_csv}", file=sys.stderr)
    preview_config = _get_preview_config_path()
    if preview_config:
        print(f"Preview config: {preview_config}", file=sys.stderr)
    
    # Set up real-time file watching using watchdog
    def sync_csv_with_glyphs():
        """Sync CSV with Glyphs file, skipping instances being edited."""
        global EDITING_INSTANCES
        
        csv_path = _get_avar2_csv_path()
        if not csv_path or not csv_path.exists():
            return
        
        try:
            # Use subprocess to call sync script (cleaner than importing)
            import subprocess
            import json as json_module
            
            # Pass editing instances via environment variable
            env = os.environ.copy()
            if EDITING_INSTANCES:
                env['SKIP_INSTANCES'] = json_module.dumps(list(EDITING_INSTANCES))
            
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent / "sync-glyphs-to-avar2.py"),
                    "--glyphs", str(GLYPHS_PATH),
                    "--csv", str(csv_path),
                    "--once"
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            
            if result.returncode == 0:
                skipped_msg = f" (skipped {len(EDITING_INSTANCES)} editing instances)" if EDITING_INSTANCES else ""
                print(f"CSV synced with Glyphs file{skipped_msg}", file=sys.stderr)
            else:
                print(f"Warning: CSV sync had issues: {result.stderr[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not sync CSV: {e}", file=sys.stderr)
    
    class GlyphsFileHandler(FileSystemEventHandler):
        """Watchdog handler for real-time Glyphs file changes."""
        
        def __init__(self):
            self.last_modified = 0
            self.debounce_interval = 0.5  # seconds
        
        def on_modified(self, event):
            """Handle file modification events."""
            if event.is_directory:
                return
            
            # Only process our Glyphs file
            if Path(event.src_path).resolve() != GLYPHS_PATH.resolve():
                return
            
            # Debounce rapid saves
            current_time = time.time()
            if current_time - self.last_modified < self.debounce_interval:
                return
            self.last_modified = current_time
            
            global BUILDING, VARIABLE_FONT_PATH, LAST_BUILD_TIME
            
            if BUILDING:
                return
            
            try:
                print(f"\nGlyphs file modified, syncing CSV and rebuilding...", file=sys.stderr)
                
                # Sync CSV first (skips editing instances)
                sync_csv_with_glyphs()
                
                # Rebuild font
                trigger_build()
            except Exception as e:
                print(f"Error handling file change: {e}", file=sys.stderr)
    
    # Set up file watcher if watchdog is available
    if WATCHDOG_AVAILABLE:
        event_handler = GlyphsFileHandler()
        observer = Observer()
        observer.schedule(event_handler, path=str(GLYPHS_PATH.parent), recursive=False)
        observer.start()
        OBSERVER = observer
        print(f"Real-time file watching enabled: watching {GLYPHS_PATH}", file=sys.stderr)
    else:
        print(f"Warning: watchdog not available, falling back to periodic checking", file=sys.stderr)
        # Fallback to periodic checking
        PERIODIC_CHECK_INTERVAL = 15
        def check_and_rebuild_periodically():
            global VARIABLE_FONT_PATH, LAST_BUILD_TIME
            if BUILDING:
                return
            try:
                if not GLYPHS_PATH.exists():
                    return
                current_mtime = GLYPHS_PATH.stat().st_mtime
                if LAST_BUILD_TIME is None or current_mtime > LAST_BUILD_TIME:
                    sync_csv_with_glyphs()
                    trigger_build()
            except Exception as e:
                print(f"Error in periodic check: {e}", file=sys.stderr)
        
        def start_periodic_checker():
            def periodic_loop():
                while True:
                    time.sleep(PERIODIC_CHECK_INTERVAL)
                    check_and_rebuild_periodically()
            checker_thread = threading.Thread(target=periodic_loop, daemon=True)
            checker_thread.start()
            print(f"Periodic file checking enabled: checking every {PERIODIC_CHECK_INTERVAL} seconds", file=sys.stderr)
        
        start_periodic_checker()
    
    try:
        app.run(host=args.host, port=args.port, debug=True)
    finally:
        if OBSERVER:
            OBSERVER.stop()
            OBSERVER.join()


if __name__ == "__main__":
    main()

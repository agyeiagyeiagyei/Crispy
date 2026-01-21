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


def build_variable_font(glyphs_path: Path, output_dir: Path) -> Path:
    """
    Build variable font from Glyphs file using fontmake.
    
    Returns path to the built variable font TTF.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build using fontmake directly
    cmd = [
        "fontmake",
        "-o", "variable",
        "-g", str(glyphs_path),
        "--output-dir", str(output_dir)
    ]
    
    print(f"Building variable font: {' '.join(cmd)}", file=sys.stderr)
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
    global VARIABLE_FONT_PATH, LAST_BUILD_TIME, BUILDING
    
    if BUILDING:
        print("Build already in progress, skipping...", file=sys.stderr)
        return False
    
    BUILDING = True
    try:
        print(f"Building font from {GLYPHS_PATH}...", file=sys.stderr)
        VARIABLE_FONT_PATH = build_variable_font(GLYPHS_PATH, BUILD_DIR)
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
    """Serve the variable font file."""
    if not VARIABLE_FONT_PATH or not VARIABLE_FONT_PATH.exists():
        return jsonify({"error": "Variable font not built yet."}), 404
    
    response = send_file(
        str(VARIABLE_FONT_PATH),
        mimetype='font/ttf',
        as_attachment=False
    )
    # Add cache control headers to prevent browser caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # Add ETag based on file modification time for cache validation
    mtime = VARIABLE_FONT_PATH.stat().st_mtime
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
    
    # Optional: insert after a specific instance
    insert_after = data.get('insert_after', None)
    if insert_after:
        insert_after = insert_after.strip()
    
    try:
        success = create_instance_in_glyphs(GLYPHS_PATH, instance_name, coordinates, insert_after_instance_name=insert_after)
        
        if success:
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
    """Update instance coordinates in the Glyphs file."""
    data = request.get_json()
    if not data or 'coordinates' not in data:
        return jsonify({"error": "Missing 'coordinates' in request body"}), 400
    
    coordinates = data['coordinates']
    
    # Validate coordinates are numeric
    try:
        coordinates = {k: float(v) for k, v in coordinates.items()}
    except (ValueError, TypeError):
        return jsonify({"error": "Coordinates must be numeric"}), 400
    
    success = update_instance_in_glyphs(GLYPHS_PATH, instance_name, coordinates)
    
    if success:
        # Trigger immediate rebuild after updating instance
        # This ensures font is rebuilt right away, not waiting for periodic check
        print(f"Instance updated, triggering immediate rebuild...", file=sys.stderr)
        trigger_build()
        
        return jsonify({"success": True, "message": f"Updated instance '{instance_name}' in Glyphs file"})
    else:
        return jsonify({"error": f"Failed to update instance '{instance_name}'"}), 500


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


def main():
    global GLYPHS_PATH, BUILD_DIR
    
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
    
    args = parser.parse_args()
    
    GLYPHS_PATH = args.glyphs.resolve()
    BUILD_DIR = args.build_dir.resolve()
    
    if not GLYPHS_PATH.exists():
        print(f"Error: Glyphs file not found: {GLYPHS_PATH}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Starting server on {args.host}:{args.port}", file=sys.stderr)
    print(f"Glyphs file: {GLYPHS_PATH}", file=sys.stderr)
    print(f"Build directory: {BUILD_DIR}", file=sys.stderr)
    
    # Set up periodic file checking (every 15 seconds) instead of file watching
    # This checks file modification time and only rebuilds if file changed
    PERIODIC_CHECK_INTERVAL = 15  # seconds
    
    def check_and_rebuild_periodically():
        """Check if Glyphs file was modified and rebuild if needed."""
        global VARIABLE_FONT_PATH, LAST_BUILD_TIME
        
        if BUILDING:
            return
        
        try:
            if not GLYPHS_PATH.exists():
                return
            
            current_mtime = GLYPHS_PATH.stat().st_mtime
            
            # Only rebuild if file was modified since last build
            if LAST_BUILD_TIME is None or current_mtime > LAST_BUILD_TIME:
                print(f"\nGlyphs file modified, rebuilding font...", file=sys.stderr)
                trigger_build()
        except Exception as e:
            print(f"Error in periodic check: {e}", file=sys.stderr)
    
    def start_periodic_checker():
        """Start background thread to periodically check for file changes."""
        def periodic_loop():
            while True:
                time.sleep(PERIODIC_CHECK_INTERVAL)
                check_and_rebuild_periodically()
        
        checker_thread = threading.Thread(target=periodic_loop, daemon=True)
        checker_thread.start()
        print(f"Periodic file checking enabled: checking every {PERIODIC_CHECK_INTERVAL} seconds", file=sys.stderr)
    
    # Start periodic checker
    start_periodic_checker()
    
    try:
        app.run(host=args.host, port=args.port, debug=True)
    finally:
        if OBSERVER:
            OBSERVER.stop()
            OBSERVER.join()


if __name__ == "__main__":
    main()

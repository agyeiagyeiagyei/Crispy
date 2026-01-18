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
    
    return send_file(
        str(VARIABLE_FONT_PATH),
        mimetype='font/ttf',
        as_attachment=False
    )


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
        return jsonify({"success": True, "message": f"Updated instance '{instance_name}' in Glyphs file"})
    else:
        return jsonify({"error": f"Failed to update instance '{instance_name}'"}), 500


def get_font_family_name(glyphs_path: Path) -> Optional[str]:
    """Get font family name from Glyphs file."""
    try:
        font = load(str(glyphs_path))
        return font.familyName
    except Exception:
        return None


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
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
        default=Path("preview-fonts"),
        help="Directory for built fonts (default: preview-fonts)"
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
    
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()

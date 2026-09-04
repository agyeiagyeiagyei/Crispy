#!/usr/bin/env python3
"""
add-spac-axis-ufo.py

UFO-based SPAC axis addition tool for Glyphs files.

This script adds a SPAC (Spacing) axis to a variable font by:
1. Using fontmake to generate UFO files + designspace from Glyphs file
2. Duplicating all master UFOs to create SPAC=100 (more spacing) and
   SPAC=-100 (reduced spacing) versions
3. Modifying sidebearings in the duplicated UFOs using logarithmic scaling
4. Scaling spacing based on master XTRA value (wider fonts get more spacing)
5. Updating designspace to add SPAC axis (-100 to 100, default 0) and new sources
6. Optionally compiling with fontc

The spacing formula uses logarithmic scaling to provide balanced spacing
across different glyph widths, with additional scaling for wider XTRA masters
(up to 2.0x at max XTRA by default, in both the add and reduce directions).
Reduced sidebearings are clamped at 0 (never negative).
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    from ufoLib2 import Font
    from fontTools.designspaceLib import DesignSpaceDocument
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.pointPen import SegmentToPointPen
except ImportError:
    print("Error: Required libraries not installed.", file=sys.stderr)
    print("  Install with: pip install ufoLib2 fontTools", file=sys.stderr)
    sys.exit(1)


def clamp_sidebearing(value: float) -> float:
    """Clamp negative sidebearings to 0."""
    return max(0.0, value)


def decompose_glyph_components(glyph, font):
    """
    Decompose all components in a glyph into actual contours.
    
    Args:
        glyph: The glyph object to decompose
        font: The font object (used as glyphSet for component lookup)
    
    Returns:
        True if components were decomposed, False if glyph had no components
    """
    if not glyph.components:
        # No components to decompose
        return False
    
    # Use DecomposingRecordingPen to decompose components into contours
    # This pen will automatically resolve component references
    decomposing_pen = DecomposingRecordingPen(font)
    
    # Draw the glyph through the decomposing pen (decomposes components)
    glyph.draw(decomposing_pen)
    
    # Clear existing components and contours
    glyph.clearContours()
    glyph.clearComponents()
    
    # Reconstruct glyph from decomposed contours
    # Use SegmentToPointPen to convert segment-based pen operations to point-based
    point_pen = glyph.getPointPen()
    segment_to_point_pen = SegmentToPointPen(point_pen)
    decomposing_pen.replay(segment_to_point_pen)
    
    return True


def modify_glyph_spacing(glyph, font, spac_value: float = 100.0, multiplier: float = 30.0, xtra_value: Optional[float] = None, xtra_scale_factor: float = 1.0):
    """
    Modify LSB and RSB for a glyph based on SPAC value using logarithmic scaling.
    
    Uses logarithmic scaling to provide balanced spacing across different glyph widths:
    - Wide glyphs (like 'M', 'w') get proportionally less space
    - Narrow glyphs (like 'I', 'i') get proportionally more space
    - Medium glyphs (like 'A', 'O', 'H') get moderate space
    
    Additionally scales spacing based on master XTRA value:
    - Higher XTRA values (wider fonts) get proportionally more spacing
    - Lower XTRA values (narrower fonts) get baseline spacing
    
    Formula: amount_to_add_total = log(glyph_width + 1) * multiplier * xtra_scale * (spac_value / 100.0)
    where xtra_scale = 1 + ((XTRA - XTRA_min) / XTRA_range) * xtra_scale_factor
    
    At SPAC=100: adds calculated amount based on logarithmic scaling
    At SPAC=0: no changes (original spacing)
    At SPAC=-100: subtracts the calculated amount (reduced spacing);
                  sidebearings are clamped at 0, never negative
    
    Uses ufoLib2's setLeftMargin/setRightMargin methods.
    The glyph outline (bounds width) remains unchanged.
    
    Args:
        glyph: The glyph object to modify
        font: The font (layer) object, required for component glyphs
        spac_value: SPAC axis value (default: 100.0); negative values reduce spacing
        multiplier: Logarithmic scaling multiplier (default: 30.0)
                    Higher values = more space for all glyphs
                    Lower values = less space for all glyphs
        xtra_value: XTRA axis value for this master (optional, for scaling)
        xtra_scale_factor: How much extra spacing for max XTRA (default: 1.0 = 2.0x at max)
    """
    if glyph.width == 0:
        # Zero-width glyphs: no changes
        return False
    
    # Get bounds to calculate glyph width (outline width)
    # Pass font as layer parameter (required for component glyphs)
    bounds = glyph.getBounds(font)
    if not bounds:
        # No bounds, skip
        return False
    
    # Calculate glyph outline width (xMax - xMin)
    glyph_width = bounds.xMax - bounds.xMin  # This stays unchanged!
    
    # Get current sidebearings (pass font as layer parameter)
    current_lsb = glyph.getLeftMargin(font) or 0.0
    current_rsb = glyph.getRightMargin(font) or 0.0
    
    # Calculate amount to add using logarithmic scaling
    # log(glyph_width + 1) compresses large numbers and expands small numbers
    # Adding 1 prevents log(0) and ensures narrow glyphs get some space
    # Multiplier controls overall scale (like a "volume knob")
    log_amount = math.log(glyph_width + 1) * multiplier
    
    # Apply XTRA-based scaling if XTRA value is provided
    xtra_scale = 1.0
    if xtra_value is not None:
        # XTRA range in Crispy font: 94 (min) to 3330 (max)
        xtra_min = 94.0
        xtra_max = 3330.0
        xtra_range = xtra_max - xtra_min
        
        # Linear scaling: higher XTRA = more spacing (and more reduction)
        # scale_factor=1.0 means max XTRA gets 2.0x spacing change
        xtra_scale = 1.0 + ((xtra_value - xtra_min) / xtra_range) * xtra_scale_factor
    
    amount_to_add_total = log_amount * xtra_scale * (spac_value / 100.0)
    amount_per_side = amount_to_add_total / 2.0
    
    # Calculate new sidebearings
    new_lsb = clamp_sidebearing(current_lsb + amount_per_side)
    new_rsb = clamp_sidebearing(current_rsb + amount_per_side)
    
    # Set new sidebearings (pass font as layer parameter)
    glyph.setLeftMargin(new_lsb, font)
    glyph.setRightMargin(new_rsb, font)
    
    # Width = LSB + glyph_width + RSB
    glyph.width = new_lsb + glyph_width + new_rsb
    
    return True


def generate_ufos_from_glyphs(glyphs_path: Path, output_dir: Path) -> Path:
    """
    Use fontmake to generate UFO files and designspace from Glyphs file.
    
    Returns path to the generated designspace file.
    """
    print(f"Step 1: Generating UFO files from Glyphs file...", file=sys.stderr)
    print(f"  Input: {glyphs_path}", file=sys.stderr)
    print(f"  Output directory: {output_dir}", file=sys.stderr)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert paths to absolute for fontmake
    glyphs_path_abs = glyphs_path.resolve()
    output_dir_abs = output_dir.resolve()
    
    # Run fontmake to generate UFOs
    cmd = [
        "fontmake",
        "-o", "ufo",
        "-g", str(glyphs_path_abs),
        "--output-dir", str(output_dir_abs)
    ]
    
    print(f"  Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error: fontmake failed", file=sys.stderr)
        print(f"  stdout: {result.stdout}", file=sys.stderr)
        print(f"  stderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    # Find the generated designspace file
    designspace_files = list(output_dir.glob("*.designspace"))
    if not designspace_files:
        print(f"Error: No designspace file found in {output_dir}", file=sys.stderr)
        sys.exit(1)
    
    designspace_path = designspace_files[0]
    print(f"  ✓ Generated designspace: {designspace_path.name}", file=sys.stderr)
    
    # Count UFO files
    ufo_files = list(output_dir.glob("*.ufo"))
    print(f"  ✓ Generated {len(ufo_files)} UFO files", file=sys.stderr)
    
    return designspace_path


def decompose_ufo_components(ufo_path: Path) -> int:
    """
    Decompose all components in a UFO file.
    
    Returns the number of glyphs that had components decomposed.
    """
    font = Font.open(ufo_path)
    glyphs_decomposed = 0
    
    for glyph_name in font.keys():
        glyph = font[glyph_name]
        if decompose_glyph_components(glyph, font):
            glyphs_decomposed += 1
    
    # Save the modified UFO
    font.save(ufo_path, overwrite=True)
    
    return glyphs_decomposed


def copy_and_modify_ufo_master(original_ufo_path: Path, new_ufo_name: str, spac_value: float = 100.0, multiplier: float = 30.0, xtra_value: Optional[float] = None, xtra_scale_factor: float = 1.0) -> Path:
    """
    Copy a UFO master and modify sidebearings for the given SPAC value
    (positive = more spacing, negative = reduced spacing).
    
    Returns path to the new UFO file.
    """
    print(f"\nStep 2: Copying and modifying UFO master...", file=sys.stderr)
    print(f"  Original: {original_ufo_path.name}", file=sys.stderr)
    print(f"  New: {new_ufo_name}", file=sys.stderr)
    
    # Step 1: Decompose components in original UFO first
    # This ensures both sources have the same structure (no components)
    print(f"  Decomposing components in original UFO...", file=sys.stderr)
    original_decomposed = decompose_ufo_components(original_ufo_path)
    if original_decomposed > 0:
        print(f"  ✓ Decomposed components in {original_decomposed} glyphs in original UFO", file=sys.stderr)
    else:
        print(f"  ✓ No components to decompose in original UFO", file=sys.stderr)
    
    # Step 2: Copy the decomposed UFO
    new_ufo_path = original_ufo_path.parent / new_ufo_name
    if new_ufo_path.exists():
        shutil.rmtree(new_ufo_path)
    shutil.copytree(original_ufo_path, new_ufo_path)
    
    print(f"  ✓ Copied UFO to {new_ufo_name}", file=sys.stderr)
    
    # Load the copied UFO (already has decomposed components)
    font = Font.open(new_ufo_path)
    
    # Step 2: Modify sidebearings for all glyphs
    print(f"  Modifying sidebearings for all glyphs...", file=sys.stderr)
    glyphs_modified = 0
    glyphs_skipped = 0
    
    for glyph_name in font.keys():
        glyph = font[glyph_name]
        if modify_glyph_spacing(glyph, font, spac_value, multiplier, xtra_value, xtra_scale_factor):
            glyphs_modified += 1
        else:
            glyphs_skipped += 1
        
        if (glyphs_modified + glyphs_skipped) % 20 == 0:
            print(f"    Processed {glyphs_modified + glyphs_skipped} glyphs...", file=sys.stderr, flush=True)
    
    # Save the modified UFO
    font.save(new_ufo_path, overwrite=True)
    
    print(f"  ✓ Modified {glyphs_modified} glyphs, skipped {glyphs_skipped} zero-width glyphs", file=sys.stderr)
    
    return new_ufo_path


def spac_suffix(spac_value: float) -> str:
    """Name suffix for a SPAC master copy, e.g. 'SPAC100' or 'SPACn100'."""
    if spac_value < 0:
        return f"SPACn{abs(spac_value):g}"
    return f"SPAC{spac_value:g}"


def update_designspace_with_spac(designspace_path: Path, source_mappings: list[tuple[str, str, float]]) -> None:
    """
    Update designspace to add SPAC axis and new sources for each SPAC extreme.
    
    Args:
        designspace_path: Path to designspace file
        source_mappings: List of (original_source_name, new_source_name, spac_value) tuples;
                         spac_value may be positive (added spacing) or negative (reduced spacing)
    """
    print(f"\nStep 3: Updating designspace with SPAC axis...", file=sys.stderr)
    
    # Load designspace
    doc = DesignSpaceDocument.fromfile(designspace_path)
    
    # Create a new designspace with all sources
    from fontTools.designspaceLib import AxisDescriptor, SourceDescriptor
    
    new_doc = DesignSpaceDocument()
    
    # Copy all axes from original designspace
    for axis in doc.axes:
        new_doc.addAxis(axis)
    
    # Derive SPAC axis bounds from the values actually generated
    spac_values = [spac_value for _, _, spac_value in source_mappings]
    spac_min = min(0.0, min(spac_values)) if spac_values else 0.0
    spac_max = max(0.0, max(spac_values)) if spac_values else 0.0
    
    # Add SPAC axis if it doesn't exist
    spac_axis = new_doc.getAxis("SPAC")
    if not spac_axis:
        spac_axis = AxisDescriptor()
        spac_axis.name = "Spacing"
        spac_axis.tag = "SPAC"
        spac_axis.minimum = spac_min
        spac_axis.default = 0.0
        spac_axis.maximum = spac_max
        new_doc.addAxis(spac_axis)
        print(f"  ✓ Added SPAC axis ({spac_min:g} to {spac_max:g}, default 0)", file=sys.stderr)
    else:
        spac_axis.minimum = min(spac_axis.minimum, spac_min)
        spac_axis.maximum = max(spac_axis.maximum, spac_max)
        print(f"  ✓ SPAC axis already exists, bounds now {spac_axis.minimum:g} to {spac_axis.maximum:g}", file=sys.stderr)
    
    # Get SPAC axis name (use name, not tag, for location dict)
    spac_axis_name = spac_axis.name  # "Spacing"
    
    # Create a mapping of original source names to source objects
    source_map = {source.name: source for source in doc.sources}
    
    # Add all original sources with SPAC=0 (once each), plus a new source per SPAC extreme
    originals_added = set()
    for original_source_name, new_source_name, spac_value in source_mappings:
        if original_source_name not in source_map:
            print(f"  ⚠ Warning: Source '{original_source_name}' not found in designspace, skipping", file=sys.stderr)
            continue
        
        original_source = source_map[original_source_name]
        
        # Add original source with SPAC=0
        if original_source_name not in originals_added:
            original_source_copy = SourceDescriptor()
            original_source_copy.filename = original_source.filename
            original_source_copy.name = original_source.name
            original_source_copy.location = original_source.location.copy()
            original_source_copy.location[spac_axis_name] = 0.0  # Use axis name, not tag
            original_source_copy.familyName = original_source.familyName
            original_source_copy.styleName = original_source.styleName
            new_doc.addSource(original_source_copy)
            originals_added.add(original_source_name)
            print(f"  ✓ Added original source '{original_source_name}' at SPAC=0", file=sys.stderr)
        
        # Create new source for this SPAC extreme
        new_ufo_filename = f"{new_source_name}.ufo"
        new_source = SourceDescriptor()
        new_source.filename = new_ufo_filename
        new_source.name = new_source_name
        new_source.location = original_source.location.copy()
        new_source.location[spac_axis_name] = spac_value  # Use axis name, not tag
        new_source.familyName = original_source.familyName
        new_source.styleName = f"{original_source.styleName} {spac_suffix(spac_value)}" if original_source.styleName else spac_suffix(spac_value)
        new_doc.addSource(new_source)
        print(f"  ✓ Added new source '{new_source_name}' at SPAC={spac_value:g}", file=sys.stderr)
    
    # Set default master using findDefault() which properly sets the default attribute
    new_doc.findDefault()
    if new_doc.default:
        print(f"  ✓ Set default master: '{new_doc.default}'", file=sys.stderr)
    else:
        # Fallback: use first original source
        if source_mappings:
            new_doc.default = source_mappings[0][0]
            print(f"  ✓ Set default master: '{new_doc.default}'", file=sys.stderr)
    
    # Copy lib if present
    if hasattr(doc, 'lib') and doc.lib:
        new_doc.lib.update(doc.lib)
    
    # Save updated designspace
    new_doc.write(designspace_path)
    print(f"  ✓ Saved updated designspace with {len(new_doc.sources)} sources", file=sys.stderr)


def compile_with_fontc(designspace_path: Path, output_file: Path) -> bool:
    """
    Compile the designspace with fontc.
    
    Returns True if successful, False otherwise.
    """
    print(f"\nStep 4: Compiling with fontc...", file=sys.stderr)
    print(f"  Designspace: {designspace_path.name}", file=sys.stderr)
    print(f"  Output: {output_file.name}", file=sys.stderr)
    
    # Check if fontc is available
    import shutil
    import os
    fontc_cmd = shutil.which("fontc")
    
    # Also check in venv/bin relative to project root
    if not fontc_cmd:
        # Try to find project root (where designspace_path is relative to)
        project_root = Path.cwd()
        venv_fontc = project_root / "venv" / "bin" / "fontc"
        if venv_fontc.exists():
            fontc_cmd = str(venv_fontc)
        else:
            # Try relative to designspace path
            venv_fontc = designspace_path.parent.parent.parent / "venv" / "bin" / "fontc"
            if venv_fontc.exists():
                fontc_cmd = str(venv_fontc)
    
    if not fontc_cmd:
        print(f"  ⚠ fontc not found in PATH or venv, skipping compilation", file=sys.stderr)
        return False
    
    # Convert paths to absolute
    designspace_path_abs = designspace_path.resolve()
    output_file_abs = output_file.resolve()
    
    cmd = [
        fontc_cmd,
        "--output-file", str(output_file_abs),
        str(designspace_path_abs)
    ]
    
    print(f"  Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"  ⚠ fontc compilation failed", file=sys.stderr)
        print(f"    stdout: {result.stdout}", file=sys.stderr)
        print(f"    stderr: {result.stderr}", file=sys.stderr)
        return False
    
    if output_file.exists():
        print(f"  ✓ fontc compilation successful", file=sys.stderr)
        print(f"    Output: {output_file}", file=sys.stderr)
        return True
    else:
        print(f"  ⚠ fontc did not produce output file", file=sys.stderr)
        return False


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Add SPAC axis to variable font using UFO-based approach"
    )
    parser.add_argument(
        "glyphs",
        type=Path,
        help="Path to Glyphs file"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test-output/ufo-spac"),
        help="Output directory for UFO files and designspace (default: test-output/ufo-spac)"
    )
    parser.add_argument(
        "--master-index",
        type=int,
        default=None,
        help="Index of master to duplicate (default: None, process all masters)"
    )
    parser.add_argument(
        "--spac-value",
        type=float,
        default=100.0,
        help="SPAC value for duplicated master (default: 100.0)"
    )
    parser.add_argument(
        "--spac-min-value",
        type=float,
        default=-100.0,
        help="Negative SPAC value for reduction masters (default: -100.0; set to 0 to disable reduction)"
    )
    parser.add_argument(
        "--multiplier",
        type=float,
        default=30.0,
        help="Logarithmic scaling multiplier (default: 30.0). Higher = more space, lower = less space"
    )
    parser.add_argument(
        "--xtra-scale-factor",
        type=float,
        default=1.0,
        help="XTRA scaling factor (default: 1.0). Higher = more spacing impact for wide XTRA masters. 1.0 means max XTRA gets 2.0x spacing change (add and reduce)"
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile final font with fontc (if available)"
    )
    parser.add_argument(
        "--fontc-output",
        type=Path,
        help="Output file for fontc compilation (default: <output-dir>/Crispy-SPAC-VF.ttf)"
    )
    
    args = parser.parse_args(argv)
    
    # Validate inputs
    if not args.glyphs.exists():
        print(f"Error: Glyphs file not found: {args.glyphs}", file=sys.stderr)
        return 1
    
    # Step 1: Generate UFOs from Glyphs
    designspace_path = generate_ufos_from_glyphs(args.glyphs, args.output_dir)
    
    # Load designspace to get source names
    doc = DesignSpaceDocument.fromfile(designspace_path)
    
    if len(doc.sources) == 0:
        print(f"Error: No sources found in designspace", file=sys.stderr)
        return 1
    
    # Filter to only actual masters (exclude brace layers which have coordinates in their names)
    # Brace layers have names like "Master Name {x, y, z}" with coordinates
    actual_masters = []
    for source in doc.sources:
        # Skip sources with coordinates in braces (brace layers)
        if '{' not in source.name and '}' not in source.name:
            actual_masters.append(source)
    
    if len(actual_masters) == 0:
        print(f"Error: No actual masters found (only brace layers?)", file=sys.stderr)
        return 1
    
    print(f"Found {len(actual_masters)} actual masters (excluding {len(doc.sources) - len(actual_masters)} brace layers)", file=sys.stderr)
    
    # Determine which masters to process
    if args.master_index is not None:
        if args.master_index >= len(actual_masters):
            print(f"Error: Master index {args.master_index} out of range (0-{len(actual_masters)-1})", file=sys.stderr)
            return 1
        masters_to_process = [actual_masters[args.master_index]]
        print(f"Processing single master at index {args.master_index}", file=sys.stderr)
    else:
        masters_to_process = actual_masters
        print(f"Processing all {len(actual_masters)} masters", file=sys.stderr)
    
    # Step 2: Process each master at each SPAC extreme
    spac_values = [args.spac_value]
    if args.spac_min_value < 0:
        spac_values.append(args.spac_min_value)
    
    source_mappings = []  # List of (original_name, new_name, spac_value) tuples
    
    for master_idx, original_source in enumerate(masters_to_process):
        original_source_name = original_source.name
        
        # Determine UFO paths
        # UFO filename is typically the source name or filename without .ufo extension
        if original_source.filename:
            original_ufo_name = original_source.filename.replace(".ufo", "")
        else:
            original_ufo_name = original_source_name
        
        original_ufo_path = args.output_dir / f"{original_ufo_name}.ufo"
        
        if not original_ufo_path.exists():
            # Try alternative naming - match by source name pattern
            ufo_files = sorted(args.output_dir.glob("*.ufo"))
            # Filter out already-processed SPAC UFO copies
            ufo_files = [f for f in ufo_files if "-SPAC" not in f.name]
            # Try to find matching UFO by name pattern
            found = False
            for ufo_file in ufo_files:
                # Check if UFO name matches source name (allowing for variations)
                ufo_base = ufo_file.stem
                if original_ufo_name.replace(" ", "-") in ufo_base or ufo_base.replace("-", " ") in original_ufo_name:
                    original_ufo_path = ufo_file
                    found = True
                    print(f"  ⚠ Using alternative UFO path: {original_ufo_path.name}", file=sys.stderr)
                    break
            if not found:
                # Fallback: use index-based matching
                if ufo_files and master_idx < len(ufo_files):
                    original_ufo_path = ufo_files[master_idx]
                    print(f"  ⚠ Using index-based UFO path: {original_ufo_path.name}", file=sys.stderr)
                else:
                    print(f"Error: Could not find UFO file for source '{original_source_name}'", file=sys.stderr)
                    return 1
        
        # Extract XTRA value from source location
        xtra_value = None
        if original_source.location:
            # Try different possible axis names
            for axis_name in ['X-Transparency', 'XTRA', 'xtra']:
                if axis_name in original_source.location:
                    xtra_value = float(original_source.location[axis_name])
                    break
        
        # Copy and modify UFO at each SPAC extreme
        print(f"\nProcessing master {master_idx + 1}/{len(masters_to_process)}: {original_source_name}", file=sys.stderr)
        if xtra_value is not None:
            print(f"  XTRA value: {xtra_value}", file=sys.stderr)
        
        for spac_value in spac_values:
            new_source_name = f"{original_ufo_name}-{spac_suffix(spac_value)}"
            new_ufo_path = copy_and_modify_ufo_master(
                original_ufo_path,
                f"{new_source_name}.ufo",
                spac_value,
                args.multiplier,
                xtra_value,
                args.xtra_scale_factor
            )
            source_mappings.append((original_source_name, new_source_name, spac_value))
    
    # Step 3: Update designspace with all sources
    update_designspace_with_spac(
        designspace_path,
        source_mappings
    )
    
    # Step 4: Optionally compile with fontc
    if args.compile:
        if args.fontc_output:
            output_file = args.fontc_output
        else:
            output_file = args.output_dir / "Crispy-SPAC-VF.ttf"
        
        compile_with_fontc(designspace_path, output_file)
    
    print(f"\n✓ Complete!", file=sys.stderr)
    print(f"  Designspace: {designspace_path}", file=sys.stderr)
    print(f"  Processed {len(masters_to_process)} master(s) at {len(spac_values)} SPAC extreme(s)", file=sys.stderr)
    for orig_name, new_name, spac_value in source_mappings:
        print(f"    {orig_name} → {new_name} (SPAC={spac_value:g})", file=sys.stderr)
    
    if args.compile:
        print(f"  Compiled font: {output_file}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

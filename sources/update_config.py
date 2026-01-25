#!/usr/bin/env python3
"""
update_config.py

Generate and inject STAT and avar2 sections into config.yaml from CSV mappings.

This script:
1. Validates CSV structure
2. Generates STAT table section
3. Generates avar2 mappings section
4. Validates generated sections
5. Reads existing config.yaml
6. Validates existing config structure
7. Replaces/updates stat and avar2 sections
8. Validates merged config
9. Writes updated config.yaml (with optional backup)
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

import yaml  # PyYAML
try:
    import ruamel.yaml
    HAS_RUAMEL = True
except ImportError:
    HAS_RUAMEL = False
    print("Warning: ruamel.yaml not available, will use basic YAML formatting", file=sys.stderr)


# ============================================================================
# Shared utilities (from gen_avar2.py and gen_stat.py)
# ============================================================================

@dataclass(frozen=True)
class RowMapping:
    instance_name: str
    in_axes: Dict[str, Decimal]
    out_axes: Dict[str, Decimal]
    out_axis_order: Tuple[str, ...]


def _is_blank(v: Optional[str]) -> bool:
    return v is None or str(v).strip() == ""


def _parse_decimal(raw: str, *, context: str) -> Decimal:
    s = str(raw).strip()
    if s == "":
        raise ValueError(f"Blank numeric value for {context}")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Non-numeric value '{raw}' for {context}")


def _normalize_in_axis_name(col: str) -> str:
    # "WGHT-e" -> "wght" (legacy support)
    # "WGHT" -> "wght" (new format)
    # "CONTRAST-e" -> "cntr"
    # "CONTRAST" -> "cntr"
    name = col.strip()
    # Remove "-e" suffix if present (for backward compatibility)
    if name.endswith("-e"):
        name = name[:-2]
    name = name.lower()
    if name == "contrast":
        return "cntr"
    return name


def _load_font_key_from_config(config_path: Path) -> str:
    """Load and validate font key from config.yaml."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config.yaml did not parse to a mapping/dict")

    fvar = data.get("fvarInstances")
    if not isinstance(fvar, dict) or not fvar:
        raise ValueError("config.yaml is missing 'fvarInstances' or it is empty")

    keys = list(fvar.keys())
    if len(keys) != 1:
        raise ValueError(
            f"Found {len(keys)} fvarInstances keys in config.yaml; "
            f"use --font-key to choose one. Keys: {keys}"
        )
    return keys[0]


# ============================================================================
# CSV Validation and Reading
# ============================================================================

def validate_csv_structure(csv_path: Path) -> Tuple[str, List[str], List[str]]:
    """Validate CSV has required columns. Returns (name_col, in_cols, out_cols)."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        fieldnames = [h.strip() for h in reader.fieldnames]
        name_col = "Instance Name"
        
        if name_col not in fieldnames:
            raise ValueError(f"CSV must include a '{name_col}' column. Found: {fieldnames}")

        # Detect in: columns (traditional axes, with or without "-e" suffix)
        # Support both "WGHT" and "WGHT-e" formats
        in_cols = []
        traditional_axes = {"WGHT", "WDTH", "OPSZ", "CONTRAST"}
        for c in fieldnames:
            # Check if column is a traditional axis (with or without -e suffix)
            col_upper = c.upper()
            if col_upper in traditional_axes or col_upper.endswith("-E"):
                in_cols.append(c)
        
        if not in_cols:
            raise ValueError("CSV contains no traditional axis columns (WGHT/WDTH/OPSZ or WGHT-e/WDTH-e/OPSZ-e); cannot build 'in:' locations")

        out_cols = [c for c in fieldnames if c not in (name_col,) and c not in in_cols]
        if not out_cols:
            raise ValueError("CSV contains no parametric axis columns for 'out:'")

        # Validate required axes (case-insensitive, with or without -e suffix)
        required_in = {"wght", "wdth", "opsz"}
        found_in = {_normalize_in_axis_name(c) for c in in_cols}
        missing = {c.upper() for c in (required_in - found_in)}
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        return name_col, in_cols, out_cols


def read_csv_mappings(csv_path: Path) -> List[RowMapping]:
    """Read and validate CSV mappings."""
    name_col, in_cols, out_cols = validate_csv_structure(csv_path)
    out_order = tuple(out_cols)

    mappings: List[RowMapping] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [h.strip() for h in reader.fieldnames]

        for line_no, row in enumerate(reader, start=2):
            row = {k.strip(): (v if v is not None else "") for k, v in row.items()}

            # Skip fully empty rows
            if all(_is_blank(row.get(c, "")) for c in fieldnames):
                continue

            inst_name = str(row.get(name_col, "")).strip()
            if _is_blank(inst_name):
                raise ValueError(f"Line {line_no}: '{name_col}' is blank")

            # Build in_axes
            in_axes: Dict[str, Decimal] = {}
            for c in in_cols:
                raw = row.get(c, "")
                if _is_blank(raw):
                    continue
                in_axes[_normalize_in_axis_name(c)] = _parse_decimal(raw, context=f"line {line_no} / {c}")

            # Build out_axes (STRICT: no blanks)
            out_axes: Dict[str, Decimal] = {}
            for c in out_cols:
                raw = row.get(c, "")
                if _is_blank(raw):
                    raise ValueError(f"Line {line_no}: parametric axis '{c}' is blank (not allowed)")
                out_axes[c] = _parse_decimal(raw, context=f"line {line_no} / {c}")

            # Required axes must exist
            for required in ("wght", "wdth", "opsz"):
                if required not in in_axes:
                    raise ValueError(
                        f"Line {line_no}: missing required traditional axis '{required}' "
                        f"(need {required.upper()}-e value)"
                    )
            
            # Contrast is optional - only include if present in CSV
            # Don't add cntr to in_axes if not in CSV

            mappings.append(
                RowMapping(
                    instance_name=inst_name,
                    in_axes=in_axes,
                    out_axes=out_axes,
                    out_axis_order=out_order,
                )
            )

    if not mappings:
        raise ValueError("CSV contains no valid mappings")

    return mappings


# ============================================================================
# STAT Table Generation
# ============================================================================

def extract_axis_values_from_csv(csv_path: Path) -> Dict[str, List[int]]:
    """Extract unique axis values from CSV."""
    wght_vals = set()
    wdth_vals = set()
    opsz_vals = set()
    cntr_vals = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Support both "WGHT" and "WGHT-e" (legacy)
            wght_col = "WGHT" if "WGHT" in row else "WGHT-e"
            wdth_col = "WDTH" if "WDTH" in row else "WDTH-e"
            opsz_col = "OPSZ" if "OPSZ" in row else "OPSZ-e"
            wght_vals.add(int(float(row[wght_col])))
            wdth_vals.add(int(float(row[wdth_col])))
            opsz_vals.add(int(float(row[opsz_col])))
            # Contrast is optional
            contrast_col = "CONTRAST" if "CONTRAST" in row else "CONTRAST-e"
            if contrast_col in row and row[contrast_col].strip():
                cntr_vals.add(int(float(row[contrast_col])))

    result = {
        "wght": sorted(wght_vals),
        "wdth": sorted(wdth_vals),
        "opsz": sorted(opsz_vals),
    }
    
    if cntr_vals:
        result["cntr"] = sorted(cntr_vals)
    
    return result


def extract_spac_range_from_csv(csv_path: Path) -> Optional[Tuple[float, float]]:
    """Extract SPAC axis min/max values from CSV.
    
    Returns (min, max) tuple if SPAC column exists and has values, None otherwise.
    """
    spac_values = []
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "SPAC" not in reader.fieldnames:
            return None
        
        for row in reader:
            spac_str = row.get("SPAC", "").strip()
            if spac_str:
                try:
                    spac_values.append(float(spac_str))
                except (ValueError, TypeError):
                    continue
    
    if not spac_values:
        return None
    
    return (min(spac_values), max(spac_values))


def get_weight_name(value: int) -> str:
    """Map weight value to STAT name."""
    names = {
        100: "Thin",
        200: "ExtraLight",
        300: "Light",
        400: "Regular",
        500: "Medium",
        600: "SemiBold",
        700: "Bold",
        800: "ExtraBold",
        900: "Black",
    }
    return names.get(value, str(value))


def get_width_name(value: int) -> str:
    """Map width value to STAT name."""
    names = {
        40: "Condensed",
        100: "Normal",
        160: "Extended",
        220: "Ultra Extended",
    }
    return names.get(value, str(value))


def generate_stat_section(axis_values: Dict[str, List[int]], font_key: str) -> Dict:
    """Generate STAT table as dict structure."""
    stat_data = {
        font_key: []
    }
    
    # Add Optical Size axis only if there's variation (more than one value)
    if "opsz" in axis_values and len(axis_values["opsz"]) > 1:
        stat_data[font_key].append({
            "name": "Optical Size",
            "tag": "opsz",
            "values": [{"name": f"{v}pt", "value": v} for v in axis_values["opsz"]],
        })
    
    # Width axis (always present)
    stat_data[font_key].append({
        "name": "Width",
        "tag": "wdth",
        "values": [{"name": get_width_name(v), "value": v} for v in axis_values["wdth"]],
    })
    
    # Weight axis (always present)
    stat_data[font_key].append({
        "name": "Weight",
        "tag": "wght",
        "values": [],
    })

    # Add weight values with style linking
    # Find weight axis (it's the last axis in the list)
    weight_axis_idx = len(stat_data[font_key]) - 1
    for wght_val in axis_values["wght"]:
        weight_entry = {"name": get_weight_name(wght_val), "value": wght_val}
        if wght_val == 400:  # Regular links to Bold
            weight_entry["linkedValue"] = 700
            weight_entry["flags"] = 2
        stat_data[font_key][weight_axis_idx]["values"].append(weight_entry)

    # Add Contrast axis if present
    if "cntr" in axis_values:
        contrast_axis = {
            "name": "Contrast",
            "tag": "cntr",
            "values": [],
        }
        for cntr_val in axis_values["cntr"]:
            if cntr_val == -10:
                contrast_axis["values"].append({"name": "Low Contrast", "value": cntr_val})
            elif cntr_val == 0:
                contrast_axis["values"].append({"name": "Normal", "value": cntr_val})
            elif cntr_val == 10:
                contrast_axis["values"].append({"name": "High Contrast", "value": cntr_val})
            else:
                contrast_axis["values"].append({"name": str(cntr_val), "value": cntr_val})
        stat_data[font_key].append(contrast_axis)

    return stat_data


def validate_stat_section(stat_data: Dict, font_key: str) -> None:
    """Validate STAT section structure."""
    if font_key not in stat_data:
        raise ValueError(f"STAT section missing font key: {font_key}")

    axes = stat_data[font_key]
    if not isinstance(axes, list):
        raise ValueError("STAT axes must be a list")

    # opsz is optional (only included if there's variation)
    required_tags = {"wdth", "wght"}
    found_tags = {ax.get("tag") for ax in axes if isinstance(ax, dict)}
    missing = required_tags - found_tags
    if missing:
        raise ValueError(f"STAT section missing required axis tags: {missing}")

    for axis in axes:
        if not isinstance(axis, dict):
            raise ValueError(f"STAT axis must be a dict: {axis}")
        if "tag" not in axis or "name" not in axis or "values" not in axis:
            raise ValueError(f"STAT axis missing required fields: {axis}")
        if not isinstance(axis["values"], list):
            raise ValueError(f"STAT axis values must be a list: {axis['tag']}")


# ============================================================================
# avar2 Generation
# ============================================================================

def _dedupe_check(mappings: List[RowMapping]) -> None:
    """Check for duplicate in: coordinate tuples."""
    seen: Dict[Tuple[Tuple[str, str], ...], str] = {}
    for m in mappings:
        key = tuple((k, str(v)) for k, v in sorted(m.in_axes.items()))
        if key in seen:
            raise ValueError(
                "Duplicate 'in:' coordinates detected:\n"
                f"  First: {seen[key]}\n"
                f"  Second: {m.instance_name}\n"
                f"  Coords: {dict(key)}"
            )
        seen[key] = m.instance_name


def _sort_key(m: RowMapping) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """Sort key: primary wdth, secondary wght, tertiary -opsz, quaternary contrast (if present)."""
    wdth = m.in_axes["wdth"]
    wght = m.in_axes["wght"]
    opsz = m.in_axes["opsz"]
    contrast = m.in_axes.get("cntr", Decimal(0))  # Default to 0 for sorting if not present
    return (wdth, wght, -opsz, contrast)


def _fmt_decimal(d: Decimal) -> str:
    """Format decimal for YAML output."""
    if d == d.to_integral_value():
        return str(int(d))
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def generate_avar2_yaml_string(
    mappings: List[RowMapping],
    font_key: str,
    include_group_headers: bool = True,
    skip_opsz_if_no_variation: bool = True,
) -> str:
    """Generate avar2 section as YAML string (preserves comments and formatting).
    
    If skip_opsz_if_no_variation is True, removes opsz from in_axes if all mappings
    have the same opsz value.
    """
    _dedupe_check(mappings)
    
    # Check for opsz variation if requested
    if skip_opsz_if_no_variation:
        opsz_values = {m.in_axes.get("opsz") for m in mappings if "opsz" in m.in_axes}
        if len(opsz_values) <= 1:
            # Remove opsz from all mappings
            for m in mappings:
                if "opsz" in m.in_axes:
                    # Create new dict without opsz
                    new_in_axes = {k: v for k, v in m.in_axes.items() if k != "opsz"}
                    # Replace the in_axes (RowMapping is frozen, so we need to recreate)
                    # Actually, we can't modify frozen dataclass, so we'll filter during output
    
    mappings = sorted(mappings, key=_sort_key)

    lines: List[str] = []
    lines.append("avar2:")
    lines.append(f"  {font_key}:")

    current_wdth: Optional[Decimal] = None
    current_opsz: Optional[Decimal] = None
    
    # Determine if we should skip opsz in output
    opsz_values = {m.in_axes.get("opsz") for m in mappings if "opsz" in m.in_axes}
    skip_opsz = skip_opsz_if_no_variation and len(opsz_values) <= 1

    for m in mappings:
        wdth = m.in_axes["wdth"]
        opsz = m.in_axes.get("opsz")  # May not exist if skipped

        if include_group_headers:
            if current_wdth is None or wdth != current_wdth:
                lines.append("")
                lines.append("  # =========================")
                lines.append(f"  # Width = {_fmt_decimal(wdth)}")
                lines.append("  # =========================")
                current_wdth = wdth
                current_opsz = None

            if opsz is not None and (current_opsz is None or opsz != current_opsz):
                lines.append("")
                lines.append(f"  # OPSZ = {_fmt_decimal(opsz)}")
                current_opsz = opsz

        lines.append("")
        # Instance name already includes contrast suffix from CSV expansion
        # (cntr=0 keeps original, cntr=-10/+10 get "Contrast-Min"/"Contrast-Max" suffix)
        lines.append(f"  # {m.instance_name}")
        lines.append("  - in:")

        # Stable ordering for in: (sorted by axis name)
        # Skip opsz if no variation
        in_axes_to_output = {k: v for k, v in m.in_axes.items() if not (skip_opsz and k == "opsz")}
        for k in sorted(in_axes_to_output.keys()):
            lines.append(f"      {k}: {_fmt_decimal(in_axes_to_output[k])}")

        lines.append("    out:")
        # Preserve out-axis order from CSV header, but exclude SPAC (spacing axis is handled separately)
        for k in m.out_axis_order:
            if k != "SPAC":  # Exclude SPAC from avar2 out mappings
                lines.append(f"      {k}: {_fmt_decimal(m.out_axes[k])}")

    lines.append("")
    return "\n".join(lines)


def validate_avar2_yaml(avar2_yaml: str, font_key: str) -> None:
    """Validate avar2 YAML string."""
    try:
        data = yaml.safe_load(avar2_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"Generated avar2 YAML is invalid: {e}")

    if not isinstance(data, dict) or "avar2" not in data:
        raise ValueError("Generated avar2 YAML missing 'avar2' key")

    if font_key not in data["avar2"]:
        raise ValueError(f"Generated avar2 YAML missing font key: {font_key}")

    entries = data["avar2"][font_key]
    if not isinstance(entries, list):
        raise ValueError("avar2 entries must be a list")

    if len(entries) == 0:
        raise ValueError("avar2 section has no entries")


# ============================================================================
# Config File Merging
# ============================================================================

def load_config(config_path: Path) -> Dict:
    """Load and validate config.yaml."""
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse config.yaml: {e}")

    if not isinstance(data, dict):
        raise ValueError("config.yaml did not parse to a mapping/dict")

    # Validate required keys
    required_keys = {"sources", "familyName", "fvarInstances"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"config.yaml missing required keys: {missing}")

    return data


def merge_config(
    config: Dict,
    stat_data: Dict,
    avar2_yaml: str,
    font_key: str,
    add_contrast: bool = False,
    csv_path: Optional[Path] = None,
) -> Tuple[Dict, str]:
    """Merge stat and avar2 sections into config.
    
    Returns (updated_config_dict, avar2_yaml_string) for writing.
    
    If add_contrast is True, automatically adds cntr: 0 to all fvarInstances.
    Note: spacingAxis section is preserved as-is and never updated automatically.
    """
    # Update/replace stat section
    config["stat"] = stat_data

    # Parse avar2 YAML to validate structure, but we'll use the string for output
    avar2_parsed = yaml.safe_load(avar2_yaml)
    config["avar2"] = avar2_parsed["avar2"]
    
    # Note: spacingAxis section is preserved as-is and never updated automatically
    # The spacingAxis min/max values should be set manually in the config file
    
    # If contrast was added, update fvarInstances to include cntr: 0
    if add_contrast:
        fvar_instances = config.get("fvarInstances", {})
        if font_key in fvar_instances:
            for instance in fvar_instances[font_key]:
                if "coordinates" not in instance:
                    instance["coordinates"] = {}
                coords = instance["coordinates"]
                if "cntr" not in coords:
                    coords["cntr"] = 0

    return config, avar2_yaml


def validate_merged_config(config: Dict, font_key: str) -> None:
    """Validate the merged config structure."""
    # Check stat section
    if "stat" not in config:
        raise ValueError("Merged config missing 'stat' section")
    if font_key not in config["stat"]:
        raise ValueError(f"Merged config stat section missing font key: {font_key}")

    # Check avar2 section
    if "avar2" not in config:
        raise ValueError("Merged config missing 'avar2' section")
    if font_key not in config["avar2"]:
        raise ValueError(f"Merged config avar2 section missing font key: {font_key}")

    # Validate YAML can be serialized
    try:
        yaml.dump(config, default_flow_style=False)
    except Exception as e:
        raise ValueError(f"Config cannot be serialized to YAML: {e}")


def write_config(
    config: Dict,
    avar2_yaml: str,
    config_path: Path,
    backup: bool = True,
) -> None:
    """Write config.yaml, replacing stat and avar2 sections.
    
    Uses a hybrid approach: writes most of config as YAML, but injects
    the pre-formatted avar2 YAML string to preserve comments.
    """
    if backup:
        backup_path = config_path.with_suffix(".yaml.backup")
        if config_path.exists():
            shutil.copy2(config_path, backup_path)
            print(f"Created backup: {backup_path}", file=sys.stderr)

    # Read original file
    original_text = config_path.read_text(encoding="utf-8")
    original_lines = original_text.splitlines()

    # Find section boundaries using regex-like approach
    stat_start_idx = None
    stat_end_idx = None
    avar2_start_idx = None
    avar2_end_idx = None
    fvar_instances_start_idx = None
    fvar_instances_end_idx = None

    in_stat = False
    in_avar2 = False
    in_fvar_instances = False
    stat_indent = None
    avar2_indent = None
    fvar_instances_indent = None

    for i, line in enumerate(original_lines):
        stripped = line.strip()
        
        # Detect stat section
        if stripped == "stat:" or stripped.startswith("stat:"):
            stat_start_idx = i
            in_stat = True
            stat_indent = len(line) - len(line.lstrip())
            continue
        
        # Detect fvarInstances section
        if stripped == "fvarInstances:" or stripped.startswith("fvarInstances:"):
            fvar_instances_start_idx = i
            in_fvar_instances = True
            fvar_instances_indent = len(line) - len(line.lstrip())
            if in_stat:
                stat_end_idx = i
                in_stat = False
            continue
        
        # Detect avar2 section
        if stripped == "avar2:" or stripped.startswith("avar2:"):
            avar2_start_idx = i
            in_avar2 = True
            avar2_indent = len(line) - len(line.lstrip())
            if in_stat:
                stat_end_idx = i
                in_stat = False
            if in_fvar_instances:
                fvar_instances_end_idx = i
                in_fvar_instances = False
            continue
        
        # Detect end of sections (top-level key)
        if in_stat or in_avar2 or in_fvar_instances:
            if not line.strip():  # Blank line, continue
                continue
            current_indent = len(line) - len(line.lstrip())
            # If we hit a line with same or less indent than section start, and it's a key
            if ":" in line and not line.strip().startswith("#"):
                if in_stat and current_indent <= stat_indent and stripped != "stat:":
                    stat_end_idx = i
                    in_stat = False
                if in_fvar_instances and current_indent <= fvar_instances_indent and stripped != "fvarInstances:":
                    fvar_instances_end_idx = i
                    in_fvar_instances = False
                if in_avar2 and current_indent <= avar2_indent and stripped != "avar2:":
                    avar2_end_idx = i
                    in_avar2 = False

    # If still in section at end of file
    if in_stat:
        stat_end_idx = len(original_lines)
    if in_fvar_instances:
        fvar_instances_end_idx = len(original_lines)
    if in_avar2:
        avar2_end_idx = len(original_lines)

    # Build new file
    new_lines = []

    # Determine which sections need to be updated
    # Order: spacingAxis, fvarInstances, stat, avar2 (in file order)
    
    # Find spacingAxis section
    spacing_axis_start_idx = None
    spacing_axis_end_idx = None
    in_spacing_axis = False
    spacing_axis_indent = None
    
    for i, line in enumerate(original_lines):
        stripped = line.strip()
        if stripped == "spacingAxis:" or stripped.startswith("spacingAxis:"):
            spacing_axis_start_idx = i
            in_spacing_axis = True
            spacing_axis_indent = len(line) - len(line.lstrip())
            continue
        if in_spacing_axis:
            if not line.strip():
                continue
            current_indent = len(line) - len(line.lstrip())
            if ":" in line and not line.strip().startswith("#"):
                if current_indent <= spacing_axis_indent and stripped != "spacingAxis:":
                    spacing_axis_end_idx = i
                    in_spacing_axis = False
    if in_spacing_axis:
        spacing_axis_end_idx = len(original_lines)
    
    # Find the first section that needs updating (excluding spacingAxis for now)
    first_update_idx = None
    for idx in [fvar_instances_start_idx, stat_start_idx, avar2_start_idx]:
        if idx is not None and (first_update_idx is None or idx < first_update_idx):
            first_update_idx = idx
    
    # Part before first section to update (but handle spacingAxis separately)
    if spacing_axis_start_idx is not None and "spacingAxis" in config:
        # Write everything before spacingAxis
        new_lines.extend(original_lines[:spacing_axis_start_idx])
        
        # Write updated spacingAxis
        spacing_yaml_lines = yaml.dump(
            {"spacingAxis": config["spacingAxis"]},
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ).strip().splitlines()
        new_lines.extend(spacing_yaml_lines)
        new_lines.append("")
        
        # Skip original spacingAxis section, continue from after it
        if spacing_axis_end_idx is not None:
            # Find next section after spacingAxis
            next_section_start = first_update_idx if first_update_idx is not None else len(original_lines)
            if spacing_axis_end_idx < next_section_start:
                # Add any blank lines between spacingAxis and next section
                between_lines = original_lines[spacing_axis_end_idx:next_section_start]
                for line in between_lines:
                    if line.strip() or (new_lines and new_lines[-1].strip()):
                        new_lines.append(line)
    elif first_update_idx is not None:
        new_lines.extend(original_lines[:first_update_idx])
    else:
        new_lines.extend(original_lines)

    # Insert fvarInstances section if it needs updating
    if fvar_instances_start_idx is not None:
        fvar_yaml_lines = yaml.dump(
            {"fvarInstances": config["fvarInstances"]},
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ).strip().splitlines()
        new_lines.extend(fvar_yaml_lines)
        new_lines.append("")
        
        # Add lines between fvarInstances and next section (if any)
        if fvar_instances_end_idx is not None:
            # Determine next section
            next_section_start = None
            if stat_start_idx is not None and stat_start_idx > fvar_instances_end_idx:
                next_section_start = stat_start_idx
            elif avar2_start_idx is not None and avar2_start_idx > fvar_instances_end_idx:
                next_section_start = avar2_start_idx
            
            if next_section_start is not None:
                between_lines = original_lines[fvar_instances_end_idx:next_section_start]
                # Filter out excessive blank lines
                for line in between_lines:
                    if line.strip() or (new_lines and new_lines[-1].strip()):
                        new_lines.append(line)
    
    # Insert stat section
    if stat_start_idx is not None:
        stat_yaml_lines = yaml.dump(
            {"stat": config["stat"]},
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ).strip().splitlines()
        new_lines.extend(stat_yaml_lines)
        new_lines.append("")

    # Part between stat and avar2
    if stat_start_idx is not None and avar2_start_idx is not None:
        if stat_end_idx is not None and avar2_start_idx > stat_end_idx:
            # Skip blank lines between sections
            between = original_lines[stat_end_idx:avar2_start_idx]
            new_lines.extend([l for l in between if l.strip() or not new_lines or new_lines[-1].strip()])

    # Insert avar2 section (preserve formatting with comments)
    if avar2_start_idx is not None:
        new_lines.extend(avar2_yaml.strip().splitlines())
        if new_lines and new_lines[-1].strip():  # Only add blank line if last line isn't blank
            new_lines.append("")

    # Part after avar2
    if avar2_start_idx is not None and avar2_end_idx is not None:
        after = original_lines[avar2_end_idx:]
        # Skip initial blank lines
        skip_blank = True
        for line in after:
            if skip_blank and not line.strip():
                continue
            skip_blank = False
            new_lines.append(line)
    elif avar2_start_idx is None and stat_start_idx is not None:
        # avar2 was added, but stat existed - nothing after
        pass

    # Write file
    output = "\n".join(new_lines)
    if not output.endswith("\n"):
        output += "\n"
    config_path.write_text(output, encoding="utf-8")


# ============================================================================
# Main
# ============================================================================

# Import contrast expansion from separate module
try:
    from expand_contrast import expand_csv_with_contrast
except ImportError:
    # Fallback if running from different directory
    import importlib.util
    expand_contrast_path = Path(__file__).parent / "expand_contrast.py"
    if expand_contrast_path.exists():
        spec = importlib.util.spec_from_file_location("expand_contrast", expand_contrast_path)
        expand_contrast = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(expand_contrast)
        expand_csv_with_contrast = expand_contrast.expand_csv_with_contrast
    else:
        expand_csv_with_contrast = None


def expand_csv_with_opsz(
    csv_path: Path, 
    opsz_config_path: Optional[Path] = None,
    output_path: Optional[Path] = None
) -> Path:
    """
    Expand CSV with MinOPSZ and MaxOPSZ rows based on opsz.yaml configuration.
    
    For each base row (OPSZ=48), creates 2 additional rows:
    - MinOPSZ (OPSZ=12): Adjusted XOPQ/YOPQ/XTRA with -MinOPSZ suffix
    - MaxOPSZ (OPSZ=72): Adjusted XOPQ/YOPQ/XTRA with -MaxOPSZ suffix
    
    Returns path to expanded CSV.
    """
    if opsz_config_path is None:
        opsz_config_path = csv_path.parent / "opsz.yaml"
    
    if not opsz_config_path.exists():
        raise FileNotFoundError(f"opsz.yaml not found at {opsz_config_path}")
    
    # Load opsz config
    with opsz_config_path.open('r') as f:
        config = yaml.safe_load(f)
    
    base_opsz = config['base_opsz']
    min_opsz = config['min_opsz']
    max_opsz = config['max_opsz']
    weight_points = sorted(config['weight_adjustments'], key=lambda x: x['weight'])
    xtra_condensed = config['xtra_adjustments']['condensed_widths']
    
    def interpolate_multiplier(weight: int, axis: str) -> Tuple[float, float]:
        """Interpolate multiplier for given weight and axis."""
        if weight <= weight_points[0]['weight']:
            return (
                weight_points[0]['min_opsz_multipliers'][axis],
                weight_points[0]['max_opsz_multipliers'][axis]
            )
        if weight >= weight_points[-1]['weight']:
            return (
                weight_points[-1]['min_opsz_multipliers'][axis],
                weight_points[-1]['max_opsz_multipliers'][axis]
            )
        
        for i in range(len(weight_points) - 1):
            w1, w2 = weight_points[i]['weight'], weight_points[i+1]['weight']
            if w1 <= weight <= w2:
                t = (weight - w1) / (w2 - w1)
                min_m1 = weight_points[i]['min_opsz_multipliers'][axis]
                min_m2 = weight_points[i+1]['min_opsz_multipliers'][axis]
                max_m1 = weight_points[i]['max_opsz_multipliers'][axis]
                max_m2 = weight_points[i+1]['max_opsz_multipliers'][axis]
                min_mult = min_m1 + (min_m2 - min_m1) * t
                max_mult = max_m1 + (max_m2 - max_m1) * t
                return min_mult, max_mult
        
        return 1.0, 1.0
    
    # Determine output path
    if output_path is None:
        # Use temporary file if no output path specified
        output_path = Path(tempfile.mktemp(suffix='.csv', prefix='avar2-mappings_with_opsz_'))
    
    rows = []
    with csv_path.open('r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            rows.append(row)
    
    # Generate new rows
    new_rows = []
    
    for row in rows:
        # Check for missing required values first
        wght_str = row.get('WGHT', '').strip()
        wdth_str = row.get('WDTH', '').strip()
        if not wght_str or not wdth_str:
            # Skip rows with missing required values entirely from opsz expansion
            # These rows will remain in the original CSV and won't be expanded
            # (They can't be used for opsz generation without WGHT/WDTH)
            continue
        
        # Only generate opsz rows if this row has the base opsz
        # Handle empty string or missing OPSZ value
        opsz_value = row.get('OPSZ', '') or str(base_opsz)
        if not opsz_value.strip():
            opsz_value = str(base_opsz)
        if int(opsz_value) != base_opsz:
            # Keep non-base-opsz rows as-is
            new_rows.append(row.copy())
            continue
        
        # Keep base row (OPSZ=base_opsz)
        base_row = row.copy()
        # Ensure SPAC is set for base row (0 for base OPSZ)
        if 'SPAC' in base_row:
            base_row['SPAC'] = base_row.get('SPAC', '').strip() or '0'
        new_rows.append(base_row)
        
        wght = int(wght_str)
        wdth = int(wdth_str)
        base_xopq = float(row.get('XOPQ', '0') or '0')
        base_yopq = float(row.get('YOPQ', '0') or '0')
        base_xtra = float(row.get('XTRA', '0') or '0')
        instance_name = row.get('Instance Name', '')
        
        # Get multipliers
        min_xopq_mult, max_xopq_mult = interpolate_multiplier(wght, 'xopq')
        min_yopq_mult, max_yopq_mult = interpolate_multiplier(wght, 'yopq')
        
        # Apply XTRA adjustments for condensed
        min_xtra_mult = xtra_condensed['min_opsz_multiplier'] if wdth < 100 else 1.0
        max_xtra_mult = xtra_condensed['max_opsz_multiplier'] if wdth < 100 else 1.0
        
        # Calculate adjusted values
        min_xopq = base_xopq * min_xopq_mult
        max_xopq = base_xopq * max_xopq_mult
        min_yopq = base_yopq * min_yopq_mult
        max_yopq = base_yopq * max_yopq_mult
        min_xtra = base_xtra * min_xtra_mult
        max_xtra = base_xtra * max_xtra_mult
        
        # Create MinOPSZ row
        min_row = row.copy()
        min_row['Instance Name'] = f"{instance_name}-MinOPSZ"
        min_row['OPSZ'] = str(min_opsz)
        min_row['XOPQ'] = f"{min_xopq:.3f}"
        min_row['YOPQ'] = f"{min_yopq:.3f}"
        min_row['XTRA'] = f"{min_xtra:.3f}"
        # Set SPAC: +20 for MinOPSZ
        if 'SPAC' in min_row:
            min_row['SPAC'] = '20'
        else:
            min_row['SPAC'] = '20'
        new_rows.append(min_row)
        
        # Create MaxOPSZ row
        max_row = row.copy()
        max_row['Instance Name'] = f"{instance_name}-MaxOPSZ"
        max_row['OPSZ'] = str(max_opsz)
        max_row['XOPQ'] = f"{max_xopq:.3f}"
        max_row['YOPQ'] = f"{max_yopq:.3f}"
        max_row['XTRA'] = f"{max_xtra:.3f}"
        # Set SPAC: -20 for MaxOPSZ
        if 'SPAC' in max_row:
            max_row['SPAC'] = '-20'
        else:
            max_row['SPAC'] = '-20'
        new_rows.append(max_row)
    
    # Write output
    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)
    
    return output_path


def check_opsz_variation(csv_path: Path) -> bool:
    """Check if CSV has variation in OPSZ column (more than one unique value)."""
    opsz_values = set()
    with csv_path.open('r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            opsz = row.get('OPSZ', '').strip()
            if opsz:
                opsz_values.add(opsz)
    return len(opsz_values) > 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate and inject STAT and avar2 sections into config.yaml from CSV."
    )
    ap.add_argument("--csv", required=True, type=Path, help="Path to CSV exported from spreadsheet.")
    ap.add_argument("--config", required=True, type=Path, help="Path to config.yaml to update.")
    ap.add_argument("--font-key", default=None, help="Override font key (otherwise auto-detected).")
    ap.add_argument("--no-backup", action="store_true", help="Don't create backup of config.yaml.")
    ap.add_argument("--dry-run", action="store_true", help="Validate only, don't write changes.")
    ap.add_argument("--add-contrast", action="store_true", help="Expand CSV with contrast variations before processing.")
    ap.add_argument("--add-opsz", action="store_true", help="Expand CSV with MinOPSZ and MaxOPSZ rows based on opsz.yaml.")
    ap.add_argument("--save-opsz-csv", action="store_true", help="Save expanded opsz CSV to file (default: use temporary file, auto-deleted).")
    args = ap.parse_args(argv)

    try:
        # Step 1: Validate CSV structure
        print("Step 1: Validating CSV structure...", file=sys.stderr)
        validate_csv_structure(args.csv)
        print("  ✓ CSV structure valid", file=sys.stderr)

        # Step 2: Read CSV mappings (with optional contrast/opsz expansion)
        print("Step 2: Reading CSV mappings...", file=sys.stderr)
        csv_to_use = args.csv
        
        # Check opsz variation before expansion (for avar2 generation later)
        has_opsz_variation_before = check_opsz_variation(csv_to_use)
        
        if args.add_opsz:
            print("  Expanding CSV with opsz variations...", file=sys.stderr)
            # Determine output path based on flag
            if args.save_opsz_csv:
                opsz_output = csv_to_use.parent / f"{csv_to_use.stem}_with_opsz{csv_to_use.suffix}"
            else:
                opsz_output = None  # Will use temporary file
            csv_to_use = expand_csv_with_opsz(csv_to_use, output_path=opsz_output)
            if args.save_opsz_csv:
                print(f"  ✓ Expanded CSV written to: {csv_to_use}", file=sys.stderr)
            else:
                print(f"  ✓ Expanded CSV generated (temporary file)", file=sys.stderr)
        
        if args.add_contrast:
            print("  Expanding CSV with contrast variations...", file=sys.stderr)
            csv_to_use = expand_csv_with_contrast(
                csv_to_use,
                # Asymmetric scaling for balanced perceptual impact
                # Negative side needs stronger scaling to match positive side's visual impact
                negative_factor=Decimal("1.20"),  # Higher factor for negative (less contrast) side
                negative_offset=Decimal("60"),    # Larger offset for negative side
                positive_factor=Decimal("0.85"),  # Moderate factor for positive (more contrast) side
                positive_offset=Decimal("30"),    # Moderate offset for positive side
            )
            print(f"  ✓ Expanded CSV written to: {csv_to_use}", file=sys.stderr)
        
        mappings = read_csv_mappings(csv_to_use)
        print(f"  ✓ Read {len(mappings)} mappings", file=sys.stderr)
        
        # Store path for cleanup if temporary file was used
        temp_opsz_file = None
        if args.add_opsz and not args.save_opsz_csv:
            temp_opsz_file = csv_to_use

        # Step 3: Load and validate existing config
        print("Step 3: Loading existing config.yaml...", file=sys.stderr)
        config = load_config(args.config)
        print("  ✓ Config loaded and validated", file=sys.stderr)

        # Step 4: Determine font key
        if args.font_key:
            font_key = args.font_key
        else:
            font_key = _load_font_key_from_config(args.config)
        print(f"  ✓ Font key: {font_key}", file=sys.stderr)

        # Step 5: Generate STAT section
        print("Step 5: Generating STAT section...", file=sys.stderr)
        # Use expanded CSV if opsz or contrast was added, otherwise use original
        stat_csv = csv_to_use if (args.add_opsz or args.add_contrast) else args.csv
        axis_values = extract_axis_values_from_csv(stat_csv)
        # Remove opsz from STAT if there's no variation (only one value)
        if len(axis_values.get("opsz", [])) <= 1:
            axis_values.pop("opsz", None)
            print("  ℹ OPSZ axis skipped in STAT (no variation)", file=sys.stderr)
        stat_data = generate_stat_section(axis_values, font_key)
        validate_stat_section(stat_data, font_key)
        print(f"  ✓ STAT section generated ({len(stat_data[font_key])} axes)", file=sys.stderr)

        # Step 6: Generate avar2 section
        print("Step 6: Generating avar2 section...", file=sys.stderr)
        # Check if opsz has variation (after expansions)
        has_opsz_variation_after = check_opsz_variation(csv_to_use)
        avar2_yaml = generate_avar2_yaml_string(
            mappings, 
            font_key,
            include_group_headers=True,
            skip_opsz_if_no_variation=not has_opsz_variation_after
        )
        validate_avar2_yaml(avar2_yaml, font_key)
        # Count entries
        avar2_parsed = yaml.safe_load(avar2_yaml)
        entry_count = len(avar2_parsed["avar2"][font_key])
        print(f"  ✓ avar2 section generated ({entry_count} entries)", file=sys.stderr)

        # Step 7: Merge into config
        print("Step 7: Merging sections into config...", file=sys.stderr)
        merged_config, avar2_yaml_final = merge_config(
            config, stat_data, avar2_yaml, font_key, 
            add_contrast=args.add_contrast,
            csv_path=csv_to_use
        )
        if args.add_contrast:
            # Verify fvarInstances were updated
            fvar_inst = merged_config.get("fvarInstances", {}).get(font_key, [])
            all_have_cntr = all("cntr" in inst.get("coordinates", {}) for inst in fvar_inst)
            if all_have_cntr:
                print(f"  ✓ fvarInstances updated with cntr: 0 ({len(fvar_inst)} instances)", file=sys.stderr)
        validate_merged_config(merged_config, font_key)
        print("  ✓ Config merged and validated", file=sys.stderr)

        # Step 8: Write config (or dry-run)
        if args.dry_run:
            print("Step 8: DRY RUN - Config validated, no changes written", file=sys.stderr)
        else:
            print("Step 8: Writing updated config.yaml...", file=sys.stderr)
            write_config(merged_config, avar2_yaml_final, args.config, backup=not args.no_backup)
            print(f"  ✓ Config written: {args.config}", file=sys.stderr)

        print("\n✓ All steps completed successfully!", file=sys.stderr)
        
        # Clean up temporary opsz file if it was created
        if 'temp_opsz_file' in locals() and temp_opsz_file and temp_opsz_file.exists():
            try:
                temp_opsz_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors
        
        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


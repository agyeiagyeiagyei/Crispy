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
    return col[:-2].strip().lower()


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

        in_cols = [c for c in fieldnames if c.endswith("-e")]
        if not in_cols:
            raise ValueError("CSV contains no '*-e' columns; cannot build 'in:' locations")

        out_cols = [c for c in fieldnames if c not in (name_col,) and c not in in_cols]
        if not out_cols:
            raise ValueError("CSV contains no parametric axis columns for 'out:'")

        # Validate required axes (case-insensitive)
        required_in = {"wght-e", "wdth-e", "opsz-e"}
        found_in = {c.lower() for c in in_cols}
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

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wght_vals.add(int(float(row["WGHT-e"])))
            wdth_vals.add(int(float(row["WDTH-e"])))
            opsz_vals.add(int(float(row["OPSZ-e"])))

    return {
        "wght": sorted(wght_vals),
        "wdth": sorted(wdth_vals),
        "opsz": sorted(opsz_vals),
    }


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
        font_key: [
            {
                "name": "Optical Size",
                "tag": "opsz",
                "values": [{"name": f"{v}pt", "value": v} for v in axis_values["opsz"]],
            },
            {
                "name": "Width",
                "tag": "wdth",
                "values": [{"name": get_width_name(v), "value": v} for v in axis_values["wdth"]],
            },
            {
                "name": "Weight",
                "tag": "wght",
                "values": [],
            },
        ]
    }

    # Add weight values with style linking
    for wght_val in axis_values["wght"]:
        weight_entry = {"name": get_weight_name(wght_val), "value": wght_val}
        if wght_val == 400:  # Regular links to Bold
            weight_entry["linkedValue"] = 700
            weight_entry["flags"] = 2
        stat_data[font_key][2]["values"].append(weight_entry)

    return stat_data


def validate_stat_section(stat_data: Dict, font_key: str) -> None:
    """Validate STAT section structure."""
    if font_key not in stat_data:
        raise ValueError(f"STAT section missing font key: {font_key}")

    axes = stat_data[font_key]
    if not isinstance(axes, list):
        raise ValueError("STAT axes must be a list")

    required_tags = {"opsz", "wdth", "wght"}
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


def _sort_key(m: RowMapping) -> Tuple[Decimal, Decimal, Decimal]:
    """Sort key: primary wdth, secondary wght, tertiary -opsz."""
    wdth = m.in_axes["wdth"]
    wght = m.in_axes["wght"]
    opsz = m.in_axes["opsz"]
    return (wdth, wght, -opsz)


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
) -> str:
    """Generate avar2 section as YAML string (preserves comments and formatting)."""
    _dedupe_check(mappings)
    mappings = sorted(mappings, key=_sort_key)

    lines: List[str] = []
    lines.append("avar2:")
    lines.append(f"  {font_key}:")

    current_wdth: Optional[Decimal] = None
    current_opsz: Optional[Decimal] = None

    for m in mappings:
        wdth = m.in_axes["wdth"]
        opsz = m.in_axes["opsz"]

        if include_group_headers:
            if current_wdth is None or wdth != current_wdth:
                lines.append("")
                lines.append("  # =========================")
                lines.append(f"  # Width = {_fmt_decimal(wdth)}")
                lines.append("  # =========================")
                current_wdth = wdth
                current_opsz = None

            if current_opsz is None or opsz != current_opsz:
                lines.append("")
                lines.append(f"  # OPSZ = {_fmt_decimal(opsz)}")
                current_opsz = opsz

        lines.append("")
        lines.append(f"  # {m.instance_name}")
        lines.append("  - in:")

        # Stable ordering for in: (sorted by axis name)
        for k in sorted(m.in_axes.keys()):
            lines.append(f"      {k}: {_fmt_decimal(m.in_axes[k])}")

        lines.append("    out:")
        # Preserve out-axis order from CSV header
        for k in m.out_axis_order:
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
) -> Tuple[Dict, str]:
    """Merge stat and avar2 sections into config.
    
    Returns (updated_config_dict, avar2_yaml_string) for writing.
    """
    # Update/replace stat section
    config["stat"] = stat_data

    # Parse avar2 YAML to validate structure, but we'll use the string for output
    avar2_parsed = yaml.safe_load(avar2_yaml)
    config["avar2"] = avar2_parsed["avar2"]

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

    in_stat = False
    in_avar2 = False
    stat_indent = None
    avar2_indent = None

    for i, line in enumerate(original_lines):
        stripped = line.strip()
        
        # Detect stat section
        if stripped == "stat:" or stripped.startswith("stat:"):
            stat_start_idx = i
            in_stat = True
            stat_indent = len(line) - len(line.lstrip())
            continue
        
        # Detect avar2 section
        if stripped == "avar2:" or stripped.startswith("avar2:"):
            avar2_start_idx = i
            in_avar2 = True
            avar2_indent = len(line) - len(line.lstrip())
            if in_stat:
                stat_end_idx = i
                in_stat = False
            continue
        
        # Detect end of sections (top-level key)
        if in_stat or in_avar2:
            if not line.strip():  # Blank line, continue
                continue
            current_indent = len(line) - len(line.lstrip())
            # If we hit a line with same or less indent than section start, and it's a key
            if ":" in line and not line.strip().startswith("#"):
                if in_stat and current_indent <= stat_indent and stripped != "stat:":
                    stat_end_idx = i
                    in_stat = False
                if in_avar2 and current_indent <= avar2_indent and stripped != "avar2:":
                    avar2_end_idx = i
                    in_avar2 = False

    # If still in section at end of file
    if in_stat:
        stat_end_idx = len(original_lines)
    if in_avar2:
        avar2_end_idx = len(original_lines)

    # Build new file
    new_lines = []

    # Part before stat
    if stat_start_idx is not None:
        new_lines.extend(original_lines[:stat_start_idx])
    else:
        # No stat section, append before avar2 or at end
        if avar2_start_idx is not None:
            new_lines.extend(original_lines[:avar2_start_idx])
        else:
            new_lines.extend(original_lines)

    # Insert stat section
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
    new_lines.extend(avar2_yaml.strip().splitlines())
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

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate and inject STAT and avar2 sections into config.yaml from CSV."
    )
    ap.add_argument("--csv", required=True, type=Path, help="Path to CSV exported from spreadsheet.")
    ap.add_argument("--config", required=True, type=Path, help="Path to config.yaml to update.")
    ap.add_argument("--font-key", default=None, help="Override font key (otherwise auto-detected).")
    ap.add_argument("--no-backup", action="store_true", help="Don't create backup of config.yaml.")
    ap.add_argument("--dry-run", action="store_true", help="Validate only, don't write changes.")
    args = ap.parse_args(argv)

    try:
        # Step 1: Validate CSV structure
        print("Step 1: Validating CSV structure...", file=sys.stderr)
        validate_csv_structure(args.csv)
        print("  ✓ CSV structure valid", file=sys.stderr)

        # Step 2: Read CSV mappings
        print("Step 2: Reading CSV mappings...", file=sys.stderr)
        mappings = read_csv_mappings(args.csv)
        print(f"  ✓ Read {len(mappings)} mappings", file=sys.stderr)

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
        axis_values = extract_axis_values_from_csv(args.csv)
        stat_data = generate_stat_section(axis_values, font_key)
        validate_stat_section(stat_data, font_key)
        print(f"  ✓ STAT section generated ({len(stat_data[font_key])} axes)", file=sys.stderr)

        # Step 6: Generate avar2 section
        print("Step 6: Generating avar2 section...", file=sys.stderr)
        avar2_yaml = generate_avar2_yaml_string(mappings, font_key, include_group_headers=True)
        validate_avar2_yaml(avar2_yaml, font_key)
        # Count entries
        avar2_parsed = yaml.safe_load(avar2_yaml)
        entry_count = len(avar2_parsed["avar2"][font_key])
        print(f"  ✓ avar2 section generated ({entry_count} entries)", file=sys.stderr)

        # Step 7: Merge into config
        print("Step 7: Merging sections into config...", file=sys.stderr)
        merged_config, avar2_yaml_final = merge_config(config, stat_data, avar2_yaml, font_key)
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
        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

